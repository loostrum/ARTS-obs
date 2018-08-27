# Author: Daniel van der Schuur
# Adapted for any science case + bands + telescopes by Leon Oostrum

if [ "$#" -ne 2 ] && [ "$#" -ne 3 ] && [ "$#" -ne 4 ]; then
    echo "Usage: $0 [dev] bands, telescopes, opts (optional), pol (optional)"
    echo "E.g. for starting 14 bands on RT4 and RT7:"
    echo "$0 2:15 4,7"
    echo "Or"
    echo "$0 2:15 4,7 centraldipole 0"
    echo "Note: bands are specified as a range, telescopes should be a comma-separated list. pol 0 = X, pol 1 = Y. Anything else for dual pol. Opts can be 'centraldipole' to use only central dipole. Also specify opts when using pol"
    exit
fi

if [ "$1" == "dev" ]; then
    app=arts_sc4-dev
    shift
else
    app=arts_sc4
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

# set central frequency through LO1
LO2=3400
config_file=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)/../config.yaml
central_freq=$(grep [[:space:]]freq: $config_file | cut -d : -f 2)
LO1=$(($LO2+$central_freq))
for dish in ${tels//,/ }; do
    ssh arts@lcu-rt$dish "cd LO1; python util_set_lo1freq.py $LO1 2>/dev/null" &
done
wait

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
