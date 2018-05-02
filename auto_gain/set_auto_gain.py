#!/usr/bin/env python
#
# set gain automatically based on data

import os
import sys
import socket

import numpy as np
from sigpyproc.Readers import FilReader


def get_scaling(dest_value):
    f = FilReader('gain.fil')
    bandpass = f.bandpass() / f.header.nsamples
    avgsample = np.average(bandpass[np.nonzero(bandpass)])
    scale = float(dest_value) / avgsample

    return scale


def set_gain(gain, uniboards):
    cmd = "ssh -t arts@ccu-corr python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/util_dp_gain.py --unb {unb} --fn 0:3 --bn 0:3 -n 1 -r {I},{Q},{U},{V}".format(unb=uniboards, I=gain, Q=gain, U=gain, V=gain)
    os.system(cmd)


if __name__ == '__main__':
    try:
        uniboards = sys.argv[1]
    except IndexError:
        uniboards = '0:15'

    hostname = socket.gethostname()

    if not hostname == 'arts022':
        # ssh to arts022 and run it there
        print "I am not arts022. trying to ssh to arts022"
        cmd = "ssh arts022 {} {}".format(os.path.realpath(__file__), uniboards)
        os.system(cmd)
        sys.exit()

    # Everything below here only runs on arts022

    script_path = os.path.dirname(os.path.realpath(__file__))
    os.chdir(script_path)

    start_gain = 20  # should not overflow IAB-12
    max_offset = 0.05  # 5<% difference between new and old gain means we're done
    dest_value = 128  # the sample value we want

    # loop until new gain is close to old gain
    old_gain = 1
    gain = start_gain

    while (float(old_gain)/gain < 1-max_offset) or (float(old_gain)/gain > 1+max_offset):
        # set gain
        set_gain(gain, uniboards)
        # record data
        os.system('./record_data.sh')
        # read scaling
        scale = get_scaling(dest_value)
        # calc new gain
        old_gain = gain
        gain = int(scale * old_gain)

    # remove the filterbank
    os.system("rm -f gain.fil")
    # set the final gain
    set_gain(gain, uniboards)
    print "Done, gain set to {}".format(gain)
