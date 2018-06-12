#!/bin/bash

if [ $(hostname) == arts041 ]; then
    echo "Should run on a worker node"
    exit
fi

key=dada
nchan=1536
pagesize=25000
nbuf=5
sc=4
#mode=0 # I+TAB
mode=2 # I+IAB

if [ x$mode == x0 ]; then
    ntab=12
elif [ x$mode == x2 ]; then
    ntab=1
else
    echo "Mode should be 0 or 2"
    exit
fi

# record 2 * 1.024 seconds of data
nbatch=2
dur=$(bc -l <<<"$nbatch * 1.024")
nread=1

# start in 5 seconds from now
now=$(date +%s)
tstart=$(($now+5))

# start time for header and fill_ringbuffer
startpacket=$(bc -l <<< "$tstart * 781250")
mjd_start=$(bc -l <<< "($tstart / 86400.0) + 40587")
utc_start=$(date -u +%Y-%m-%d-%H:%M:%S --date "@$tstart")

# CB is hostname-1
host=$(hostname | tail -c 3)
hostnum=$(printf "%02d" $host)
cb=$(($hostnum-1))
if [ $cb -lt 10 ]; then
    cb=0$cb
fi
port=50$cb

cp header_template.txt header.txt
echo "BEAM $cb" >> header.txt
echo "UTC_START ${utc_start}" >> header.txt
echo "MJD_START ${mjd_start}" >> header.txt
echo "SCIENCE_MODE ${mode}" >> header.txt

pkill fill_ringbuffer
dada_db -d -k $key 2>/dev/null

echo "Starting buffer"
dada_db -k $key -b $(($nchan * $pagesize * $ntab)) -n $nbuf -r $nread -p
echo "starting reader"
dadafilterbank -k $key -l dadafilterbank.log -n gain &


sleep 2
echo "filling buffer"
fill_ringbuffer -h header.txt -k $key -s $startpacket -d $dur -p $port -l fill_ringbuffer.log

dada_db -d -k $key
