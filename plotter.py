#!/usr/bin/env python
#
# Plot triggers output by the ML classifier

import sys

import h5py
import matplotlib
matplotlib.use('pdf')
import matplotlib.pyplot as plt


if __name__ == '__main__':
    # input hdf5 file
    fname = sys.argv[1]

    # read dataset 
    with h5py.File(fname, 'r') as f:
        data_frb_candidate = f['data_frb_candidate']
        probability = f['probability']
        params = f['params']  # snr, DM, boxcard width, arrival time

    for i, cand in data_frb_candidate:
        data_freq_time = cand[:, :, 0]
        prob = probability[i]
        snr, dm, boxcar_width, t0 = params[i]

        fig, ax = plt.subplots()
        # scaling: std = 1, median=0
        ax.imshow(data_freq_time, cmap='viridis', vmin=-3, vmax=3, interpolation='nearest', aspect='equal')
        fig.suptitle("p: {:.1f} }SNR: {:.0f} DM: {:.2f}, T0: {:.2f}".format(prob, snr, dm, t0))
        plt.savefig("plots/cand_{:2d}_snr{:.0f}_dm{:.0f}.pdf".format(i, snr, dm))
        plt.close(fig)
