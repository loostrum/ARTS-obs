#!/usr/bin/env python
#
# Script to set up a full survey mode observation on the ARTS cluster
# Should only be used on the worker nodes
# Author: L.C. Oostrum

import os
import sys
import socket
from time import sleep

import yaml
import numpy as np


class Survey(object):
    """Start a survey mode observation on ARTS. This class runs the relevant commands on the current node
    """

    def __init__(self, config):
        """
        config: dict with settings, as generated by the master script
        """
        # set hostname
        self.hostname = socket.gethostname()
        
        # how long to sleep between commands
        waittime = 0.5

        # check CB
        self.config = config
        expected_CB = int(self.hostname[5:7]) - 1
        if not self.config['beam'] == expected_CB:
            self.log("WARNING: Requested to record CB {}, expected CB {}".format(config['beam'], expected_CB))        

        # start the programmes
        # remove running ringbuffers, AMBER, etc.
        self.clean()
        sleep(waittime)
        # create ringbuffer
        self.ringbuffer()
        sleep(waittime)
        # start readers depending on observing mode
        if config['obs_mode'] == 'scrub':
            self.scrub()
        elif config['obs_mode'] == 'dump':
            self.dump()
        elif config['obs_mode'] == 'fil':
            self.dadafilterbank()
        elif config['obs_mode'] == 'fits':
            self.dadafits()
        elif config['obs_mode'] == 'amber':
            self.amber()
        elif config['obs_mode'] == 'survey':
            self.survey()
        sleep(waittime)
        # start fill ringbuffer
        self.fill_ringbuffer()
        sleep(waittime)
        # Everything has been started
        self.log("Everything started")


    def log(self, message):
        """
        Log a message. Prints the hostname, then the message
        """
        print "{}: {}".format(self.hostname, message)


    def clean(self):
        self.log("Removing old ringbuffers")
        cmd = "dada_db -d -k {} 2>/dev/null".format(self.config['dadakey'])
        self.log(cmd)
        os.system(cmd)


    def ringbuffer(self):
        self.log("Starting ringbuffers")
        cmd = "dada_db -k {} -b {} -n {} -p -r {} &".format(self.config['dadakey'], self.config['buffersize'], self.config['nbuffer'], self.config['nreader'])
        self.log(cmd)
        os.system(cmd)


    def fill_ringbuffer(self):
        self.log("Starting fill_ringbuffer")
        cmd = "fill_ringbuffer -c {} -m {} -b {} -k {} -s {} -d {} -p {}".format(self.config['science_case'], self.config['science_mode'], self.config['pagesize'], \
                                                            self.config['dadakey'], self.config['startpacket'], self.config['duration'], self.config['network_port'])
        self.log(cmd)
        os.system(cmd)


    def scrub(self):
        self.log("Starting dada_dbscrubber")
        cmd = "dada_dbscrubber -k {} &".format(self.config['dadakey'])
        self.log(cmd)
        os.system(cmd)


    def dump(self):
        self.log("Starting dada_dbdisk")
        output_dir = os.path.join(self.config['output_dir'], 'filterbank')
        os.system("mkdir -p {}".format(output_dir))
        output_prefix = os.path.join(output_dir, 'CB{:02d}'.format(self.config['beam']))
        cmd = "dada_dbdisk -k {} &"


    def dadafilterbank(self):
        self.log("Starting dadafilterbank")
        output_dir = os.path.join(self.config['output_dir'], 'filterbank')
        os.system("mkdir -p {}".format(output_dir))
        output_prefix = os.path.join(output_dir, 'CB{:02d}'.format(self.config['beam']))
        cmd = "dadafilterbank -k {} -n {} -l {} &".format(self.config['dadakey'], output_prefix, "/dev/null")


    def dadafits(self):
        self.log("Starting dadafits")
        self.log("ERROR: dadafits not yet supported")
        exit()


    def amber(self):
        self.log("Starting AMBER")
        output_dir = os.path.join(self.config['output_dir'], 'amber')
        os.system("mkdir -p {}".format(output_dir))
        # load AMBER config
        with open(self.config['amber_config'], 'r') as f:
            cfg = yaml.load(f)
        # add output prefix
        cfg['output_prefix'] = os.path.join(output_dir, 'CB{:02d}'.format(self.config['beam']))
        # make dict with fullconfig, because AMBER settings are spread over the general and node-specific config files
        fullconfig = cfg.copy()
        fullconfig.update(self.config)
        if cfg['mode'] == 'bruteforce':
            cmd = ("amber -opencl_platform {opencl_platform} -opencl_device {opencl_device} -device_name {device_name} -padding_file {amber_conf_dir}/padding.conf"
                   "-zapped_channels {amber_conf_dir}/zapped_channels.conf -integration_steps {amber_conf_dir}/integration_steps.conf -dedisperion_file"
                   "{amber_conf_dir}/dedispersion.conf -integration_file {amber_conf_dir}/integration.conf -snr_file {amber_conf_dir}/snr.conf -dms {num_dm}"
                   " -dm_first {dm_first} -dm_step {dm_step} -threshold {snrmin} -output {output_prefix} &").format(**fullconfig)
        elif cfg['mode'] == 'subband':
            self.log("ERROR: Subbanding mode not yet supported")
            exit()
        self.log(cmd)
        os.system(cmd)


    def survey(self):
        self.amber()
        self.dadafilterbank()


if __name__ == '__main__':
    # first argument is the config file
    # no need for something like argsparse as this script should always be called
    # from the master node, i.e. the commandline format is fixed
    conf_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), sys.argv[1])

    # TEMPORARY: copy config files from master node
    os.system("scp -r arts041:ARTS-obs/nodes $HOME/ARTS-obs/")

    # load config
    with open(conf_file, 'r') as f:
        config = yaml.load(f)

    # start observation
    Survey(config)
    