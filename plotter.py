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
    cb = int(sys.argv[2])

    # read dataset 
    with h5py.File(fname, 'r') as f:
        data_frb_candidate = f['data_frb_candidate'][:]
        probability = f['probability'][:]
        params = f['params'][:]  # snr, DM, boxcar width, arrival time

    for i, cand in enumerate(data_frb_candidate):
        data_freq_time = cand[:, :, 0]
        prob = probability[i]
        snr, dm, bin_width, t0 = params[i]

        times = np.arange(data_freq_time.shape[1]) * bin_width * 1E3  # ms
        fmin = 1220.09765625
        fmax = 1519.90234375
        freqs = np.linspace(fmin, fmax, data_freq_time.shape[0])

        fig, (ax1, ax2) = plt.subplots(nrows=2, sharex=True, gridspec_kw=dict(height_ratios=[1, 2]))

        # timeseries
        ax1.plot(times, np.sum(data_freq_time, axis=0)/np.sqrt(data_freq_time.shape[0]), c='k')
        ax1.set_ylabel('S/N')
        # add what a DM=0 signal would look like
        DM0_delays = dm * 4.15E6 * (fmin**-2 - freqs**-2)
        ax2.plot(DM0_delays, freqs, c='r', lw='2')
        # waterfall plot
        # scaling: std = 1, median=0
        extent = [times[0], times[-1], fmin, fmax]
        ax2.imshow(data_freq_time, cmap='viridis', vmin=-3, vmax=3, interpolation='nearest', aspect='auto', origin='upper', extent=extent)
        ax2.set_xlabel('Time (ms)')
        ax2.set_ylabel('Freq (Mhz)')
        fig.suptitle("p: {:.2f}, S/N: {:.0f}, DM: {:.2f}, T0: {:.2f}, CB: {:02d}".format(prob, snr, dm, t0, cb))
        plt.savefig("plots/cand_{:04d}_snr{:.0f}_dm{:.0f}.pdf".format(i, snr, dm))
        plt.close(fig)
