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

NUMTHREADS = 40


class Survey(object):
    """Start a survey mode observation on ARTS. This class runs the relevant commands on the current node
    """

    def __init__(self, config):
        """
        config: dict with settings, as generated by the master script
        """
        # set hostname and config
        self.hostname = socket.gethostname()
        self.config = config
        
        # how long to sleep between commands
        waittime = 0.5

        # check CB
        expected_CB = int(self.hostname[5:7]) - 1
        if not self.config['beam'] == expected_CB:
            self.log("WARNING: Requested to record CB {}, expected CB {}".format(self.config['beam'], expected_CB))        

        # create directory for log files
        os.system("mkdir -p {}".format(self.config['log_dir']))

        # start the programmes
        # remove running ringbuffers, AMBER, etc.
        self.clean()
        sleep(2*waittime)
        # create ringbuffer
        self.ringbuffer()
        sleep(waittime)
        # start readers depending on observing mode
        if self.config['obs_mode'] == 'scrub':
            self.scrub()
        elif self.config['obs_mode'] == 'dump':
            self.dump()
        elif self.config['obs_mode'] == 'fil':
            self.dadafilterbank()
        elif self.config['obs_mode'] == 'fits':
            self.dadafits()
        elif self.config['obs_mode'] == 'amber':
            self.amber()
        elif self.config['obs_mode'] == 'survey':
            self.survey()
        sleep(waittime)
        # start fill ringbuffer (operations) or read from disk (debug)
        if self.config['debug']:
            self.diskdb()
        elif self.config['usemac']:
            self.fill_ringbuffer(reorder=True)
        else:
            self.fill_ringbuffer()
        sleep(waittime)
        # Everything has been started
        self.log("Everything started")
        # flush stdout
        sys.stdout.flush()
        # Add dataproducts to atdb
        if self.config['atdb'] and self.config['obs_mode'] in ('survey', 'fits'):
            self.add_dataproducts()
        # test pulsar command
        if self.config['pulsar']:
            # MAC: CB00 = central beam
            # no MAC: CB21 = central beam
            if (self.config['usemac'] and self.config['beam'] == 0) or ((not self.config['usemac']) and self.config['beam'] == 21):
                # this is the central beam
                print "Will fold pulsar on CB{:02d}".format(self.config['beam'])
                fold_script = "{script_dir}/utilities/fold_pulsar.py".format(script_dir=os.path.dirname(os.path.realpath(__file__)), **self.config)
                cmd = "(sleepuntil_utc {endtime}; sleep 10; {fold_script} --obs_dir {output_dir}) &".format(fold_script=fold_script, **self.config)
                self.log(cmd)
                sys.stdout.flush()
                os.system(cmd)

        # proc trigger command
        if self.config['proctrigger']:
            cmd = "mkdir -p {output_dir}/triggers".format(**self.config)
            os.system(cmd)
            self.log("Waiting for finish, then processing triggers")
            if self.config['debug']:
                prog = 'dada_diskdb'
            else:
                prog = 'fill_ringbuffer'
            cmd = "sleep 1; pid=$(pgrep {prog}); tail --pid=$pid -f /dev/null; sleep 5; " \
                  "{script_dir}/process_triggers.sh {output_dir}/triggers {output_dir}/filterbank/CB{beam:02d}.fil " \
                  "{amber_dir}/CB{beam:02d} {master_dir} " \
                  "{snrmin_processing} {snrmin_processing_local} {dmmin} {dmmax} {beam:02d} {duration}".format(prog=prog, 
                                                          script_dir=os.path.dirname(os.path.realpath(__file__)),
                                                          **self.config)
            self.log(cmd)
            sys.stdout.flush()
            os.system(cmd)

    def log(self, message):
        """
        Log a message. Prints the hostname, then the message
        """
        print "{}: {}".format(self.hostname, message)

    def add_dataproducts(self):
        """
        Add dataproducts to ATDB
        """
        fits_dir = "{output_dir}/fits/CB{beam:02d}".format(**self.config)
        # IAB mode: one dataproduct
        if self.config['ntabs'] == 1:
            fname = "ARTS{taskid}_CB{beam:02d}.fits".format(**self.config)
            # symlink the fits file
            os.symlink("{fits_dir}/tabA.fits".format(fits_dir=fits_dir), "{fits_dir}/{fname}".format(fits_dir=fits_dir, fname=fname))
            # add the data products
            cmd = "source /home/arts/atdb_client/env2/bin/activate; atdb_service -o add_dataproduct --taskid {taskid} " \
                  " --node {hostname} --data_dir {fits_dir} --filename {fname}" \
                  " --atdb_host prod".format(hostname=self.hostname, fname=fname, fits_dir=fits_dir, **self.config)
            self.log(cmd)
            sys.stdout.flush()
            #os.system(cmd)

        # TAB mode: multiple dataproducts
        else:
            mapping = {1:'A', 2:'B', 3:'C', 4:'D', 5:'E', 6:'F', 7:'G', 8:'H', 9:'I', 10:'J', 11:'K', 12:'L'}
            for tab in range(1, self.config['ntabs']+1):
                fname = "ARTS{taskid}_CB{beam:02d}_TAB{tab:02d}.fits".format(tab=tab, **self.config)
                # symlink the fits file
                os.symlink("{fits_dir}/tab{letter}.fits".format(fits_dir=fits_dir, letter=mapping[tab]), 
                            "{fits_dir}/{fname}".format(fits_dir=fits_dir, fname=fname))
                # add the data products
                cmd = "source /home/arts/atdb_client/env2/bin/activate; atdb_service -o add_dataproduct --taskid {taskid} " \
                      " --node {hostname} --data_dir {fits_dir} --filename {fname}" \
                      " --atdb_host prod".format(hostname=self.hostname, fname=fname, fits_dir=fits_dir, **self.config)
                self.log(cmd)
                sys.stdout.flush()
                #os.system(cmd)

    def clean(self):
        self.log("Removing old ringbuffers")
        cmd = "dada_db -d -k {dadakey} 2>/dev/null; pkill fill_ringbuffer; pkill amber".format(**self.config)
        self.log(cmd)
        os.system(cmd)

    def ringbuffer(self):
        self.log("Starting ringbuffers")
        cpu = self.config['affinity']['dada_db_i']
        cmd = "taskset -c {cpu} dada_db -a {hdr_size} -k {dadakey} -b {buffersize} -n {nbuffer} -p " \
              "-r {nreader} &".format(cpu=cpu, **self.config)
        self.log(cmd)
        os.system(cmd)

    def fill_ringbuffer(self, reorder=False):
        self.log("Starting fill_ringbuffer")
        cpu = self.config['affinity']['fill_ringbuffer_i']
        if reorder:
            cmd = ("taskset -c {cpu} fill_ringbuffer -f -k {dadakey} -s {startpacket} -d {duration}"
                   " -p {network_port} -h {header} -l {log_dir}/fill_ringbuffer.{beam:02d} &").format(cpu=cpu,
                                                                                                      **self.config)
        else:
            cmd = ("taskset -c {cpu} fill_ringbuffer -k {dadakey} -s {startpacket} -d {duration}"
                   " -p {network_port} -h {header} -l {log_dir}/fill_ringbuffer.{beam:02d} &").format(cpu=cpu,
                                                                                                      **self.config)
        self.log(cmd)
        os.system(cmd)

    def diskdb(self):
        self.log("Starting dada_diskdb")
        cpu = self.config['affinity']['fill_ringbuffer_i']
        files = os.listdir(self.config['dada_dir'])
        files.sort()
        arg = " -f {dada_dir}/".format(**self.config) + " -f {dada_dir}/".format(**self.config).join(files)
        cmd = "taskset -c {cpu} dada_diskdb -k {dadakey} {arg} &".format(cpu=cpu, arg=arg, **self.config)
        self.log(cmd)
        os.system(cmd)

    def scrub(self):
        self.log("Starting dada_dbscrubber")
        cmd = "dada_dbscrubber -k {dadakey} > {log_dir}/dada_dbscrubber.{beam:02d} &".format(**self.config)
        self.log(cmd)
        os.system(cmd)

    def dump(self):
        self.log("Starting dada_dbdisk")
        cpu = self.config['affinity']['dada_dbdisk_i']
        output_dir = os.path.join(self.config['output_dir'], 'dada')
        os.system("mkdir -p {}".format(output_dir))
        cmd = "taskset -c {cpu} dada_dbdisk -k {dadakey} -D {output_prefix} " \
              "> {log_dir}/dada_dbdisk.{beam:02d} &".format(cpu=cpu, output_prefix=output_dir, **self.config)
        self.log(cmd)
        os.system(cmd)

    def dadafilterbank(self):
        self.log("Starting dadafilterbank")
        cpu = self.config['affinity']['dadafilterbank']
        output_dir = os.path.join(self.config['output_dir'], 'filterbank')
        os.system("mkdir -p {}".format(output_dir))
        output_prefix = os.path.join(output_dir, 'CB{:02d}'.format(self.config['beam']))
        cmd = "export OMP_NUM_THREADS={threads}; taskset -c {cpu} dadafilterbank -k {dadakey} -n {output_prefix} " \
              "-l {log_dir}/dadafilterbank.{beam:02d} &".format(cpu=cpu, output_prefix=output_prefix,
                                                                threads=NUMTHREADS, **self.config)
        self.log(cmd)
        os.system(cmd)

    def dadafits(self):
        self.log("Starting dadafits")
        cpu = self.config['affinity']['dadafits']
        output_dir = os.path.join(self.config['output_dir'], 'fits', 'CB{:02d}'.format(self.config['beam']))
        os.system("mkdir -p {}".format(output_dir))
        cmd = "taskset -c {cpu} dadafits -k {dadakey} -l {log_dir}/dadafits.{beam:02d} -t {fits_templates} -d " \
              "{output_fits} &".format(cpu=cpu, output_fits=output_dir, **self.config)
        self.log(cmd)
        os.system(cmd)

    def amber(self):
        self.log("Starting AMBER")
        os.system("mkdir -p {}".format(self.config['amber_dir']))
        # load AMBER config
        with open(self.config['amber_config'], 'r') as f:
            cfg = yaml.load(f)
        # load config for specified dedispersion mode
        ambercfg = cfg[self.config['amber_mode']]
        # add output prefix
        ambercfg['output_prefix'] = os.path.join(self.config['amber_dir'], 'CB{:02d}'.format(self.config['beam']))

        if self.config['amber_mode'] == 'bruteforce':
            self.log("ERROR: amber bruteforce mode no longer supported")
            exit(1)
        elif self.config['amber_mode'] == 'subband':
            self.log("Starting amber in subband mode")
            # loop over the amber configs for the GPUs
            for ind in range(len(ambercfg['opencl_device'])):
                cpu = self.config['affinity']['amber'][ind]
                # make dict with fullconfig, because AMBER settings are spread over the general
                # and node-specific config files
                fullconfig = ambercfg.copy()
                fullconfig.update(self.config)
                # set the settings for this GPU
                for key in ['dm_first', 'dm_step', 'num_dm', 'opencl_device', 'device_name', 'subbands',
                            'subbanding_dm_first', 'subbanding_dm_step', 'subbanding_dms',
                           'downsamp', 'integration_file']:
                    fullconfig[key] = ambercfg[key][ind]

                # Set downsampling flag if downsampling is used
                if fullconfig['downsamp'] > 1:
                    fullconfig['downsampling_cmd'] = '-downsampling'
                else:
                    fullconfig['downsampling_cmd'] = ''

                cmd = (" taskset -c {cpu} amber -sync -print -opencl_platform {opencl_platform}"
                       " -opencl_device {opencl_device} -device_name {device_name}"
                       " -padding_file {amber_conf_dir}/padding.conf"
                       " -zapped_channels {amber_conf_dir}/zapped_channels.conf"
                       " -integration_steps {amber_conf_dir}/{integration_file} -subband_dedispersion"
                       " -dedispersion_stepone_file {amber_conf_dir}/dedispersion_stepone.conf"
                       " -dedispersion_steptwo_file {amber_conf_dir}/dedispersion_steptwo.conf"
                       " -integration_file {amber_conf_dir}/integration.conf -snr_file {amber_conf_dir}/snr.conf"
                       " -dms {num_dm} -dm_first {dm_first} -dm_step {dm_step}"
                       " -subbands {subbands} -subbanding_dms {subbanding_dms}"
                       " -subbanding_dm_first {subbanding_dm_first}"
                       " -subbanding_dm_step {subbanding_dm_step}"
                       " -snr_momad -max_file {amber_conf_dir}/max.conf"
                       " -mom_stepone_file {amber_conf_dir}/mom_stepone.conf"
                       " -mom_steptwo_file {amber_conf_dir}/mom_steptwo.conf -momad_file {amber_conf_dir}/momad.conf"
                       " {downsampling_cmd} -downsampling_configuration {amber_conf_dir}/downsampling.conf -downsampling_factor {downsamp}"
                       " -threshold {snrmin_amber} -output {output_prefix}_step{ind} -beams {ntabs} -synthesized_beams {nsynbeams}"
                       " -dada -dada_key {dadakey} -batches {nbatch} -compact_results"
                       " 2>&1 > {log_dir}/amber_{ind}.{beam:02d} &").format(cpu=cpu, ind=ind+1, **fullconfig)
                self.log(cmd)
                os.system(cmd)

    def survey(self):
        self.amber()
        self.dadafilterbank()
        self.dadafits()


if __name__ == '__main__':
    # first argument is the config file
    # no need for something like argparse as this script should always be called
    # from the master node, i.e. the commandline format is fixed
    conf_file = os.path.join(os.path.realpath(os.path.dirname(__file__)), sys.argv[1])

    # load config
    with open(conf_file, 'r') as f:
        config = yaml.load(f)

    # start observation
    Survey(config)
