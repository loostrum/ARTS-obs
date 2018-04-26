#!/usr/bin/env python
#
# Process filterbanks with AMBER, and process results in the usual way
# Uses the log folder to find which CBs were used

import os
import sys
import shutil
import socket
import argparse
import glob

import yaml

CONFIG = "config.yaml"
AMBERCONFIG = "amber.yaml"
MODE = "subband"

class OfflineProcessing(object):

    def __init__(self, args):
        self.args = args
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', CONFIG)
        with open(filename, 'r') as f:
            config = yaml.load(f)
            science_case = "sc{}".format(args.sc)
        self.config = config[science_case]
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', AMBERCONFIG)
        with open(filename, 'r') as f:
            amber_config = yaml.load(f)
        amber_config = amber_config[MODE]
        amber_config['amber_conf_dir'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'amber_conf')
        amber_config['snrmin'] = args.snrmin
        self.amber_config = amber_config


        # get log dir and check whether it exists
        log_dir = self.config['log_dir'].format(date=args.date, datetimesource=args.obs)
        if not os.path.isdir(log_dir):
            print "ERROR: log dir {log_dir} does not exist".format(log_dir=log_dir)
            exit()

        # get dadafilterbank logs, as we want to run AMBER on filterbank
        dadafilterbank_logs = glob.glob('{}/dadafilterbank.*'.format(log_dir))
        if len(dadafilterbank_logs) == 0:
            print "ERROR: this observation did not run dadafilterbank"
            exit()

        # get used beams from dadafilterbank logs
        CBs = sorted([x[-2:] for x in dadafilterbank_logs])
        print "Found {} CBs:".format(len(CBs))
        for CB in CBs:
            sys.stdout.write(CB+' ')
        sys.stdout.write('\n')
        sys.stdout.flush()

        # clear old results
        master_dir = self.config['master_dir'].format(date=args.date, datetimesource=args.obs)
        amber_dir = self.config['amber_dir'].format(date=args.date, datetimesource=args.obs)
        os.system("rm -f {master_dir}/CB*".format(master_dir=master_dir))
        shutil.rmtree(amber_dir)
        os.makedirs(amber_dir)
        # process each CB
        for CB in CBs:
            self.start_processing(CB)
        print "Processing started"

        # start emailer
        if args.email:
            print "Starting emailer"
            emailer = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'emailer.py')
            cmd = "python {emailer} {master_dir} \"{beams}\"".format(emailer=emailer, master_dir=master_dir, 
                                                                beams=str(CBs))
            print cmd
            os.system(cmd)


    def run_on_node(self, node, command, background=False):
        """Run command on an ARTS node. Assumes ssh keys have been set up
            node: nr of node (string or int)
            command: command to run
            background: whether to run ssh in the background
        """

        # if node is given as number, change to hostname
        if isinstance(node, int):
            hostname = "arts0{:02d}".format(node)
        else:
            hostname = node

        if background:
            ssh_cmd = "ssh {} '{}' &".format(hostname, command)
            #ssh_cmd = "ssh {} 'source $HOME/python/bin/activate; {}' &".format(hostname, command)
        else:
            ssh_cmd = "ssh {} '{}'".format(hostname, command)
            #ssh_cmd = "ssh {} 'source $HOME/python/bin/activate; {}' &".format(hostname, command)
        print "Executing \"{}\"".format(ssh_cmd)
        os.system(ssh_cmd)


    def start_processing(self, CB):
        """
        Processing a full observation on a node determined by CB number
            CB: nr of CB to processs
        """
        # make sure CB is an int
        CB = int(CB)
        hostname = "arts0{:02d}".format(CB+1)

        # setup the commands to execute
        # filterbank file
        filfile = "{output_dir}/filterbank/CB{CB:02d}.fil".format(CB=CB, **self.config).format(date=args.date, datetimesource=args.obs)
        # header size (bash command to be executed on node): assumed to be remainder of division by 25000 * 1536 (for sc4)
        get_sizes = ("file_size=$(du -b {filfile} | awk '{{print $1}}'); "
                     "hdr_size=$(($file_size % $(({pagesize}*{nchan})))); "
                     "nbatch=$(($(($file_size - $hdr_size)) / $(({pagesize}*{nchan}))))").format(filfile=filfile, **self.config)
        # amber command line
        amber = ['spack unload amber', 'export PATH=$HOME/software/install/bin:$PATH', 
                  'export LD_LIBRARY_PATH=$HOME/software/install/lib:$HOME/software/install/lib64:$LD_LIBRARY_PATH']
        for ind in range(len(self.amber_config['opencl_device'])):
                # make dict with fullconfig, because AMBER settings are spread over the general and node-specific config files
                fullconfig = self.amber_config.copy()
                fullconfig.update(self.config)
                fullconfig['CB'] = CB
                fullconfig['output_prefix'] = "{amber_dir}/CB{CB:02}".format(**fullconfig).format(date=args.date, datetimesource=args.obs)
                fullconfig['filfile'] = filfile
                fullconfig['chan_width'] = float(fullconfig['bw']) / fullconfig['nchan']
                fullconfig['min_freq'] = fullconfig['freq'] - float(fullconfig['bw'])/2 + fullconfig['chan_width'] / 2
                # set the settings for this GPU
                for key in ['dm_first', 'dm_step', 'num_dm', 'opencl_device', 'device_name', 'subbands', 'subbanding_dm_first', 'subbanding_dm_step', 'subbanding_dms']:
                    fullconfig[key] = self.amber_config[key][ind]

                cmd = ("amber -opencl_platform {opencl_platform} -opencl_device {opencl_device} -device_name {device_name} -padding_file {amber_conf_dir}/padding.conf"
                       " -zapped_channels {amber_conf_dir}/zapped_channels.conf -integration_steps {amber_conf_dir}/integration_steps.conf -subband_dedispersion"
                       " -dedispersion_stepone_file {amber_conf_dir}/dedispersion_stepone.conf -dedispersion_steptwo_file {amber_conf_dir}/dedispersion_steptwo.conf"
                       " -integration_file {amber_conf_dir}/integration.conf -snr_file {amber_conf_dir}/snr.conf -dms {num_dm} -dm_first {dm_first} -dm_step {dm_step}"
                       " -subbands {subbands} -subbanding_dms {subbanding_dms} -subbanding_dm_first {subbanding_dm_first} -subbanding_dm_step {subbanding_dm_step}"
                       " -threshold {snrmin} -output {output_prefix}_step{ind} -beams 1 -synthesized_beams 1"
                       " -sigproc -header $hdr_size -data {filfile} -channels {nchan} -min_freq {min_freq} -channel_bandwidth {chan_width} -samples {pagesize}"
                       " -sampling_time {tsamp} -batches $nbatch -stream 2>&1 > {log_dir}/amber_{ind}.{CB:02d} &").format(ind=ind+1, **fullconfig).format(date=args.date, 
                                                                                                                                        datetimesource=args.obs)
                amber.append(cmd)
        amber.append('wait')
        amber = ' \n'.join(amber)

        # trigger processsing
        kwargs = self.amber_config.copy()
        kwargs['output_dir'] = self.config['output_dir'].format(date=args.date, datetimesource=args.obs)
        kwargs['master_dir'] = self.config['master_dir'].format(date=args.date, datetimesource=args.obs)
        kwargs['amber_dir'] = self.config['amber_dir'].format(date=args.date, datetimesource=args.obs)
        kwargs['script_dir'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')


        prepare = "rm -rf {output_dir}/triggers\nmkdir -p {output_dir}/triggers".format(**kwargs)
        process = ("{script_dir}/process_triggers.sh {output_dir}/triggers {output_dir}/filterbank/CB{CB:02d}.fil"
                    " {amber_dir}/CB{CB:02d} {master_dir} {snrmin} {CB:02d}").format(CB=CB, **kwargs)

        # create script and execute
        cmd = '\n'.join([get_sizes, amber, prepare, process])
        fname = '/home/oostrum/offline/CB{:02d}.sh'.format(CB)
        with open(fname, 'w') as f:
            f.writelines(cmd)

        self.run_on_node(hostname, "bash {}".format(fname), background=True)



if __name__ == '__main__':
    # check on which node we are running
    hostname = socket.gethostname()
    if not hostname == "arts041":
        print "ERROR: This script should be run from the master node (arts041)"
        exit()

    parser = argparse.ArgumentParser(description="Offline processing of ARTS data")
    # observation info
    parser.add_argument("--date", type=str, help="Observation date, e.g. 20180101")
    parser.add_argument("--obs", type=str, help="Observation name, e.g. 2018-01-01-00:00:00.B0000+00")
    # AMBER
    parser.add_argument("--snrmin", type=int, help="Minimum S/N, (default: 10)", default=10)
    # science case
    parser.add_argument("--sc", type=int, help="Science case, 3 or 4. (default: 4)", default=4)
    # email setting
    parser.add_argument("--email", action='store_true', help="Email triggers (Default: false)")

    args = parser.parse_args()
    if not args.sc in [3, 4]:
        print "ERROR: Science case should be 3 or 4"
        exit()

    OfflineProcessing(args)




