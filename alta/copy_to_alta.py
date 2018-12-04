#!/usr/bin/env python
# 
# Create node scripts to transfer data to alta
# Gather results and post to slack

import os
import sys
import ast
import subprocess
from textwrap import dedent
from time import sleep

from argparse import ArgumentParser, RawTextHelpFormatter
import numpy as np


def run_on_node(hostname, command, background=True):
    """Run command on an ARTS node. Assumes ssh keys have been set up
        node: nr of node (string or int)
        command: command to run
        background: whether to run ssh in the background
    """
    if background:
        ssh_cmd = "ssh {} \"{}\" &".format(hostname, command)
    else:
        ssh_cmd = "ssh {} \"{}\"".format(hostname, command)
    print "Executing '{}'".format(ssh_cmd)
    os.system(ssh_cmd)


def write_commands(**kwargs):
    """
    Create commands to copy files to ALTA for one node
    """

    cmds = dedent("""    #!/bin/bash
    if ! [ -d {source_dir} ]; then
        result="CB{cb}: FAIL - fits directory not present."
        echo $result > {result_file}
        exit
    elif ! [ ls -A {source_dir} ]; then
        result="CB{cb}: FAIL - fits directory is empty."
        echo $result > {result_file}
        exit

    imkdir -p {dest_dir}
    iput -IPr -X {status_file} --lfrestart {lfstatus_file} --retries 5 -N {nthreads} -R {resc} {source_dir} {dest_dir}
    failed=$(irsync -lsr {source_dir} i:{dest_dir} 2>&1)
    
    if [ "$failed" == "" ]; then
        result="CB{cb}: SUCCESS"
    else
        result="CB{cb}: FAILED - $failed"
    echo $result > {result_file}
    exit""").format(**kwargs)

    with open(kwargs['out_file'], 'rw') as f:
        f.write(cmds)

def get_resc(cb):
    """
    Spread 32 in-use ARTS nodes over 4 ALTA servers
        based on CB number
    """
    if cb < 10:
        resc = "alta-icat-Resc"
    elif cb < 20:
        resc = "alta-res1-Resc"
    elif cb < 30:
        resc = "alta-res2-Resc"
    elif cb < 40:
        resc = "alta-res3-Resc"
    return resc
    
def main(args):
    # convert args to dict
    kwargs = vars(args)
    
    # create directories
    for directory in (args.source_dir, args_log_dir, args.script_dir):
        if not os.path.isdir(directory):
            os.makedirs(directory)
    
    # format list of compound beams
    cbs= np.array(ast.literal_eval(args.cbs), dtype=int)
    # get list of nodes
    nodelist = ["arts0{:02d}".format(cb+1) for cb in cbs]

    # loop over nodes and create commands
    commands_to_run = {}
    result_files = {}
    for node, cb in zip(nodelist, cbs):
        nodekwargs = kwargs.copy()
        nodekwargs['node'] = node
        nodekwargs['cb'] = "{:02d}".format(cb)
        nodekwargs['resc'] = get_resc(cb)
        nodekwargs['source_dir'] = "/data2/output/{date}/{obs}/CB{cb}/fits".format(**nodekwargs)
        nodekwargs['dest_dir'] = "/altaZone/home/arts_main/arts_sc4/{date}/{obs}/CB{cb}".format(**nodekwargs)
        nodekwargs['out_file'] = "{script_dir}/{node}.sh".format(**nodekwargs)
        nodekwargs['log_file'] = "{log_dir}/{node}.log".format(**nodekwargs)
        nodekwargs['result_file'] = "{script_dir}/{node}.result".format(**nodekwargs)
        nodekwargs['status_file'] = "{source_dir}/altacopy.irods-status".format(**nodekwargs)
        nodekwargs['lfstatus_file'] = "{source_dir}/altacopy.lf-irods-status".format(**nodekwargs)

        write_commands(**nodekwargs)
        result_files[node] = nodekwargs['result_file']
        commands_to_run[node] = "cd {script_dir}; bash {out_file} 2>&1 > {log_file}".format(**nodekwargs)

    # run all commands
    for node in nodelist:
        run_on_node(node, commands_to_run[node])

    # wait for all to be done -> check result files
    nbeam = len(cbs)
    print "Expecting {} beams".format(nbeam)
    beams_done = 0
    while beams_done < nbeam:
        sleep(10)
        beams_done = 0 
        for node in nodelist:
            if os.path.isfile(result_files[node]):
                beams_done += 1 
        print "{} out of {} CBs transferred".format(beams_done, nbeam)

    # Gather output into one message
    message = "ARTS transfer of {obs} completed:\n".format(**kwargs)
    result = []
    for fname in result_files.items():
        with open(fname) as f:
            content = f.readlines()
        result.append(content)
    message += "\n".join(result)

    # Put message on slack: todo
    print "Message:"
    print message
    
if __name__ == '__main__':
    home = os.path.expanduser('~')

    parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
    parser.add_argument('--date', type=str, help="Date of observation", required=True)
    parser.add_argument('--obs', type=str, help="Observation ID", required=True)
    parser.add_argument('--cbs', type=str, help="List of CBs", required=True)
    parser.add_argument('--nthreads', type=int, default=5, 
                        help="Number of threads per iput, default: %(default)s")
    parser.add_argument('--script_dir', type=str, default="{}/alta".format(home),
                        help="Script directory, default: %(default)s")
    parser.add_argument('--log_dir', type=str, default="{}/alta/log".format(home), 
                        help="Log directory, default: %(default)s")

    # print help if not arguments are supplied
    if len(sys.argv) == 1:
        parser.print_help()
        exit()

    args = parser.parse_args()
    main(args)
