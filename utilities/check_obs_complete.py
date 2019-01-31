#!/usr/bin/env python
#
# Check if observation is complete and set status in ATDB

import os
import sys
import subprocess
import ast
import argparse

from time import time, sleep
import numpy as np


TIMEOUT=120


def log(message):
    print "Master-check-obs-complete: {}".format(message)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Check status of observation and put in ATDB")
    parser.add_argument('--cbs', type=str, help="List of CBs", required=True)
    parser.add_argument('--taskid', type=str, help="Task ID", required=True)

    args = parser.parse_args()

    # format list of compound beams
    cbs = np.array(ast.literal_eval(args.cbs), dtype=int)
    # get list of nodes
    nodelist = ["arts0{:02d}".format(cb+1) for cb in cbs]

    # check status of all nodes
    complete = False
    start_time = time()
    while not complete and time() < start_time + TIMEOUT:
        # check if dadafits is running for each node
        complete = True
        for node in set(nodelist):
            log("Checking status of {}".format(node))
            cmd = "ssh -o ConnectTimeout=10 {} 'ps uax | grep ['d']adafits >/dev/null'; echo $?".format(node)
            status = int(subprocess.check_output(cmd, shell=True))
            if status == 255:
                # ssh failed
                log("Failed to connect to {}".format(node))
                complete = False
                continue
            elif status == 0:
                # dadafits is running
                log("{} not ready".format(node))
                complete = False
            elif status == 1:
                log("{} ready".format(node))
                # dadafits not running, all ok
                # no need to check this node again
                nodelist.remove(node)
                continue           

    # set status to completing
    cmd = "source /home/arts/atdb_client/env2/bin/activate; atdb_service -o change_status " \
          " --resource observations --search_key taskid:{taskid} --status completing " \
          " --atdb_host prod".format(taskid=args.taskid)
    print cmd

