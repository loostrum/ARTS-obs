#!/usr/bin/env python

import os
import sys
import socket
import argparse
import errno
import signal
from astropy.time import Time, TimeDelta

import matplotlib as mpl
mpl.use('agg')
import matplotlib.pyplot as plt
import numpy as np
import yaml
import filterbank


DEBUG = True

def clean_exit(sig, stack):
    """
    Prints exit message and quits program
    """
    print "Received signal: {}. Exiting\n".format(sig)
    sys.exit(1)


def plot_histogram(obs_config):
    """
    Creates a histogram of sample values
    """

    filfile = "{output_dir}/filterbank/CB{beam:02d}.fil".format(**obs_config)

    fil_obj = filterbank.FilterbankFile(filfile)
    nspec = fil_obj.nspec
    header = fil_obj.header
    dt = header['tsamp'] # delta_t in seconds

    samp_per_block = int(1.024/dt)
    nsamp = obs_config['nbatch'] * samp_per_block

    start_samp = nspec-nsamp

    # read last N blocks
    if nspec <= nsamp:
        if DEBUG:
            print "Not enough spectra in file to create plot"
            return
    data = fil_obj.get_spectra(start_samp, nsamp)

    # create and save histogram
    # 256 bins because we have 8-bit unsigned data
    bins = np.arange(0, 256)
    fig, ax = plt.subplots()
    ax.hist(data.data.flatten(), bins=bins, color='k')
    ax.set_xlabel('Sample value')
    ax.set_ylabel('Count')
    ax.set_yscale('log')
    beam = "{beam:02d}".format(**obs_config)
    obs = obs_config['output_dir'].split('/')[-1]
    time_of_data = "{:.0f}".format((nspec-0.5*nsamp) * dt)
    ax.set_title("CB{} - {} @ {}s".format(beam, obs, time_of_data))
    fig_name = "{webdir}/{hostname}_histogram.png".format(**obs_config)
    try:
        fig.savefig(fig_name, bbox_inches='tight')
    except IOError:
        if DEBUG:
            print "Could not save figure"
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate raw data plots for monitoring")
    parser.add_argument('--configdir', type=str, help="Directory with node configurations",
                        required=True)
    parser.add_argument('--nbatch', type=int, default=5, help="Number of batch to generate stats from "
                        "(Default: %(default)s)")
    parser.add_argument('--webdir', type=str, default='/home/arts/public_html/monitoring/',
                        help="Directory to store plots in "
                        "(Default: %(default)s)")

    args = parser.parse_args()
    config = vars(args)

    print "{}: Starting noise plotter".format(Time.now())

    # create output dir
    try:
        os.makedirs(args.webdir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            print "Cannot access output directory: {}".format(args.webdir)
            sys.exit(1)

    # set hostname and beam number
    hostname = socket.gethostname()
    beam = int(hostname[5:7]) - 1

    config['hostname'] =  hostname
    conf_file = "{configdir}/CB{beam:02d}.yaml".format(beam=beam, **config)

    if DEBUG:
        print "Config file: {}".format(conf_file)

    # Exit on sigterm
    signal.signal(signal.SIGTERM, clean_exit)

    # find obs config
    if not os.path.isfile(conf_file):
        # wait for next obs
        if DEBUG:
            print "Config file not found: {}".format(conf_file)
        sys.exit()

    # load obs config
    with open(conf_file, 'r') as f:
        obs_config = yaml.load(f)
    # add general config
    obs_config.update(config)
    # check end time
    obs_end = Time(obs_config['endtime'], scale='utc')
    if Time.now() >= obs_end:
        # Obs is already over
        if DEBUG:
            print "End time has passed, waiting for new obs"
        sys.exit()

    # check start time (at least 5s after start time so we have some data)
    obs_start = Time(float(obs_config['startpacket'])/781250., format='unix')
    if Time.now() < obs_start + TimeDelta(5, format='sec'):
        # New obs hasn't started yet
        if DEBUG:
            print "Observation not yet running"
        sys.exit()

    # Checks done - at this point an observation should be running
    if DEBUG:
        print "Observation running - calling plot_histogram"
    plot_histogram(obs_config)

