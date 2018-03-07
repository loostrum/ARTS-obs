#!/usr/bin/env bash
#
# Script to set process AMBER triggers on each worker node
# Author: L.C. Oostrum


triggerscript=$HOME/software/arts-analysis/triggers.py

ntrig=1000000
cmap=viridis
ntime_plot=250
nfreq_plot=32
ndm=20
fmt=hdf5

outputdir=$1
filfile=$2
prefix=$3
snrmin=$4

# create master trigger files
cat ${prefix}*trigger > ${prefix}.trigger

mkdir -p $outputdir/plots
cd $outputdir
source $HOME/venv/bin/activate
# process the triggers
python $triggerscript --sig_thresh $snrmin --ndm $ndm --save_data $fmt --mk_plot --ntrig $ntrig --nfreq_plot $nfreq_plot --ntime_plot $ntime_plot --cmap $cmap $filfile $prefix.trigger
deactivate
# make merged pdf if < 1000 triggers, then email
numtrigger=$(ls $outputdir/plot | wc -l)
if [ $numtrigger -lt 1000 ]; then
    gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=merged.pdf $outputdir/plots/*pdf
    $HOME/bin/emailer merged.pdf
else
    touch empty.pdf
    $HOME/bin/emailer empty.pdf
fi
