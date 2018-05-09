#!/bin/bash
#
# read TAB beamformer weights

if [ "$#" -ne 1 ]; then
    echo "echo "Specify uniboards as range, e.g. $0 2:15""
fi

unbs="$1"


ssh -t arts@ccu-corr.apertif python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/pi_arts_tab_beamformer_weights.py --cmd 1 --unb $unbs --fn 0:3 --bn 0:3
