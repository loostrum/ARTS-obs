#!/usr/bin/env bash
#
# Script to set process AMBER triggers on each worker node
# Author: L.C. Oostrum

# directory of this script
SOURCE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)

triggerscript=$HOME/software/arts-analysis/triggers.py
preproc=$HOME/software/arts-analysis/preprocess.py
classifier=$HOME/software/single_pulse_ml/single_pulse_ml/run_single_pulse_DL.py
trigger_to_master=$SOURCE_DIR/trigger_to_master.py
plotter=$HOME/software/arts-analysis/plotter.py
# python venv location
venv_dir=$HOME/python

ntrig=1000000
cmap=viridis
ntime_plot=250
nfreq_plot=32
ndm=1
fmt=hdf5
dmmin=10
dmmax=5000

outputdir=$1
filfile=$2
prefix=$3
master_dir=$4
snrmin=$5
CB=$6

# create master trigger files
cat ${prefix}_step*trigger > ${prefix}.trigger
# get number of raw candidates
ncand_raw=$(grep -v \# ${prefix}.trigger | wc -l)

# make sure we start clean
rm -f $outputdir/*hdf5
rm -f $outputdir/plots/*pdf
mkdir -p $outputdir/plots
cd $outputdir
# process the triggers without making plots
python $triggerscript --dm_min $dmmin --dm_max $dmmax --sig_thresh $snrmin --ndm $ndm --save_data $fmt --ntrig $ntrig --nfreq_plot $nfreq_plot --ntime_plot $ntime_plot --cmap $cmap $filfile ${prefix}.trigger
# get number of triggers after grouping
if [ ! -f grouped_pulses.singlepulse ]; then
    ncand_grouped=0
else
    ncand_grouped=$(wc -l grouped_pulses.singlepulse | awk '{print $1}')
    # concatenate hdf5 files
    python $preproc --fnout combined.hdf5 --nfreq_f $nfreq_plot --ntime_f $ntime_plot $(pwd)
    # run the classifier
    source $venv_dir/bin/activate
    python $classifier combined.hdf5
    deactivate
    # make plots
    python $plotter combinefreq_time_candidates.hdf5 $CB
    # merge and copy to master dir
    ncands=$(ls $outputdir/plots | wc -l)
    merged=candidates.pdf
    if [ $ncands -ne 0 ]; then
        # create merged pdf
        gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=$merged plots/*pdf
    fi
fi
# copy results to masternode
python $trigger_to_master combinefreq_time_candidates.hdf5 $ncand_raw $ncand_grouped $master_dir
