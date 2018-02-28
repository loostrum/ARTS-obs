#!/usr/bin/env python
#
# Script to set up a full survey mode observation on the ARTS cluster
# Should only be used on the master node
# Author: L.C. Oostrum

import os
import sys
import argparse

import yaml

CONFIGFILE="config.yaml"

class Survey(object):
    """Class for setting up an ARTS survey mode observation"
    """

    def __init__(self, args):
        self.parse_args(args)


    def parse_args(self, args):
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), CONFIGFILE)
        with open(filename, 'r') as f:
            config = yaml.load(f)
        conf_sc = 'sc{:.0f}'.format(args.science_case)
        conf_mode = args.science_mode.lower()
        # science case specific
        self.nbit = config[conf_sc]['nbit']
        self.nchan = config[conf_sc]['nchan']
        self.time_unit = config[conf_sc]['time_unit']
        self.nbeams = config[conf_sc]['nbeams']
        self.missing_beams = config[conf_sc]['missing_beams']
        self.nbuffer = config[conf_sc]['nbuffer']
        self.valid_modes = config[conf_sc]['valid_modes']
        self.network_port_start = config[conf_sc]['network_port_start']
        self.tsamp = config[conf_sc]['tsamp']
        self.pagesize = config[conf_sc]['pagesize']
        # pol and beam specific
        self.ntabs = config[conf_mode]['ntabs']
        self.science_mode  = config[conf_mode]['science_mode']
        
        

if __name__ == '__main__':
    #parser = argparse.ArgumentParser(prog="start_survey_master.py", \
    parser = argparse.ArgumentParser(description="Start a survey mode observation on ARTS")
    # source info
    parser.add_argument("--src", type=str, help="Source name " \
                            "(Default: None)", default="None")
    parser.add_argument("--ra", type=str, help="J2000 RA in hh:mm:ss.s format " \
                            "(Default: 00:00:00)", default="00:00:00")
    parser.add_argument("--dec", type=str, help="J2000 DEC in dd:mm:ss.s format " \
                            "(Default: 00:00:00)", default="00:00:00")
    # time related
    parser.add_argument("--duration", type=float, help="Observation duration in seconds " \
                            "(Default: 10.24)", default=10.24)
    parser.add_argument("--tstart", type=str, help="Start time (UTC), e.g. 2017-01-01 00:00:00 " \
                            "(Default: now + 5 seconds)", default="default")
    # either start and end beam or list of beams
    beamgroup = parser.add_mutually_exclusive_group()
    beamgroup.add_argument("--sbeam", type=int, help="No of first CB to record " \
                            "(Default: 21)", default=21)
    beamgroup.add_argument("--beams", type=str, help="List of beams to process. Use instead of sbeam and ebeam")
    parser.add_argument("--ebeam", type=int, help="No of last CB to record " \
                            "(Default: same as sbeam", default=0)
    # observing modes
    parser.add_argument("--obs_mode", type=str, help="Observation mode. Can be bruteforce, subband, dump, scrub, fil, fits, survey" \
                            "(Default: fil", default="fil")
    parser.add_argument("--science_case", type=int, help="Science case " \
                            "(Default: 4", default=4)
    parser.add_argument("--science_mode", type=str, help="Sciene mode. Can be I+TAB, IQUV+TAB, I+IAB, IQUV+IAB " \
                            "(Default: I+TAB", default="I+TAB")
    args = parser.parse_args()

    Survey(args)
