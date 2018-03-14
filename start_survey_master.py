#!/usr/bin/env python
#
# Script to set up a full survey mode observation on the ARTS cluster
# Should only be used on the master node
# Author: L.C. Oostrum

import os
import sys
import argparse
import datetime
import socket
from time import sleep

import yaml
import numpy as np
from astropy.time import Time

CONFIG = "config.yaml"
NODECONFIG = "nodes/CB{:02d}.yaml"
NODEHEADER = "nodes/CB{:02d}_header.txt"
TEMPLATE = "header_template.txt"
AMBERCONFIG = "amber.yaml"
AMBERCONFDIR = "amber_conf"


def run_on_node(node, command, background=False):
    """Run command on an ARTS node. Assumes ssh keys have been set up
        node: nr of node (string or int)
        command: command to run
        background: whether to run ssh in the background
    """
    if isinstance(node, str):
        if len(node) == 1:
            # assume a leading 0 is missing
            node = '0'+node
        elif len(node) > 2:
            # wrong, should only have 2 digits. Assume extra leading zeros
            node = node[-3:]
        hostname = "arts0{}".format(node)
    else:
        hostname = "arts0{:02d}".format(node)

    if background:
        #ssh_cmd = "ssh {} {} &".format(hostname, command)
        ssh_cmd = "ssh {} 'source $HOME/venv/bin/activate; {}' &".format(hostname, command)
    else:
        #ssh_cmd = "ssh {} {}".format(hostname, command)
        ssh_cmd = "ssh {} 'source $HOME/venv/bin/activate; {}' &".format(hostname, command)
    log("Executing '{}'".format(ssh_cmd))
    os.system(ssh_cmd)


def log(message):
    """
    Log a message. Prints the hostname, then the message
    """
    print "Master: {}".format(message)


def start_survey(args):
    """Sets up a survey mode observation from the master node
    """

    # initialize parameters
    pars = {}
    # Load static configuration
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), CONFIG)
    with open(filename, 'r') as f:
        config = yaml.load(f)
    conf_sc = 'sc{:.0f}'.format(args.science_case)  # sc3 or sc4
    conf_mode = args.science_mode.lower()  # i+tab, iquv+tab, i+iab, iquv+iab
    # IQUV not yet supported
    if 'iquv' in conf_mode:
        log("ERROR: IQUV modes not yet supported")
        exit()
    # science case specific
    pars['science_case'] = args.science_case
    pars['nbit'] = config[conf_sc]['nbit']
    pars['nchan'] = config[conf_sc]['nchan']
    pars['freq'] = config[conf_sc]['freq']
    pars['bw'] = config[conf_sc]['bw']
    pars['time_unit'] = config[conf_sc]['time_unit']
    pars['nbeams'] = config[conf_sc]['nbeams']
    pars['missing_beams'] = config[conf_sc]['missing_beams']
    pars['nbuffer'] = config[conf_sc]['nbuffer']
    pars['valid_modes'] = config[conf_sc]['valid_modes']
    pars['network_port_start'] = config[conf_sc]['network_port_start']
    pars['tsamp'] = config[conf_sc]['tsamp']
    pars['pagesize'] = config[conf_sc]['pagesize']
    # pol and beam specific
    pars['ntabs'] = config[conf_mode]['ntabs']
    pars['science_mode']  = config[conf_mode]['science_mode']
    # derived values
    pars['chan_width'] = float(pars['bw']) / pars['nchan']
    pars['min_freq'] = pars['freq'] - pars['bw'] / 2 + pars['chan_width'] / 2
    if args.obs_mode == 'survey':
        pars['nreader'] = 5
    elif args.obs_mode == 'amber':
        pars['nreader'] = 4
    else:
        pars['nreader'] = 1

    # load observation specific arguments
    pars['proctrigger'] = args.proctrigger
    pars['amber_mode'] = args.amber_mode
    pars['snrmin'] = args.snrmin
    pars['source'] = args.source
    pars['ra'] = args.ra
    pars['dec'] = args.dec
    # Observing time, has to be multiple of 1.024 seconds
    pars['nbatch'] = int(np.ceil(args.duration / 1.024))
    pars['tobs'] = pars['nbatch'] * 1.024
    # start time
    if args.tstart == 'default':
        tstart = datetime.datetime.utcnow() + datetime.timedelta(seconds=15)
        pars['utcstart'] = tstart.strftime('%Y-%m-%d %H:%M:%S')
    else:
        #tstart = datetime.datetime(args.tstart)
        #pars['utcstart'] = args.tstart
        log("Specific start time not yet supported")
        exit()  
    starttime = Time(pars['utcstart'], format='iso', scale='utc')
    pars['date'] = tstart.strftime("%Y%m%d")
    pars['datetimesource'] = "{}.{}".format(pars['utcstart'].replace(' ','-'), pars['source'])
    pars['mjdstart'] = starttime.mjd
    # startpacket has to be along
    pars['startpacket'] = long(starttime.unix) * pars['time_unit']
    # output directories
    pars['output_dir'] = config[conf_sc]['output_dir'].format(**pars)
    pars['log_dir'] = config[conf_sc]['log_dir'].format(**pars)
    pars['amber_dir'] = config[conf_sc]['amber_dir'].format(**pars)
    # observing mode
    if args.obs_mode not in pars['valid_modes']:
        log("ERROR: observation mode not valid: {}".format(args.obs_mode))
        exit()
    else:
        pars['obs_mode'] = args.obs_mode
    # beams
    if not args.beams is None:
        pars['beams'] = [int(beam) for beam in args.beams.split(',')]
        # make sure each beams is present only once
        pars['beams'] = list(set(pars['beams']))
    else:
        pars['sbeam'] = args.sbeam
        if args.ebeam == 0:
            pars['ebeam'] = pars['sbeam']
        elif args.ebeam < pars['sbeam']:
            log("WARNING: ebeam cannot be smaller than sbeam. Setting ebeam to sbeam ({})".format(pars['sbeam']))
            pars['ebeam'] = pars['sbeam']
        else:
            pars['ebeam'] = args.ebeam
        pars['beams'] = range(pars['sbeam'], pars['ebeam']+1)
   
    # check validity of beams
    if min(pars['beams']) < 0:
        log("ERORR: CB index < 0 is impossible")
        exit()
    if max(pars['beams']) > pars['nbeams']-1:
        log("ERROR: CB index > {} is impossible".format(pars['nbeams']-1))
        exit()
    # remove the missing beams
    for beam in pars['missing_beams']:
        try:
            pars['beams'].remove(beam)
        except ValueError:
            # beam was not in list of beams anyway
            continue

    # we have all parameters now, create psrdada header and config file for each beam
    # config file
    cfg = {}
    cfg['buffersize'] = pars['ntabs'] * pars['nchan'] * pars['pagesize']
    cfg['nbuffer'] = pars['nbuffer']
    cfg['nreader'] = pars['nreader']
    cfg['obs_mode'] = pars['obs_mode']
    cfg['startpacket'] = pars['startpacket']
    cfg['duration'] = pars['tobs']
    cfg['nbatch'] = pars['nbatch']
    cfg['output_dir'] = pars['output_dir']
    cfg['ntabs'] = pars['ntabs']
    cfg['amber_conf_dir'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), AMBERCONFDIR)
    cfg['amber_config'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), AMBERCONFIG)
    cfg['amber_dir'] = pars['amber_dir']
    cfg['log_dir'] = pars['log_dir']
    cfg['snrmin'] = pars['snrmin']
    cfg['proctrigger'] = pars['proctrigger']
    cfg['amber_mode'] = pars['amber_mode']

    # load PSRDADA header template
    with open(TEMPLATE, 'r') as f:
        header_template = f.read()

    for beam in pars['beams']:
        # add CB-dependent parameters
        cfg['beam'] = beam
        cfg['dadakey'] = pars['network_port_start'] + beam
        cfg['network_port'] = pars['network_port_start'] + beam
        cfg['header'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), NODEHEADER.format(beam))

        # save to file
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), NODECONFIG.format(beam))
        with open(filename, 'w') as f:
            yaml.dump(cfg, f, default_flow_style=False)



        # fill in the psrdada header keys
        temppars = pars.copy()
        temppars['ra'] = pars['ra'].replace(':', '')
        temppars['dec'] = pars['dec'].replace(':','')
        temppars['resolution'] = pars['pagesize'] * pars['nchan']
        temppars['bps'] = int(pars['pagesize'] * pars['nchan'] / 1.024)
        temppars['beam'] = beam
        temppars['az_start'] = 0
        temppars['za_start'] = 0

        header = header_template.format(**temppars)

        with open(NODEHEADER.format(beam), 'w') as f:
            f.write(header)

    # TEMP copy the nodes config
    log("Copying files to nodes")
    for beam in pars['beams']:
        node = beam + 1
        cmd = "scp -r nodes/ arts0{:02d}.apertif:ARTS-obs/ >/dev/null &".format(node)
        os.system(cmd)
    sleep(2)
    log("Done")

    # Start the node scripts
    for beam in pars['beams']:
        node = beam + 1
        script_path = os.path.realpath(os.path.dirname(__file__))
        node_script = os.path.join(script_path, "start_survey_node.py")
        cmd = "{} nodes/CB{:02d}.yaml".format(node_script, beam)
        run_on_node(node, cmd, background=True)

    sleep(1)
    # done
    log("All nodes started for observation")

        

if __name__ == '__main__':
    # check if this is the master node
    hostname = socket.gethostname()
    if not hostname == "arts041":
        log("ERROR: an observation should be started from the master node (arts041)")
        exit()

    parser = argparse.ArgumentParser(description="Start a survey mode observation on ARTS")
    # source info
    parser.add_argument("--source", type=str, help="Source name " \
                            "(Default: None)", default="None")
    parser.add_argument("--ra", type=str, help="J2000 RA in hh:mm:ss.s format " \
                            "(Default: 00:00:00)", default="00:00:00")
    parser.add_argument("--dec", type=str, help="J2000 DEC in dd:mm:ss.s format " \
                            "(Default: 00:00:00)", default="00:00:00")
    # time related
    parser.add_argument("--duration", type=float, help="Observation duration in seconds " \
                            "(Default: 10.24)", default=10.24)
    parser.add_argument("--tstart", type=str, help="Start time (UTC), e.g. 2017-01-01 00:00:00 " \
                            "(Default: now + 15 seconds)", default="default")
    # either start and end beam or list of beams: make beams and sbeam mutually exclusive
    beamgroup = parser.add_mutually_exclusive_group()
    beamgroup.add_argument("--sbeam", type=int, help="No of first CB to record " \
                            "(Default: 21)", default=21)
    beamgroup.add_argument("--beams", type=str, help="List of beams to process. Use instead of sbeam and ebeam")
    parser.add_argument("--ebeam", type=int, help="No of last CB to record " \
                            "(Default: same as sbeam)", default=0)
    # observing modes
    parser.add_argument("--obs_mode", type=str, help="Observation mode. Can be dump, scrub, fil, fits, amber, survey" \
                            "(Default: fil)", default="fil")
    parser.add_argument("--science_case", type=int, help="Science case " \
                            "(Default: 4)", default=4)
    parser.add_argument("--science_mode", type=str, help="Science mode. Can be I+TAB, IQUV+TAB, I+IAB, IQUV+IAB " \
                            "(Default: I+IAB)", default="I+IAB")
    # amber and trigger processing
    parser.add_argument("--amber_mode", type=str, help="AMBER dedispersion mode, can be bruteforce or suband " \
                            "(Default: subband)", default="subband")
    parser.add_argument("--snrmin", type=float, help="AMBER minimum S/N " \
                            "(Default: 10)", default=10)
    parser.add_argument("--proctrigger", help="Process and email triggers. "\
                            "(Default: False)", action="store_true")
    args = parser.parse_args()

    start_survey(args)
