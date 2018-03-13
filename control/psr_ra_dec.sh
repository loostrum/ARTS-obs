#!/bin/bash

psr=$1

if [ -z $psr ]; then
    echo "Specify pulsar name as first argument"
    exit
fi

RA=$(psrcat -e $psr | grep RAJ | awk '{print $2}')
DEC=$(psrcat -e $psr | grep DECJ | awk '{print $2}')

if [ -z $RA ]; then
    echo "Warning: coordinates not found for PSR $psr"
    RA=00:00:00
    DEC=00:00:00
fi

echo --source $psr --ra $RA --dec $DEC
