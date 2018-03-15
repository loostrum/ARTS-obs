#!/usr/bin/env bash
#
# Script to set process AMBER triggers on each worker node
# Author: L.C. Oostrum


triggerscript=$HOME/software/arts-analysis/triggers.py
preproc=$HOME/software/arts-analysis/preprocess.py
classifier=$HOME/software/single_pulse_ml/single_pulse_ml/run_single_pulse_DL.py
trigger_to_master=$HOME/ARTS-obs/trigger_to_master.py
plotter=$HOME/ARTS-obs/plotter.py

ntrig=1000000
cmap=viridis
ntime_plot=250
nfreq_plot=32
ndm=1
fmt=hdf5
dmmin=5

outputdir=$1
filfile=$2
prefix=$3
master_dir=$4
snrmin=$5

# create master trigger files
cat ${prefix}_step*trigger > ${prefix}.trigger
# get number of raw candidates
ncand_raw=$(grep -v \# ${prefix}.trigger | wc -l)

# make sure we start clean
rm -f $outputdir/*hdf5
rm -f $outputdir/plots/*pdf
mkdir -p $outputdir/plots
cd $outputdir
source $HOME/venv/bin/activate
# process the triggers without making plots
python $triggerscript --dm_thresh $dmmin --sig_thresh $snrmin --ndm $ndm --save_data $fmt --ntrig $ntrig --nfreq_plot $nfreq_plot --ntime_plot $ntime_plot --cmap $cmap $filfile ${prefix}.trigger
# get number of triggers after grouping
if [ ! -f grouped_pulses.singlepulse ]; then
    ncand_grouped=0
else
    ncand_grouped=$(wc -l grouped_pulses.singlepulse | awk '{print $1}')
    # concatenate hdf5 files
    python $preproc --fnout combined.hdf5 --nfreq_f $nfreq_plot --ntime_f $ntime_plot $(pwd)
    deactivate
    # run the classifier
    spack unload cuda
    spack load cuda@9.0
    source /export/astron/oostrum/tensorflow/bin/activate
    python $classifier combined.hdf5
    deactivate
    # make plots
    source $HOME/venv/bin/activate
    python $plotter combinefreq_time_candidates.hdf5
    # merge and copy to master node
    ncands=$(ls $outputdir/plots | wc -l)
    merged=candidates.pdf
    if [ $ncands -ne 0 ]; then
        # create merged pdf
        gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=$merged plots/*pdf
    fi
fi
# copy results to masternode
python $trigger_to_master combinefreq_time_candidates.hdf5 $ncand_raw $ncand_grouped $master_dir
deactivate

#mailto="oostrum@astron.nl"
#subject="$(date): FRB triggers from $(hostname --fqdn)"
#attachment=candidates.pdf
#if [ $ncands -ne 0 ]; then
#    gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile=$attachment plots/*pdf
#    (
#        echo "From: ARTS FRB Alert System <arts@$(hostname).apertif>"
#        echo "To: $mailto"
#        echo "Subject: $subject"
#        echo "MIME-Version: 1.0"
#        echo "Content-Type: multipart/mixed; boundary="-q1w2e3r4t5""
#        echo
#        echo "---q1w2e3r4t5"
#        echo "Content-Type: text/plain; charset=utf-8"
#        echo "Content-Transfer-Encoding: 8bit"
#        echo
#        echo "Hi there,"
#        echo 
#        echo "This is the FRB alert system at $(hostname --fqdn)."
#        echo
#        echo "Please have a look at the attached FRB triggers from this filterbank file:"
#        echo "$filfile"
#        readfile $filfile
#        echo "Number of candidates after grouping: $ncand_grouped"
#        echo "Number of candidates after ML classifier: $ncands"
#        echo "---q1w2e3r4t5"
#        echo "Content-Type: application/pdf; charset=utf-8; name=$attachment"
#        echo "Content-Transfer-Encoding: base64"
#        echo "Content-Disposition: attachment; filename=$name"
#        echo
#        base64 < $attachment
#        echo
#        echo "---q1w2e3r4t5--"
#    ) | /usr/sbin/sendmail $mailto
#else
#    # no candidates found
#    (
#        echo "From: ARTS FRB Alert System <arts@$(hostname).apertif>"
#        echo "To: $mailto"
#        echo "Subject: $subject"
#        echo "Hi there,"
#        echo 
#        echo "This is the FRB alert system at $(hostname --fqdn)."
#        echo "No FRB triggers were found in this filterbank file:"
#        echo "$filfile"
#        readfile $filfile | tail -n +5
#        echo "Number of candidates after grouping: $ncand_grouped"
#        echo "Number of candidates after ML classifier: $ncands"
#    ) | /usr/sbin/sendmail $mailto
#
#fi
