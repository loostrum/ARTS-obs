#!/usr/bin/env python

import os
import sys

import argparse

from lofar.parameterset import parameterset

def fix_ha(ha):
    postfix = raw_ha[-3:]
    ha = float(raw_ha[:-3])
    if ha > 180:
        ha -= 360 
    if ha < -180:
        ha += 360 
    new_raw_ha = str(ha)+postfix
    return new_raw_ha
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parset_folder = '/opt/apertif/share/parsets'

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--taskid', help="Taskid of parset to fix HADEC pointing of. Full path assumed to be {}/<taskid>.parset".format(parset_folder))
    group.add_argument('--parset', help="Full path to parset to fix HADEC pointing of")

    args = parser.parse_args()
    if args.taskid is None and args.parset is None:
        print "Provied either taskid or full parset path"
        sys.exit(1)

    if args.taskid:
        full_path = os.path.join(parset_folder, '{}.parset'.format(args.taskid))
    else:
        full_path = args.parset

    if not os.path.isfile(full_path):
        print "File not found: {}".format(full_path)
        sys.exit(1)

    # load parset 
    parset = parameterset()
    parset.adoptFile(full_path)

    # check if ref frame is hadec
    ref_frame = parset.getString('task.directionReferenceFrame')
    if not ref_frame.upper() == 'HADEC':
        print "This is not a HADEC parset!"
        sys.exit(1)

    # fix the phase centers
    for beam in range(40):
        key = 'task.beamSet.0.compoundBeam.{}.phaseCenter'.format(beam)
        try:
            value = parset.getStringVector(key)
        except RuntimeError as e:
            print "Failed to get phase center of beam {}: {}".format(beam, e)
            continue
        # do the HA fix
        raw_ha, raw_dec = value
        new_raw_ha = fix_ha(raw_ha)
        print "Changing CB{} phase center HA from {} to {}".format(beam, raw_ha, new_raw_ha)
        new_value = "[{}, {}]".format(new_raw_ha, raw_dec)
        parset.replace(key, new_value)

    # fix the telescope pointings
    telescopes = parset.getStringVector('task.telescopes')
    for telescope in telescopes:
        key = 'task.telescope.{}.pointing'.format(telescope)
        try:
            value = parset.getStringVector(key)
        except RuntimeError as e:
            print "Failed to get phase center of beam {}: {}".format(beam, e)
            continue
        raw_ha, raw_dec = value
        new_raw_ha = fix_ha(raw_ha)
        print "Changing {} pointing HA from {} to {}".format(telescope, raw_ha, new_raw_ha)
        new_value = "[{}, {}]".format(new_raw_ha, raw_dec)
        parset.replace(key, new_value)
    
    # write the new parset
    parset.writeFile(full_path)
