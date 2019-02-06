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


# Timeout in seconds in case of broken connection to a node
TIMEOUT=30


def log(message):
    print "Master-check-obs-complete: {}".format(message)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Check status of observation and put in ATDB")
    parser.add_argument('--date', type=str, help="Date of observation", required=True)
    parser.add_argument('--obs', type=str, help="Observation ID", required=True)
    parser.add_argument('--cbs', type=str, help="List of CBs", required=True)
    parser.add_argument('--taskid', type=str, help="Task ID", required=True)

    args = parser.parse_args()
    kwargs = vars(args)

    # format list of compound beams
    cbs = np.array(ast.literal_eval(args.cbs), dtype=int)

    # check status of all nodes
    complete = False
    start_time = time()
    end_time = start_time + TIMEOUT
    while not complete and time() < end_time:
        # check if fits file exists for each node
        complete = True
        for cb in set(cbs):
            node = "arts0{:02d}".format(cb+1)
            log("Checking status of {}".format(node))

            # file name glob that works for both TAB and IAB
            fname = "/data2/output/{date}/{obs}/fits/CB{cb:02d}/ARTS{taskid}_CB{cb:02d}*.fits".format(cb=cb, **kwargs)

            cmd = "ssh -o ConnectTimeout=10 {} 'ls {} 1>/dev/null 2>/dev/null'; echo $?".format(node, fname)
            status = int(subprocess.check_output(cmd, shell=True))
            if status == 255:
                # ssh failed
                log("Failed to connect to {}".format(node))
                complete = False
            elif status == 0:
                # file exists, this node is ready
                log("{} ready".format(node))
                # no need to check it again: remove from cb list
                cbs = np.delete(cbs, np.where(cbs == cb))
            else:
                # file does not exist yet
                log("{} not ready".format(node))
                complete = False

    # set status to completing
    cmd = "source /home/arts/atdb_client/env2/bin/activate; atdb_service -o change_status " \
          " --resource observations --search_key taskid:{taskid} --status completing " \
          " --atdb_host prod".format(taskid=args.taskid)
    log(cmd)
    os.sytem(cmd)

