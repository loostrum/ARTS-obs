#!/usr/bin/env python
#
# Get the number of items in an hdf5 file
# Author: L.C. Oostrum

import os
import sys

# Disable h5py FutureWarning we cannot do anythign about
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import h5py



if __name__ == '__main__':
    # key to use for dataset in hdf5 file
    key = 'data_frb_candidate'

    try:
        fname = sys.argv[1]
    except IndexError:
        sys.stderr.write('{}: Provide filename as first argument\n'.format(sys.argv[0]))
        exit()

    if not os.path.isfile(fname):
        sys.stderr.write('{}: File not found: {}\n'.format(sys.argv[0], fname))
        exit()

    # typical filename: ranked_CB21_freq_time.hdf5
    with h5py.File(fname) as f:
        keys = f.keys()
        if not key in keys:
            sys.stderr('{}: Key not found: {}, setting nitem to 0\n'.format(sys.argv[0], key))
            nitem = 0
        else:
            nitem = f[key].shape[0]

    sys.stdout.write('{:.0f}\n'.format(nitem))
