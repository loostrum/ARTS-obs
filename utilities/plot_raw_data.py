#!/usr/bin/env python

import os
import sys
import socket
import argparse
import errno
import signal
from time import sleep
from astropy.time import Time, TimeDelta

import matplotlib as mpl
mpl.use('pdf')
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
    beam = "{beam:02d}".format(**obs_config)
    obs = obs_config['output_dir'].split('/')[-1]
    time_of_data = "{:.1f}".format((nspec-0.5*nsamp) * dt)
    ax.set_title("CB{} - {} @ {}s".format(beam, obs, time_of_data))
    fig_name = "{webdir}/{hostname}.pdf".format(**obs_config)
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
    parser.add_argument('--interval', type=float, default=10, help="Seconds between creating plots "
                        "(Default: %(default)s)")
    parser.add_argument('--obsinterval', type=float, default=60, help="Seconds between checking for new observations "
                        "(Default: %(default)s)")
    parser.add_argument('--webdir', type=str, default='/home/arts/public_html/monitoring/',
                        help="Directory to store plots in "
                        "(Default: %(default)s)")

    args = parser.parse_args()
    config = vars(args)

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

    while True:
        # find obs config
        if not os.path.isfile(conf_file):
            # wait for next obs
            if DEBUG:
                print "Config file not found: {}".format(conf_file)
            sleep(args.obsinterval)
            continue
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
            sleep(args.obsinterval)
            continue
        # check start time (at least 5s after start time so we have some data)
        obs_start = Time(float(obs_config['startpacket'])/781250., format='unix')
        if Time.now() < obs_start + TimeDelta(5, format='sec'):
            # New obs hasn't started yet
            if DEBUG:
                print "Observation not yet running"
                sleep(args.interval)
                continue

        # Checks done - at this point an observation should be running
        if DEBUG:
            print "Observation running - calling plot_histogram"
        plot_histogram(obs_config)
        # sleep until next iteration
        sleep(args.interval)

    

    fil_obj = filterbank.FilterbankFile(fname)
    nspec = fil_obj.nspec
    header = fil_obj.header
    dt = header['tsamp'] # delta_t in seconds
    fch1 = header['fch1']
    nchans = header['nchans']
    foff = header['foff']

    samp_per_block = int(1.024/dt)
    nsamp = 10 * samp_per_block

    downsamp = max(int(desired_dt // dt), 1)

    # read first 10 blocks
    data = fil_obj.get_spectra(0, nsamp)
    data.dedisperse(dm=dm)
    # subband to 1 per beamlet
    data.subband(nsub=nsub)
    data.downsample(downsamp)

    timeseries = data.data.sum(axis=0)

    foff *= nchans/nsub
    fch_f = fch1 + foff * nsub
    freq = np.linspace(fch1, fch_f, nsub)
    times = np.arange(0, len(timeseries)) * dt * downsamp

    print "Time resolution: ", dt*downsamp
    print "Freq resolution: ", abs(foff)

    # Fig
    fig, (ax1, ax2) = plt.subplots(nrows=2, gridspec_kw=dict(height_ratios=[1, 2]), sharex=True)
    #ax1.plot(times, timeseries, c='k')
    ax1.plot(range(len(timeseries)), timeseries, c='k')
    #extent = [times[0], times[-1], freq[-1], freq[0]]
    extent = [0, len(times), 0, len(freq)]
    ax2.imshow(data.data, extent=extent, origin='upper', cmap='viridis', interpolation=None, aspect='auto')

    ax1.set_ylabel('Intensity (a.u.)')
    #ax2.set_xlabel('Time (s)')
    #ax2.set_ylabel('Frequency (MHz)')
    ax2.set_xlabel('Sample ({})'.format(dt*downsamp))
    ax2.set_ylabel('Channel ({})'.format(abs(foff)))

    plt.show()
    exit()

    # full timeseries
    downsamp = int((1.024//dt))
    full_ts = []
    chunksize = samp_per_block * 10
    imax = int(nspec // chunksize) + 1
    i = 0
    for i in tqdm(range(imax+1)):
        data = fil_obj.get_spectra(i*chunksize, chunksize)
        if len(data.data[0]) == 0:
            print "Breaking at iteration", i
            break
        data.downsample(downsamp)
        ts = data.data.sum(axis=0)
        full_ts.append(ts)
        i += 1

    full_ts = np.concatenate(full_ts, axis=-1)
    times = np.arange(0, len(full_ts)) * dt * downsamp
    
    plt.figure()
    plt.plot(times, full_ts, c='k')

    plt.show()
