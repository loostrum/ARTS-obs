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
triggerfile=$3
snrmin=$4

mkdir -p $outputdir/plots
cd $outputdir
source $HOME/venv/bin/activate
python $triggerscript --sig_thresh $snrmin --ndm $ndm --save_data $fmt --mk_plot --ntrig $ntrig --nfreq_plot $nfreq_plot --ntime_plot $ntime_plot --cmap $cmap $filfile $triggerfile 
deactivate
