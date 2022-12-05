#!/usr/bin/python3

# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

import socket
import logging
import re
from urllib.parse import unquote

import pymedia_redis

from pymedia_const import REDIS_SERVER, REDIS_PORT, REDIS_DB

# ---------------------

LMS_SERVER = "juke"
LMS_SERVER_PORT = 9090
LMS_PLAYERID = "13:89:0e:c8:1d:a5"

logging.basicConfig(level=logging.DEBUG)

# ---------------------

def cdsp_set_volume(vol, _redis):
    """Set CamillaDSP volume via redis action.

    only set CamillaDSP volume if CamillaDSP isn't muted to avoid "feedback
    loop": when cdsp is muted the lms player is paused (see pymedia_cdsp);
    however LMS and/or squeezelite set the mixer's volume to 0%, which trigger
    alsa mixer events, setting cdsp volume to 0%. Then, on "un-mute",
    LMS/squeezelite restores the mixer to its previous level, triggering another
    set of alsa mixer events and messing again with cdsp's volume.
    """
    if not _redis.get_s("CDSP:mute"):
        logging.info("Action - set CDSP volume to %s", vol)
        _redis.send_action('CDSP', f"volume_perc:{vol}")


def receive_volume_event(_socket, player_id, callback, cb_args=()):

    # 13%3A89%3A0e%3Ac8%3A1d%3Aa5 mixer volume 50
    regex = re.compile("^" + player_id + r" mixer volume (\d+)$")

    # subscribe to volume changes
    _socket.send("subscribe mixer,pause\r".encode("UTF-8"))


    while True:
        data = _socket.recv(4096)
        line = unquote(data.decode("UTF-8").strip())
        logging.debug("received %s", line)
        re_match = regex.match(line)
        if re_match:
            vol = re_match.group(1)
            logging.info("Volume changed to %s for player %s", vol,
                         LMS_PLAYERID)
            callback(vol, *cb_args)


# ---------------------

if __name__ == '__main__':

    redis = pymedia_redis.RedisHelper(REDIS_SERVER, REDIS_PORT, REDIS_DB,
                                      'LMS_VOL')

    srvsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #srvsock.settimeout(3) # 3 second timeout on commands
    srvsock.connect((LMS_SERVER, LMS_SERVER_PORT))

    try:
        receive_volume_event(srvsock, LMS_PLAYERID, cdsp_set_volume,
                             cb_args=(redis,))
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt, shutting down...")
        srvsock.close()
