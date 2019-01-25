#!/usr/bin/env bash
#
# Script to set process AMBER triggers on each worker node
# Author: L.C. Oostrum

# directory of this script
SOURCE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)

triggerscript=$SOURCE_DIR/external/arts-analysis/triggers.py
classifier=$SOURCE_DIR/external/single_pulse_ml/single_pulse_ml/classify.py
trigger_to_master=$SOURCE_DIR/trigger_to_master.py
# python venv location
venv_dir=$HOME/python34

cmap=viridis
ntime_plot=64
nfreq_plot=32
ndm=1
fmt=concat
modeldir=$HOME/keras_models
pthresh=0.5
ML_GPUs=0

outputdir=$1
filfile=$2
prefix=$3
master_dir=$4
snrmin=$5
snrmin_local=$6
dmmin=$7
dmmax=$8
CB=$9
time_limit=${10}

# Set GPUs visible to the classifier
export CUDA_VISIBLE_DEVICES=$ML_GPUs

# create master trigger files
cat ${prefix}_step*trigger > ${prefix}.trigger
# get number of raw candidates
ncand_raw=$(grep -v \# ${prefix}.trigger | wc -l)

# make sure we start clean
rm -f $outputdir/data/*
rm -f $outputdir/plots/*pdf
cd $outputdir
# process the triggers without making plots
trig_start=$(date)
python $triggerscript --rficlean --sig_thresh_local $snrmin_local --time_limit $time_limit --descending_snr --beamno $CB --mk_plot --dm_min $dmmin --dm_max $dmmax --sig_thresh $snrmin --ndm $ndm --save_data $fmt --nfreq_plot $nfreq_plot --ntime_plot $ntime_plot --cmap $cmap --outdir=$outputdir $filfile ${prefix}.trigger
trig_end=$(date)

# get number of triggers after grouping
if [ ! -f grouped_pulses.singlepulse ]; then
    ncand_grouped=0
else
    ncand_grouped=$(wc -l grouped_pulses.singlepulse | awk '{print $1}')
    # run the classifier
    source $venv_dir/bin/activate
    # to add DM model: --fn_model_dm $modeldir/heimdall_dm_time.hdf5
    python $classifier --fn_model_time $modeldir/heimdall_b0329_mix_147411d_time.hdf5 --pthresh $pthresh --save_ranked --plot_ranked --fnout=ranked_CB$CB $outputdir/data/data_full.hdf5 $modeldir/20190125-17114-freqtimefreq_time_model.hdf5
    deactivate
    # merge classifier summary figs
    nMLfigs=$(ls $outputdir/*pdf | wc -l)
    merged=candidates_summary.pdf
    if [ $nMLfigs -ne 0 ]; then
        # create merged pdf
        gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=$merged $outputdir/*pdf
    fi
fi
# copy results to masternode
python $trigger_to_master ranked_CB${CB}_freq_time.hdf5 $ncand_raw $ncand_grouped $master_dir

echo "Start of triggers.py: $trig_start"
echo "End of triggers.py: $trig_end"
