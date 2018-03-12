# Author: Daniel van der Schuur, Leon Oostrum
# Usage: -r I,Q,U,V
# Default values in firmware are 1,1,1,1

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 bands, gain"
    echo "E.g. for setting the gain to 3150 on 14 bands:"
    echo "$0 2:15 3150"
    echo "Note: bands are specified as a range, gain should be an integer."
    exit
fi

unbs="$1"
gain="$2"

ssh -t arts@192.168.3.74 python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/util_dp_gain.py --unb $unbs --fn 0:3 --bn 0:3 -n 1 -r $gain,1,1,1
