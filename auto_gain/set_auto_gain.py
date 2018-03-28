#!/usr/bin/env python
#
# set gain automatically based on data

import os
import sys

import numpy as np
from sigpyproc.Readers import FilReader


def get_scaling(filfile, dest_value):
    if not os.path.isfile(filfile):
        print "No such file: {}".format(filfile)
        sys.exit(1)

    f = FilReader(filfile)

    bandpass = f.bandpass() / f.header.nsamples
    avgsample = np.average(bandpass)
    scale = float(dest_value) / avgsample

    return scale


def set_gain(gain, uniboards):
    cmd = "ssh -t arts@ccu-corr python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/util_dp_gain.py --unb {unb} --fn 0:3 --bn 0:3 -n 1 -r {I},{Q},{U},{V}".format(unb=uniboards, I=gain, Q=1, U=1, V=1)
    os.system(cmd)


if __name__ == '__main__':
    try:
        uniboards = sys.argv[1]
    except IndexError:
        uniboards = '0:15'

    script_path = os.path.dirname(os.path.realpath(__file__))

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
        recorder = os.path.join(script_path, 'record_data.sh')
        os.system(recorder)
        # read scaling
        scale = get_scaling(os.path.join(script_path, 'gain.fil'), dest_value)
        # calc new gain
        old_gain = gain
        gain = int(scale * old_gain)

    # set the final gain
    set_gain(gain, uniboards)
    # remove the filterbank
    cmd = "rm -f {}".format(os.path.join(script_path, 'gain.fil'))
    os.system(cmd)
    print "Done, final gain set to {}".format(gain)
