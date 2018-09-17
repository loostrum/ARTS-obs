#!/bin/bash
#
# Get the init BSN as set by main.py on the dishes

init_bsn_list=$(ssh ccu-corr 'grep init_bsn $COM_DESP/main.log' | awk '{print $21}' | uniq)

echo $init_bsn_list
