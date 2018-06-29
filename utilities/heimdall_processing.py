#!/usr/bin/env python
#
# Process ARTS filterbank files
# -- Run Heimdall
# -- Group resulting candidate files and extract dedispersed data (triggers.py)
# -- Plot candidates (plotter.py)
# -- merge into one pdf per compound beam (bash)


import os
import sys
import socket
import argparse
import glob

import yaml

CONFIG = "config.yaml"
SC = "sc4"
RESULTDIR = "@HOME@/observations/heimdall/{date}/{datetimesource}"


class Processing(object):

    def __init__(self, args):
        # load observation config
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', CONFIG)
        with open(filename, 'r') as f:
            config = yaml.load(f)[SC]
        home = os.path.expanduser('~')
        for key, item in config.items():
            if isinstance(item, str):
                config[key] = item.replace('@HOME@', home).format(date=args.date, datetimesource=args.obs)
        # add args to config
        config.update(vars(args))
        config['datetimesource'] = args.obs
        self.config = config

        # set up relevant directories
        if not os.path.isdir(self.config['log_dir']):
            print "ERROR: log dir {log_dir} does not exist".format(**self.config)
            exit()

        # get dadafilterbank logs, as we want to run processing on filterbank
        dadafilterbank_logs = glob.glob('{log_dir}/dadafilterbank.*'.format(**self.config))
        if len(dadafilterbank_logs) == 0:
            print "ERROR: this observation did not run dadafilterbank"
            exit()

        # create directory to store results in
        self.config['result_dir'] = RESULTDIR.replace("@HOME@", home).format(**self.config)
        try:
            os.makedirs(self.config['result_dir'])
        except OSError:
            # Directory already exists
            pass

        # get used beams from dadafilterbank logs
        CBs = sorted([x.split('.')[-1] for x in dadafilterbank_logs])
        print "Found {} CBs:".format(len(CBs))
        for CB in CBs:
            sys.stdout.write(CB+' ')
        sys.stdout.write('\n')

        # process each CB
        for CB in CBs:
            self.process(CB)
        sys.stdout.write("Processing started\n")
        sys.stdout.flush()

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
        else:
            ssh_cmd = "ssh {} '{}'".format(hostname, command)
        sys.stdout.write("Executing \"{}\"\n".format(ssh_cmd))
        os.system(ssh_cmd)

    def process(self, CB):
        """Process filterbank on node specified by CB
            CB: nr of CB to process (int)
        """

        # node number, keep in mind 1-based indexing for nodes
        CB = int(CB)
        node = CB + 1

        localconfig = self.config.copy()
        localconfig['filfile'] = "{output_dir}/filterbank/CB{CB:02d}.fil".format(CB=CB, **self.config)
        localconfig['heimdall_dir'] = "{result_dir}/CB{CB:02d}".format(CB=CB, **self.config)
        try:
            os.makedirs(localconfig['heimdall_dir'] )
        except OSError:
            # Directory already exists
            pass

        # Heimdall command line
        command = ("(heimdall -v -f {filfile} -dm 0 {dmmax} -gpu_id 0 -output_dir {heimdall_dir}; "
                   "cd {heimdall_dir}; cat *cand > CB{CB:02d}.cand; mkdir plots; "
                   "echo python $HOME/software/arts-analysis/triggers.py --dm_min 10 --dm_max 5000 --sig_thresh {snrmin} "
                   " --ndm 1 --save_data hdf5 --ntrig 1000000000 --nfreq_plot 32 --ntime_plot 250 --cmap viridis "
                   " --mk_plot {filfile} CB{CB:02d}.cand) > {result_dir}/CB{CB:02d}.log").format(CB=CB, **localconfig)

        self.run_on_node(node, command, background=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Offline processing of ARTS data with Heimdall")
    # observation info
    parser.add_argument("--date", '-d', type=str, help="Observation date, e.g. 20180101", required=True)
    parser.add_argument("--obs", type=str, help="Observation name, e.g. 2018-01-01-00:00:00.B0000+00", required=True)
    # Heimdall settings
    parser.add_argument("--dmmax", type=float, help="Maximum DM, (default: 5000)", default=5000)
    parser.add_argument("--snrmin", type=int, help="Minimum S/N, (default: 8)", default=8)

    args = parser.parse_args()

    # check on which node we are running
    hostname = socket.gethostname()
    if not hostname == "arts041":
        print "ERROR: This script should be run from the master node (arts041)"
        exit()

    Processing(args)
