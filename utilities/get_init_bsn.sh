#!/bin/bash
#
# Get the init BSN as set by main.py on the dishes

last_known_bsn=1213148553562500
init_bsn=$(ssh ccu-corr 'grep init_bsn $COM_DESP/main.log' | awk '{print $21}' | uniq | head -n 1)

# use last known value if empty
if [ -z $init_bsn ]; then
    echo "WARNING: could not get init BSN. Using last known value" >&2
    init_bsn=$last_known_bsn
fi
echo $init_bsn
