#!/usr/bin/env python
#
# Script to set up a full survey mode observation on the ARTS cluster
# Should only be used on the master node
# Author: L.C. Oostrum

import os
import sys
import argparse
import datetime

import yaml
import numpy as np
from astropy.time import Time

CONFIG = "config.yaml"
NODECONFIG = "nodes/CB{:02d}.yaml"
HEADER = "nodes/CB{:02d}_header.txt"
TEMPLATE = "header_template.txt"


def run_on_node(node, command, background=False):
    """Run command on an ARTS node. Assumes ssh keys have been set up
        node: nr of node (string or int)
        command: command to run
        background: whether to run ssh in the background
    """
    if isinstance(node, str):
        hostname = "arts0{}".format(node)
    else:
        hostname = "arts0{:02d}".format(node)

    if background:
        ssh_cmd = "ssh {} {} &".format(hostname, command)
    else:
        ssh_cmd = "ssh {} {}".format(hostname, command)
    print "Executing '{}'".format(ssh_cmd)
    os.system(ssh_cmd)


def start_survey(args):
    """Sets up a survey mode observation from the master node
    """

    # initialize parameters
    pars = {}
    # Load static configuration
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), CONFIG)
    with open(filename, 'r') as f:
        config = yaml.load(f)
    conf_sc = 'sc{:.0f}'.format(args.science_case)  # sc4 or sc4
    conf_mode = args.science_mode.lower()  # i+tab, iquv+tab, i+iab, iquv+iab
    # IQUV not yet supported
    if 'iquv' in conf_mode:
        print "ERROR: IQUV modes not yet supported"
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

    # load observation specific arguments
    pars['snrmin'] = args.snrmin
    pars['source'] = args.source
    pars['ra'] = args.ra
    pars['dec'] = args.dec
    # Observing time, has to be multiple of 1.024 seconds
    pars['nbatch'] = np.ceil(args.duration / 1.024)
    pars['tobs'] = pars['nbatch'] * 1.024
    # start time
    if args.tstart == 'default':
        tstart = datetime.datetime.utcnow() + datetime.timedelta(seconds=10)
        pars['utcstart'] = tstart.strftime('%Y-%m-%d %H:%M:%S')
    else:
        #tstart = datetime.datetime(args.tstart)
        #pars['utcstart'] = args.tstart
        print "Specific start time not yet supported"
        exit()  
    starttime = Time(pars['utcstart'], format='iso', scale='utc')
    pars['date'] = tstart.strftime("%Y%m%d")
    pars['datetimesource'] = "{}.{}".format(pars['utcstart'].replace(' ','-'), pars['source'])
    pars['mjdstart'] = starttime.mjd
    # startpacket has to be along
    pars['startpacket'] = long(starttime.unix) * pars['time_unit']
    # output directory
    pars['output_dir'] = config[conf_sc]['output_dir'].format(date=pars['date'], datetimesource=pars['datetimesource'])
    # observing mode
    if args.obs_mode not in pars['valid_modes']:
        print "ERROR: observation mode not valid: {}".format(args.obs_mode)
        exit()
    else:
        pars['mode'] = args.obs_mode
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
            print "WARNING: ebeam cannot be smaller than sbeam. Setting ebeam to sbeam ({})".format(pars['sbeam'])
            pars['ebeam'] = pars['sbeam']
        else:
            pars['ebeam'] = args.ebeam
        pars['beams'] = range(pars['sbeam'], pars['ebeam']+1)
   
    # check validity of beams
    if min(pars['beams']) < 0:
        print "ERORR: CB index < 0 is impossible"
        exit()
    if max(pars['beams']) > pars['nbeams']-1:
        print "ERROR: CB index > {} is impossible".format(pars['nbeams']-1)
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
    cfg['pagesize'] = pars['pagesize']
    cfg['nbuffer'] = pars['nbuffer']
    cfg['startpacket'] = pars['startpacket']
    cfg['output_dir'] = pars['output_dir']

    for beam in pars['beams']:
        # add CB-dependent parameters
        cfg['dadakey'] = pars['network_port_start'] + beam
        cfg['header'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), HEADER.format(beam))

        # save to file
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), NODECONFIG.format(beam))
        with open(filename, 'w') as f:
            yaml.dump(cfg, f, default_flow_style=False)

        # load PSRDADA header template
        with open(TEMPLATE, 'r') as f:
            header_template = f.read()

        # add header keys
        header = header_template.format(source=pars['source'], 
                    utc_start=pars['utcstart'],
                    mjd_start=pars['mjdstart'],
                    freq=pars['freq'],
                    bw=pars['bw'],
                    tsamp=pars['tsamp'],
                    min_freq=pars['min_freq'],
                    nchan=pars['nchan'],
                    chan_width=pars['chan_width'],
                    page_size=pars['pagesize'],
                    nbit=pars['nbit'],
                    resolution=pars['pagesize'] * pars['nchan'],
                    bps=int(pars['pagesize'] * pars['nchan'] / 1.024),
                    science_case=pars['science_case'],
                    science_mode=pars['science_mode'],
                    ra=pars['ra'].replace(':',''),
                    dec=pars['dec'].replace(':',''),
                    beam=beam,
                    az_start=0,
                    za_start=0)
        with open(HEADER.format(beam), 'w') as f:
            f.write(header)

        

if __name__ == '__main__':
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
                            "(Default: now + 10 seconds)", default="default")
    # either start and end beam or list of beams: make beams and sbeam mutually exclusive
    beamgroup = parser.add_mutually_exclusive_group()
    beamgroup.add_argument("--sbeam", type=int, help="No of first CB to record " \
                            "(Default: 21)", default=21)
    beamgroup.add_argument("--beams", type=str, help="List of beams to process. Use instead of sbeam and ebeam")
    parser.add_argument("--ebeam", type=int, help="No of last CB to record " \
                            "(Default: same as sbeam", default=0)
    # observing modes
    parser.add_argument("--obs_mode", type=str, help="Observation mode. Can be dump, scrub, fil, fits, survey" \
                            "(Default: fil", default="fil")
    parser.add_argument("--science_case", type=int, help="Science case " \
                            "(Default: 4", default=4)
    parser.add_argument("--science_mode", type=str, help="Science mode. Can be I+TAB, IQUV+TAB, I+IAB, IQUV+IAB " \
                            "(Default: I+IAB", default="I+IAB")
    # amber
    parser.add_argument("--snrmin", type=float, help="AMBER minimum S/N " \
                            "(Default: 10)", default=10)
    args = parser.parse_args()

    start_survey(args)
