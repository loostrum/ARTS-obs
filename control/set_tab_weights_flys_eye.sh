#!/bin/bash
#
# set TAB beamformer weights for fly's eye mode
# TAB 00 = RT2
# TAB 01 = RT3
# TAB 02 = RT4
# TAB 03 = RT5
# TAB 04 = RT6
# TAB 05 = RT7
# TAB 06 = RT8
# TAB 07 = RT9
# TAB 08 = RTA
# TAB 09 = RTB
# TAB 10 = unused -> all zeroes
# TAB 11 = unused -> all zeroes


if [ "$#" -ne 2 ]; then
    echo "Usage: $0 bands, weight"
    echo "E.g. for setting up fly's eye on bands 2 to 15 with weight 31 for both Re and Im:"
    echo "$0 2:15 31,31"
    exit
fi

unbs="$1"
weights="$2"

# first set all weights to zero
ssh -t arts@ccu-corr.apertif python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/pi_arts_tab_beamformer_weights.py --cmd 3 --input 0:11 --tabs 0:11 --unb $unbs --fn 0:3 --bn 0:3 --weight 0,0

for i in {00..09}; do 
    ssh -t arts@ccu-corr.apertif python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/pi_arts_tab_beamformer_weights.py --cmd 3 --input $i --tabs $i --unb $unbs --fn 0:3 --bn 0:3 -a --weight $weights
done
