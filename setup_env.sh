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
    start_streams () { $CONTROL/start_streams.sh "$@"; }
    set_lo1freq () { $CONTROL/set_lo1freq.sh "$@"; }
    read_lo1freq () { $CONTROL/read_lo1freq.sh "$@"; }
    point_array () { $CONTROL/point_array.sh "$@"; }
    start_obs () { $SOURCE_DIR/start_survey_master.py "$@"; }
    disable_dish () { $CONTROL/disable_dish.py "$@"; }
    enable_dish () { $CONTROL/enable_dish.py "$@"; }
fi

# scripts for all nodes
CB_to_offset () { $CONTROL/CB_to_offset.py "$@"; }
get_ha () { $UTIL/get_ha.py "$@"; }
psr_ra_dec () { $UTIL/psr_ra_dec.sh "$@"; }
#packet_rate () { $CONTROL/packet_rate.py "$@"; }  # now in ~/bin for easier use over ssh
# ARTS041 40g link is down, so allow on all nodes for now
check_40g_links () { $CONTROL/check_40g_links.py "$@"; }
