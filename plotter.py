#!/usr/bin/env python
#
# Plot triggers output by the ML classifier

import sys

import numpy as np
import h5py
import matplotlib
matplotlib.use('pdf')
import matplotlib.pyplot as plt


if __name__ == '__main__':
    # input hdf5 file
    fname = sys.argv[1]

    # read dataset 
    with h5py.File(fname, 'r') as f:
        data_frb_candidate = f['data_frb_candidate'][:]
        probability = f['probability'][:]
        params = f['params'][:]  # snr, DM, boxcar width, arrival time

    for i, cand in enumerate(data_frb_candidate):
        data_freq_time = cand[:, :, 0]
        prob = probability[i]
        snr, dm, boxcar_width, t0 = params[i]

        times = np.arange(data_freq_time.shape[1]) * 40.96E-3  # tsamp in ms
        freqs = np.arange(data_freq_time.shape[0]) * 0.1953125 + 1250.09765625

        fig, (ax1, ax2) = plt.subplots(nrows=2, sharex=True, gridspec_kw=dict(height_ratios=[1, 2]))

        # timeseries
        ax1.plot(times, np.average(data_freq_time, axis=0), c='k')
        ax1.set_xlabel('Time (ms)')
        ax1.set_ylabel('S/N')
        # waterfall plot
        # scaling: std = 1, median=0
        extent = [times[0], times[-1], freqs[0], freq[-1]]
        ax2.imshow(data_freq_time, cmap='viridis', vmin=-3, vmax=3, interpolation='nearest', aspect='equal', origin='lower', extent=extent)
        ax2.set_xlabel('Time (ms)')
        ax2.set_ylabel('Freq (Mhz)')
        fig.suptitle("p: {:.1f}, S/N: {:.0f}, DM: {:.2f}, T0: {:.2f}".format(prob, snr, dm, t0))
        plt.savefig("plots/cand_{:04d}_snr{:.0f}_dm{:.0f}.pdf".format(i, snr, dm))
        plt.close(fig)
