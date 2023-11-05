import os
import sys

sys.path.append(os.environ["TFM_DIR"])

import zmq
from rc.InhibitManager import InhibitManager
import os, sys, time

sys.path.append(os.getcwd())


def do_enable_base(self):
    context = zmq.Context()
    publisher = InhibitManager.StatusPUBNode(context, "tcp://*:5556")
    time.sleep(0.5)
    publisher.send_status_msg("TFM", "ENABLE", "OK")


def do_disable_base(self):
    context = zmq.Context()
    publisher = InhibitManager.StatusPUBNode(context, "tcp://*:5556")
    time.sleep(0.5)
    publisher.send_status_msg("TFM", "ENABLE", "ERROR")
