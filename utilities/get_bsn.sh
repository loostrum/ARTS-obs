#!/bin/bash
#
# Get the init BSN as set by main.py on the dishes

last_known_bsn=1216336740443750

current_bsn=$(ssh -o ConnectTimeout=10 apertif@ccu-corr 'ubctl --bsnstatus=mesh 2>/dev/null' | awk '{print $3}' | tail -n +6 | uniq | head -n 1)

# use last known value if empty
if [ -z $current_bsn ]; then
    echo "WARNING: could not get BSN from ccu-corr. Using last known value of $last_known_bsn" >&2
    current_bsn=$last_known_bsn
fi

# BSN can only increase; if not something is wrong and we use old value
if [ "$current_bsn" -lt "$last_known_bsn" ]; then
    echo "WARNING: BSN ($current_bsn) is lower than last known BSN ($last_known_bsn). Using last known value" >&2
    current_bsn=$last_known_bsn
fi

echo $current_bsn | tee $HOME/.controller/last_known_bsn
