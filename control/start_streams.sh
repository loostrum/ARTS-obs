# Author: Daniel van der Schuur
# Adapted for any science case + bands + telescopes by Leon Oostrum

if [ "$#" -ne 2 ] && [ "$#" -ne 3 ] && [ "$#" -ne 4 ]; then
    echo "Usage: $0 [dev] bands, telescopes, pol (optional), opts (optional)"
    echo "E.g. for starting 14 bands on RT4 and RT7:"
    echo "$0 2:15 4,7"
    echo "Or"
    echo "$0 2:15 4,7 0 centraldipole"
    echo "Note: bands are specified as a range, telescopes should be a comma-separated list or all/fixed/a8/10. pol 0 = X, pol 1 = Y. Anything else for dual pol. Opts can be 'centraldipole' to use only central dipole. Also specify pol when using opts"
    exit
fi

if [ "$1" == "dev" ]; then
    echo "ERROR: dev option not implemented yet on ccu-corr"
    exit
    app=arts_sc4-dev
    shift
else
    app=arts_sc4
fi

unbs="$1"
tels="$2"
pol="$3"
opts="$4"

if [ "$tels" == "all" ]; then
    tels="2,3,4,5,6,7,8,9,a,b,c,d"
elif [ "$tels" == "fixed" ]; then
    tels="2,3,4,5,6,7,8,9"
elif [ "$tels" == "a8" ]; then
    tels="2,3,4,5,6,7,8,9"
elif [ "$tels" == "a10" ]; then
    tels="2,3,4,5,6,7,8,9,a,b"
fi

if [ x"$opts" == x ]; then
    opts=""
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

ssh -t arts@ccu-corr.apertif python /home/arts/SVN/RadioHDL/trunk/applications/apertif/commissioning/main.py --app $app --tel $tels --unb $unbs $opts $pol

# only set gain for science mode (i.e. IAB)
if [ "$app" == "arts_sc4" ]; then
    single_dish_gain=5000

    ndish=$(grep -o "," <<< $tels, | wc -l)
    gain=$(echo "$single_dish_gain / $ndish" | bc)
    echo "Found $ndish dishes, setting gain to $gain"
    # setting gain sometimes fails: always try twice
    ssh -t arts@ccu-corr.apertif  python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/util_dp_gain.py --unb $unbs --fn 0:3 --bn 0:3 -n 1 -r $gain,$gain,$gain,$gain
    ssh -t arts@ccu-corr.apertif  python /home/arts/SVN/UniBoard/trunk/Software/python/peripherals/util_dp_gain.py --unb $unbs --fn 0:3 --bn 0:3 -n 1 -r $gain,$gain,$gain,$gain
fi
