# Author: Daniel van der Schuur
# Adapted for any science case + bands + telescopes by Leon Oostrum

if [ "$#" -ne 2 ] && [ "$#" -ne 3 ] && [ "$#" -ne 4 ]; then
    echo "Usage: $0 bands, telescopes, opts (optional), pol (optional)"
    echo "E.g. for starting 14 bands on RT4 and RT7:"
    echo "$0 2:15 4,7"
    echo "Or"
    echo "$0 2:15 4,7 centraldipole 0"
    echo "Note: bands are specified as a range, telescopes should be a comma-separated list. pol 0 = X, pol 1 = Y. Anything else for dual pol. Opts can be 'centraldipole' to use only central dipole. Also specify opts when using pol"
    exit
fi

unbs="$1"
tels="$2"
opts="$3"
pol="$4"

if [ x"$opts" == x ]; then
    opts="--opt none"
else
    opts="--opt $opts"
fi

if [ x"$pol" == x"0" ] || [ x"$pol" == x"1" ]; then
    # single pol
    pol="--pol $pol"
else
    # dual pol
    pol=""
fi

ssh -t arts@192.168.3.74 python /home/arts/SVN/RadioHDL/trunk/applications/apertif/commissioning/main.py --app arts_sc4 --tel $tels --unb $unbs $opts $pol

# Gain, correcting for nr of pols
if [ "$pol" == "" ]; then
    # dual pol
    single_dish_gain=1000
else
    # single pol
    single_dish_gain=1000
fi

ndish_min1=$(grep -o "," <<< $tels | wc -l)
ndish=$(echo "$ndish_min1 + 1" | bc)
gain=$(echo "$single_dish_gain / $ndish" | bc)
echo "Found $ndish dishes, setting gain to $gain"
# setting gain sometimes fails: always try twice
ssh -t arts@192.168.3.74  python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/util_dp_gain.py --unb $unbs --fn 0:3 --bn 0:3 -n 1 -r $gain,1,1,1
ssh -t arts@192.168.3.74  python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/util_dp_gain.py --unb $unbs --fn 0:3 --bn 0:3 -n 1 -r $gain,1,1,1
