#!/bin/bash
# Telescope pointing
# Author: Leon Oostrum

if [ -z $1 ]; then
    echo Pass \'stop\', \'stow\', \(RA, DEC\) or one of the following supported sources as argument 1:
    echo
    echo 0248 : source = J0248+6021
    echo 0329 : source = B0329+54
    echo 0531 : source = Crab
    echo 0950 : source = B0950+08
    echo 1022 : source = J1022+1001
    echo 1713 : source = J1713+0747
    echo 1855 : source = B1855+09
    echo 1908 : source = B1908+00A
    echo 1937 : source = B1937+21
    echo 1900 : source = B1900+01
    echo 1901 : source = J1901+0435
    echo 1933 : source = B1933+16
    echo 2020 : source = B2020+28
    echo 2303 : source = B2303+46
    echo Cas.A : source = Cas.A
    echo Coff1 : source = CasA-5deg.
    echo Coff2 : source = CasA+5deg.
    echo
    echo To specify dishes, pass a comma separated list \(no spaces\) as
    echo second argument, e.g. \'rt4,rt5,rt6,rt7,rt8\' \(without quotes\).
    echo
    echo Full command example: ./point_array.sh 0329 rt6,rt7,rta
    echo
    echo No argument passed. Exiting
fi

if [ "$#" == "3" ]; then
    # user passed ra and dec, dishes are $3
    echo Now pointing dishes $3 to \(RA, DEC\) = \($1, $2\)
else
  # user passed stop, stow or source name, dishes are $2
  if [ "$2" == "" ]; then
    echo "No dishes passed. Exiting"
    exit
  fi

  # check stop, stow or source name
  if [ "$1" == "stow" ]; then
    echo "Stowing dishes $2"
  elif [ "$1" == "stop" ]; then
    echo "Stop tracking dishes $2"
  elif [ "$1" == "check" ]; then
    echo "Checking dishes $2"
  else
    echo Now pointing dishes $2 to source $1
  fi
fi
ssh -t arts@192.168.3.74 python /home/arts/SVN/RadioHDL/trunk/applications/arts/commissioning/point_array.py $@

