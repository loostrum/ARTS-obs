#!/usr/bin/env bash
#
# Setup observing commands for ARTS
# Author: L.C. Oostrum

# Master node
MASTER="arts041"
# directory of this script
SOURCE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) && pwd)
# directory of control scripts
CONTROL=$SOURCE_DIR/control
# directory of utility scripts
UTIL=$SOURCE_DIR/utilities

# scripts only for master node
if [ "$(hostname)" == "$MASTER" ]; then
    alias start_streams=$CONTROL/start_streams.sh
    alias set_gain=$CONTROL/set_gain.sh
    alias read_gain=$CONTROL/read_gain.sh
    alias auto_gain=$SOURCE_DIR/auto_gain/set_auto_gain.py
    alias point_array=$CONTROL/point_array.sh
    alias start_obs=$SOURCE_DIR/start_survey_master.py
fi

# scripts for all nodes
alias CB_to_offset=$CONTROL/CB_to_offset.py
alias get_ha=$UTIL/get_ha.py
alias psr_ra_dec=$UTIL/psr_ra_dec.sh
alias packet_rate=$CONTROL/packet_rate.py
# ARTS041 40g link is down, so allow on all nodes for now
alias check_40g_links=$CONTROL/check_40g_links.py
