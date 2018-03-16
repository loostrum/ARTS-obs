#!/usr/bin/env python
#
# Plot triggers output by the ML classifier

import os
import sys
import socket

import numpy as np
import h5py
import yaml


if __name__ == '__main__':
    success = True
    # input hdf5 file = output of clasifier
    fname = sys.argv[1]
    # number of candidates before grouping
    ncand_raw = int(sys.argv[2])
    # number of candidates before ML
    ncand_trigger = int(sys.argv[3])
    # dir on master node
    master_dir = sys.argv[4]
    # beam of this node
    beam = int(socket.gethostname()[5:7]) - 1
    try:
        # read dataset 
        with h5py.File(fname, 'r') as f:
            data_frb_candidate = f['data_frb_candidate'][:]
            probability = f['probability'][:]
            params = f['params'][:]  # snr, DM, boxcar width, arrival time
    except IOError:
        success = False
        ncand_classifier = 0
    # else only gets executed if the try succeeds
    else:
        # number of canddiates
        ncand_classifier = len(params)
        # make one big matrix with candidates
        data = np.column_stack([params, probability])
        # save to file
        header = "SNR DM Width T0 p"
        fname = "CB{:02d}_triggers.txt".format(beam)
        np.savetxt(fname, data, header=header, fmt="%.2f %.2f %.4f %.4f %.2f")
        # copy to master node
        cmd = "scp {fname} arts041:{master_dir}/ &".format(fname=fname, master_dir=master_dir, beam=beam)
        os.system(cmd)

    # copy candidates file if it exists
    fname = "candidates.pdf"
    if os.path.isfile(fname):
        cmd = "scp {fname} arts041:{master_dir}/CB{beam:02d}_candidates.pdf &".format(beam=beam, master_dir=master_dir)
        os.system(cmd)
    else:
        success = False

    # create summary file
    summary = {}
    summary['success'] = success
    summary['ncand_raw'] = ncand_raw
    summary['ncand_trigger'] = ncand_trigger
    summary['ncand_classifier'] = ncand_classifier
    fname = "CB{:02d}_summary.yaml".format(beam)
    with open(fname, 'w') as f:
        yaml.dump(summary, f, default_flow_style=False)
    # copy to master node
    cmd = "scp {fname} arts041:{master_dir}/CB{beam:02d} &".format(fname=fname, master_dir=master_dir, beam=beam)
    os.system(cmd)
    
