#!/bin/bash
tels="$1"
freq="$2"

if [ "$#" -ne 2 ]; then
    echo "Usage: $(basename $0) RTs LO1freq"
    echo "E.g.: $(basename $0) 8,9,a,b 4770"
    exit
fi

if [ "$tels" == "all" ]; then
    tels="2,3,4,5,6,7,8,9,a,b,c,d"
elif [ "$tels" == "fixed" ]; then
    tels="2,3,4,5,6,7,8,9"
elif [ "$tels" == "a8" ]; then
    tels="2,3,4,5,6,7,8,9"
elif [ "$tels" == "a10" ]; then
    tels="2,3,4,5,6,7,8,9,a,b"
fi


tels2="${tels//,/ }"

for tel in $tels2; do 
    ssh lcu-rt$tel "cd LO1; python util_set_lo1freq.py $freq 2>/dev/null" &
done
wait

exit
