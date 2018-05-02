#!/bin/bash

tels="$1"

if [ "$tels" == "" ]; then
    echo "Usage: $(basename $0) RTs"
    echo "E.g. $(basename $0) 8,9,a,b"
    exit
fi

tels2="${tels//,/ }"

for tel in $tels2; do 
    ssh lcu-rt$tel "cd LO1; python util_get_lo1freq.py 2>/dev/null"
done

exit
