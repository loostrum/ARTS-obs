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
    # input hdf5 file 1 = output of triggers.py
    fname_clustered = sys.argv[1]
    # input hdf5 file 2 = output of clasifier
    fname_classifier = sys.argv[2]
    # number of candidates before grouping
    ncand_raw = int(sys.argv[3])
    # number of candidates before ML
    ncand_trigger = int(sys.argv[4])
    # dir on master node
    master_dir = sys.argv[5]
    # beam of this node
    beam = int(socket.gethostname()[5:7]) - 1
    # read clustering output
    try:
        # read dataset
        with h5py.File(fname_clustered, 'r') as f:
            ncand_skipped = int(f['ntriggers_skipped'][0])
    except IOError:
        #success = False
        print "WARNING: could not get ncand_skipped from {}".format(fname_clustered)
        ncand_skipped = -1
    # read classifier output
    try:
        # read dataset 
        with h5py.File(fname_classifier, 'r') as f:
            frb_index = f['frb_index'][:]
            data_frb_candidate = f['data_frb_candidate'][:]
            probability = f['probability'][:][frb_index]
            params = f['params'][:][frb_index]  # snr, DM, downsampling, arrival time, dt
    except IOError:
        success = False
        ncand_classifier = 0
    # else only gets executed if the try succeeds
    else:
        # convert widths to ms 
        params[:, 2] *= params[:, 4] * 1000
        # number of canddiates
        ncand_classifier = len(params)
        # make one big matrix with candidates, removing the dt column
        data = np.column_stack([params[:, :4], probability])
        # sort by probability
        data = data[data[:, -1].argsort()[::-1]]
        # save to file
        header = "SNR DM Width T0 p"
        fname = "CB{:02d}_triggers.txt".format(beam)
        np.savetxt(fname, data, header=header, fmt="%.2f %.2f %.4f %.3f %.2f")
        # copy to master node
        cmd = "cp {fname} {master_dir}/ &".format(fname=fname, master_dir=master_dir, beam=beam)
        os.system(cmd)

    # copy candidates file if it exists
    fname = "candidates_summary.pdf"
    if os.path.isfile(fname):
        cmd = "cp {fname} {master_dir}/CB{beam:02d}_candidates_summary.pdf &".format(beam=beam, master_dir=master_dir, fname=fname)
        os.system(cmd)
    else:
        success = False

    # create summary file
    summary = {}
    summary['success'] = success
    summary['ncand_raw'] = ncand_raw
    summary['ncand_trigger'] = ncand_trigger
    summary['ncand_skipped'] = ncand_skipped
    summary['ncand_abovethresh'] = ncand_trigger - ncand_skipped
    summary['ncand_classifier'] = ncand_classifier
    fname = "CB{:02d}_summary.yaml".format(beam)
    with open(fname, 'w') as f:
        yaml.dump(summary, f, default_flow_style=False)
    # copy to master node
    cmd = "cp {fname} {master_dir}/ &".format(fname=fname, master_dir=master_dir, beam=beam)
    os.system(cmd)
    
