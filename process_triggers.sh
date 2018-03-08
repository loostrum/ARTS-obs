#!/usr/bin/env bash
#
# Script to set process AMBER triggers on each worker node
# Author: L.C. Oostrum


triggerscript=$HOME/software/arts-analysis/triggers.py
preproc=$HOME/software/arts-analysis/preprocess.py
classifier=$HOME/software/single_pulse_ml/single_pulse_ml/run_single_pulse_DL.py
plotter=$HOME/ARTS-obs/plotter.py

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
# process the triggers without making plots
#python $triggerscript --sig_thresh $snrmin --ndm $ndm --save_data $fmt --mk_plot --ntrig $ntrig --nfreq_plot $nfreq_plot --ntime_plot $ntime_plot --cmap $cmap $filfile $prefix.trigger
python $triggerscript --sig_thresh $snrmin --ndm $ndm --save_data $fmt --mk_plot=False --ntrig $ntrig --nfreq_plot $nfreq_plot --ntime_plot $ntime_plot --cmap $cmap $filfile ${prefix}.trigger
# concatenate hdf5 files
python $preproc --fnout combined.hdf5 --nfreq_f $nfreq_plot --ntime_f $ntime_plot $(pwd)
deactivate
# run the classifier
spack unload cuda
spack load cuda@9.0.176
source /export/astron/oostrum/tensorflow/bin/activate
python $classifier combined.hdf5
deactivate
# make plots
source $HOME/venv/bin/activate
python $plotter combinedfreq_time_candidates.hdf5
deactivate
# merge 
gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=candidates.pdf plots/*pdf
# email
$HOME/bin/emailer candidates.pdf
