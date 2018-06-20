#!/usr/bin/env python
#
# Script to set up a full survey mode observation on the ARTS cluster
# Should only be used on the master node
# Author: L.C. Oostrum

import os
import sys
import argparse
import datetime
import socket
import subprocess
import warnings
from time import sleep

import yaml
import numpy as np
from astropy.time import Time, TimeDelta
from astropy import units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz

CONFIG = "config.yaml"
NODECONFIG = "nodes/CB{:02d}.yaml"
NODEHEADER = "nodes/CB{:02d}_header.txt"
TEMPLATE = "header_template.txt"
AMBERCONFIG = "amber.yaml"
AMBERCONFDIR = "amber_conf"
COORD = "coordinates.txt"
INFO = "info.yaml"


def run_on_node(node, command, background=False):
    """Run command on an ARTS node. Assumes ssh keys have been set up
        node: nr of node (string or int)
        command: command to run
        background: whether to run ssh in the background
    """
    if isinstance(node, str):
        if len(node) == 1:
            # assume a leading 0 is missing
            node = '0'+node
        elif len(node) > 2:
            # wrong, should only have 2 digits. Assume extra leading zeros
            node = node[-3:]
        hostname = "arts0{}".format(node)
    else:
        hostname = "arts0{:02d}".format(node)

    if background:
        ssh_cmd = "ssh {} {} &".format(hostname, command)
        #ssh_cmd = "ssh {} 'source $HOME/python/bin/activate; {}' &".format(hostname, command)
    else:
        ssh_cmd = "ssh {} {}".format(hostname, command)
        #ssh_cmd = "ssh {} 'source $HOME/python/bin/activate; {}' &".format(hostname, command)
    log("Executing '{}'".format(ssh_cmd))
    os.system(ssh_cmd)


def log(message):
    """
    Log a message. Prints the hostname, then the message
    """
    print "Master: {}".format(message)


def pointing_to_CB_pos(CB, coords, pol='X'):
    """
    Convert dish pointing to RA and DEC of specified CB
    CB: number of CB to get position of
    coords: astropy.coordinates.SkyCoord object with dish pointing
    pol: polarization to use: X, Y, or average. Default: X
    returns: SkyCoord object with shifted coordinates
    """

    # PAF layout is based on generic elements (gels):
    # generic element (gel) layout:
    #
    #  0-----55------110
    #  |      |      |
    #  |      |      |
    #  5-----60------115
    #  |      |      |
    #  |      |      |
    #  10----65------120
    #
    # +DEC = North = down, +HA is West = right
    # +RA = east = left

    # 11*11 grid of elements
    nrows = 11
    ncols = 11
    # gel offsets
    offset_to_RADEC = 0.375  # degrees

    ### 32-beam IAB layout
    shift = 0.075  # degrees, extra shift needed for some rows/cols to match Apertif layout
    # gel for each CB, -1 means gel is not used
    # because gels use fortran ordering, this looks like the transpose of the beam layout on-sky
    gel_to_CB = [ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1, \
                  -1,  -1,   0,  -1,  12,  -1,  26,  -1,  23,  -1,  -1, \
                  -1,   3,   0,   6,  12,  20,  26,  32,  23,  -1,  -1, \
                  -1,   3,   1,   6,  15,  20,  27,  32,  28,  -1,  -1, \
                  -1,   8,   1,   7,  15,  21,  27,  35,  28,  -1,  -1, \
                  -1,   8,   2,   7,  16,  21,  30,  35,  33,  -1,  -1, \
                  -1,  13,   2,  10,  16,  22,  30,  36,  33,  -1,  -1, \
                  -1,  13,   5,  10,  17,  22,  31,  36,  38,  -1,  -1, \
                  -1,  18,   5,  11,  17,  25,  31,  37,  38,  -1,  -1, \
                  -1,  18,  -1,  11,  -1,  25,  -1,  37,  -1,  -1,  -1, \
                  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1]

    ### 37-beam apertif hex (so no CB37,CB38)
    #shift = 0 
    #gel_to_CB = [ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,   0,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,   0,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1, \
    #              -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1]


    # create CB -> gel mapping
    CB_to_gel_X = {}
    CB_to_gel_Y = {}
    for gel, cb in enumerate(gel_to_CB):
        if gel % 2:
            CB_to_gel_Y[cb] = gel
        else:
            CB_to_gel_X[cb] = gel

    # get the gel numbers of the requested CB
    try:
        gel = [CB_to_gel_X[CB], CB_to_gel_Y[CB]]
    except KeyError:
        # CB is not in IAB selection
        log("Could not get gel of CB{:02d}, returning input coordinates".format(CB))
        return coords

    # get row and column of gel
    # loop over X and Y element
    tmpshift = []
    for ele in gel:
        # Negative offsets are up and left with respect to central element. 
        # That corresponds to a negative offset in DEC and a positive offset in RA
        # gels use fortran ordering: row = RA, col = DEC
        # rows: negative offset = left = positive RA: multiply by -1
        # cols: negative ofset = up = negative DEC: correct
        row = -1 * (np.floor(ele/ncols) - nrows//2)
        col = (ele % nrows - nrows//2)

        dRA = row * offset_to_RADEC 
        dDEC = col * offset_to_RADEC
        # apply shifts (do not understand yet why these are needed to match Apertif layout)
        # RA (only row 3 and -3 from center, maybe more?)
        if row % 3 == 0:
            dRA -= shift * np.sign(dRA)
        # DEC (every odd row from center)
        if col % 2 == 1:
            # odd row, shift DEC
            dDEC -= shift * np.sign(dDEC)
        # save
        tmpshift.append([dRA, dDEC])
    # choose RA DEC shift to apply
    if pol.upper() == 'X':
        radec_shift = tmpshift[0]
    elif pol.upper() == 'Y':
        radec_shift = tmpshift[1]
    else:
        radec_shift = np.average(tmpshift, axis=0)

    # apply offset
    newdec = coords.dec.degree + radec_shift[1]
    newra = coords.ra.degree + radec_shift[0] / np.cos(newdec * np.pi/180)
    newcoord = SkyCoord(newra, newdec, unit=[u.degree, u.degree])
    return newcoord



def start_survey(args):
    """Sets up a survey mode observation from the master node
    """

    # initialize parameters
    pars = {}
    # initialize coordinate overview
    coordinates = []
    # Load static configuration
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), CONFIG)
    with open(filename, 'r') as f:
        config = yaml.load(f)
    # replace @HOME@ by current users' home dir
    home_dir = os.path.expanduser('~')
    for key, value in config['general'].items():
        if isinstance(value, str):
            config['general'][key] = value.replace('@HOME@', home_dir)
            config['sc3'][key] = value.replace('@HOME@', home_dir)
            config['sc4'][key] = value.replace('@HOME@', home_dir)
    conf_sc = 'sc{:.0f}'.format(args.science_case)  # sc3 or sc4
    conf_mode = args.science_mode.lower()  # i+tab, iquv+tab, i+iab, iquv+iab
    # IQUV not yet supported
    if 'iquv' in conf_mode:
        log("ERROR: IQUV modes not yet supported")
        exit()
    # science case specific
    pars['usemac'] = args.mac
    pars['science_case'] = args.science_case
    pars['time_unit'] = config[conf_sc]['time_unit']
    pars['nbit'] = config[conf_sc]['nbit']
    pars['nchan'] = config[conf_sc]['nchan']
    if args.mac:
        # could have non-zero starting subband
        pars['freq'] = config[conf_sc]['freq'] + config[conf_sc]['first_subband'] * pars['time_unit'] * 1E-6
    else:
        pars['freq'] = config[conf_sc]['freq']
    pars['bw'] = config[conf_sc]['bw']
    pars['nbeams'] = config[conf_sc]['nbeams']
    pars['missing_beams'] = config[conf_sc]['missing_beams']
    pars['nbuffer'] = config[conf_sc]['nbuffer']
    pars['valid_modes'] = config[conf_sc]['valid_modes']
    pars['network_port_start'] = config[conf_sc]['network_port_start']
    pars['tsamp'] = config[conf_sc]['tsamp']
    pars['pagesize'] = config[conf_sc]['pagesize']
    pars['fits_templates'] = config[conf_sc]['fits_templates']
    # pol and beam specific
    pars['ntabs'] = config[conf_mode]['ntabs']
    pars['science_mode']  = config[conf_mode]['science_mode']
    # derived values
    pars['chan_width'] = float(pars['bw']) / pars['nchan']
    pars['min_freq'] = pars['freq'] - pars['bw'] / 2 + pars['chan_width'] / 2
    if args.obs_mode == 'survey':
        pars['nreader'] = 5
    elif args.obs_mode == 'amber':
        pars['nreader'] = 3
    else:
        pars['nreader'] = 1

    # load observation specific arguments
    pars['proctrigger'] = args.proctrigger
    pars['amber_mode'] = args.amber_mode
    pars['snrmin'] = args.snrmin
    pars['source'] = args.source
    pars['ra'] = args.ra
    pars['dec'] = args.dec.replace('m', '-')
    # Observing time, has to be multiple of 1.024 seconds
    pars['nbatch'] = int(np.ceil(args.duration / 1.024))
    pars['tobs'] = pars['nbatch'] * 1.024
    # start time
    if args.tstart == 'default':
        # start in 30 s
        starttime = Time.now() + TimeDelta(30, format='sec')
    else:
        #starttime = Time(args.tstart, format='iso', scale='utc')
        log("Specific start time not yet supported")
        exit()  

    #Time(pars['utcstart'], format='iso', scale='utc')
    # round to multiple of 1.024 s since epoch
    unixstart = round(starttime.unix / 1.024) * 1.024
    starttime = Time(unixstart, format='unix')
    # delta=0 means slightly less accurate (~10arcsec), but no need for internet
    starttime.delta_ut1_utc = 0

    pars['utcstart'] = starttime.datetime.strftime('%Y-%m-%d-%H:%M:%S')
    pars['date'] = starttime.datetime.strftime("%Y%m%d")
    pars['datetimesource'] = "{}.{}".format(pars['utcstart'].replace(' ','-'), pars['source'])
    pars['mjdstart'] = starttime.mjd
    # startpacket has to be along
    #pars['startpacket'] = long(starttime.unix) * pars['time_unit']
    pars['startpacket'] = "{:.0f}".format(starttime.unix * pars['time_unit'])
    # output directories
    pars['master_dir'] = config[conf_sc]['master_dir'].format(**pars)
    pars['output_dir'] = config[conf_sc]['output_dir'].format(**pars)
    pars['log_dir'] = config[conf_sc]['log_dir'].format(**pars)
    pars['amber_dir'] = config[conf_sc]['amber_dir'].format(**pars)
    # observing mode
    if args.obs_mode not in pars['valid_modes']:
        log("ERROR: observation mode not valid: {}".format(args.obs_mode))
        exit()
    else:
        pars['obs_mode'] = args.obs_mode
    # beams
    if not args.beams is None:
        pars['beams'] = [int(beam) for beam in args.beams.split(',')]
        # make sure each beams is present only once
        pars['beams'] = list(set(pars['beams']))
    else:
        pars['sbeam'] = args.sbeam
        if args.ebeam == 0:
            pars['ebeam'] = pars['sbeam']
        elif args.ebeam < pars['sbeam']:
            log("WARNING: ebeam cannot be smaller than sbeam. Setting ebeam to sbeam ({})".format(pars['sbeam']))
            pars['ebeam'] = pars['sbeam']
        else:
            pars['ebeam'] = args.ebeam
        pars['beams'] = range(pars['sbeam'], pars['ebeam']+1)
   
    # check validity of beams
    if min(pars['beams']) < 0:
        log("ERORR: CB index < 0 is impossible")
        exit()
    if max(pars['beams']) > pars['nbeams']-1:
        log("ERROR: CB index > {} is impossible".format(pars['nbeams']-1))
        exit()
    # remove the missing beams
    for beam in pars['missing_beams']:
        try:
            pars['beams'].remove(beam)
        except ValueError:
            # beam was not in list of beams anyway
            continue

    # we have all parameters now
    # create output dir on master node
    cmd = "mkdir -p {master_dir}/".format(**pars)
    os.system(cmd)
    log(cmd)

    #create psrdada header and config file for each beam
    # config file
    cfg = {}
    cfg['buffersize'] = pars['ntabs'] * pars['nchan'] * pars['pagesize']
    cfg['nbuffer'] = pars['nbuffer']
    cfg['nreader'] = pars['nreader']
    cfg['obs_mode'] = pars['obs_mode']
    cfg['startpacket'] = pars['startpacket']
    cfg['duration'] = pars['tobs']
    cfg['nbatch'] = pars['nbatch']
    cfg['output_dir'] = pars['output_dir']
    cfg['ntabs'] = pars['ntabs']
    cfg['amber_conf_dir'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), AMBERCONFDIR)
    cfg['amber_config'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), AMBERCONFIG)
    cfg['amber_dir'] = pars['amber_dir']
    cfg['log_dir'] = pars['log_dir']
    cfg['master_dir'] = pars['master_dir']
    cfg['snrmin'] = pars['snrmin']
    cfg['proctrigger'] = pars['proctrigger']
    cfg['amber_mode'] = pars['amber_mode']
    cfg['fits_templates'] = pars['fits_templates']
    cfg['min_freq'] = pars['min_freq']
    cfg['max_freq'] = pars['min_freq'] + pars['bw'] - pars['chan_width']
    cfg['usemac'] = pars['usemac']

    # load PSRDADA header template
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), TEMPLATE), 'r') as f:
        header_template = f.read()

    # define pointing coordinates
    coord = SkyCoord(pars['ra'], pars['dec'], unit=(u.hourangle, u.deg))
    # wsrt location required for alt/az calculation
    wsrt_lat = 52.915184*u.deg
    wsrt_lon = 6.60387*u.deg
    wsrt_loc = EarthLocation(lat=wsrt_lat, lon=wsrt_lon, height=0*u.m)

    for beam in pars['beams']:
        # add CB-dependent parameters
        cfg['beam'] = beam
        cfg['dadakey'] = pars['network_port_start'] + beam
        cfg['network_port'] = pars['network_port_start'] + beam
        cfg['header'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), NODEHEADER.format(beam))

        # save to file
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), NODECONFIG.format(beam))
        with open(filename, 'w') as f:
            yaml.dump(cfg, f, default_flow_style=False)

        # save the coordinates of the beams
        this_cb_coord = pointing_to_CB_pos(beam, coord)
        gl, gb = this_cb_coord.galactic.to_string(precision=8).split(' ')
        altaz = this_cb_coord.transform_to(AltAz(obstime=starttime, location=wsrt_loc))
        az = altaz.az.deg
        za = 90 - altaz.alt.deg
        ra = this_cb_coord.ra.to_string(unit=u.hourangle, sep=':', pad=True, precision=1)
        dec = this_cb_coord.dec.to_string(unit=u.degree, sep=':', pad=True, precision=1)
        coordinates.append(["{:02d}".format(beam), ra, dec, gl, gb])
        # get LST start in seconds
        lststart = starttime.sidereal_time('mean', wsrt_lon).to(u.arcsecond).value / 15

        # fill in the psrdada header keys 
        temppars = pars.copy()
        temppars['ra'] = ra.replace(':', '')
        temppars['ra_hms'] = ra
        temppars['dec'] = dec.replace(':', '')
        temppars['dec_hms'] = dec
        temppars['lst_start'] = lststart
        temppars['az_start'] = az
        temppars['za_start'] = za
        temppars['resolution'] = pars['pagesize'] * pars['nchan']
        temppars['bps'] = int(pars['pagesize'] * pars['nchan'] / 1.024)
        temppars['beam'] = beam

        header = header_template.format(**temppars)

        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), NODEHEADER.format(beam)), 'w') as f:
            f.write(header)

    # save coordinate overview to disk
    filename = os.path.join(pars['master_dir'], COORD)
    with open(filename, 'w') as f:
        for line in coordinates:
            f.write(' '.join(line)+'\n')

    # save obs info to disk
    info = {}
    for key in ['utcstart', 'source', 'tobs']:
        info[key] = pars[key]
    # get MW DMs
    # YMW16
    # mode, Gl, Gb, dist(pc), dist->DM. 1E6 pc should cover entire MW
    cmd = "ymw16 Gal {} {} 1E6 2 | awk '{{print $8}}'".format(*coord.galactic.to_string(precision=8).split(' '))
    log(cmd)
    ymw16_dm = subprocess.check_output(cmd, shell=True)
    try:
        ymw16_dm = str(float(ymw16_dm))
    except ValueError:
        ymw16_dm = "-"
    info['ymw16'] = ymw16_dm
    filename = os.path.join(pars['master_dir'], INFO)
    with open(filename, 'w') as f:
        yaml.dump(info, f, default_flow_style=False)

    # TEMP copy the nodes config
    #log("Copying files to nodes")
    #for beam in pars['beams']:
    #    node = beam + 1
    #    cmd = "scp -r nodes/ arts0{:02d}.apertif:ARTS-obs/ >/dev/null &".format(node)
    #    os.system(cmd)
    #sleep(2)
    #log("Done")

    # Start the node scripts
    script_path = os.path.realpath(os.path.dirname(__file__))
    for beam in pars['beams']:
        node = beam + 1
        node_script = os.path.join(script_path, "start_survey_node.py")
        cmd = "{} nodes/CB{:02d}.yaml".format(node_script, beam)
        run_on_node(node, cmd, background=True)

    sleep(1)
    # done
    log("All nodes started for observation")

    # start the trigger listener + emailer NOTE: this is the only command that keeps running in the foreground during the obs
    if pars['proctrigger']:
        email_script = os.path.join(script_path, "emailer.py")
        cmd = "sleep {tobs}; python {email_script} {master_dir} '{beams}'".format(email_script=email_script, **pars)
        log(cmd)
        os.system(cmd)


        

if __name__ == '__main__':
    warnings.filterwarnings('ignore', category=UnicodeWarning)
    # check if this is the master node
    hostname = socket.gethostname()
    if not hostname == "arts041":
        log("ERROR: an observation should be started from the master node (arts041)")
        exit()

    parser = argparse.ArgumentParser(description="Start a survey mode observation on ARTS")
    # source info
    parser.add_argument("--source", type=str, help="Source name " \
                            "(Default: None)", default="None")
    parser.add_argument("--ra", type=str, help="J2000 RA in hh:mm:ss.s format " \
                            "(Default: 00:00:00)", default="00:00:00")
    parser.add_argument("--dec", type=str, help="J2000 DEC in dd:mm:ss.s format " \
                            "(Default: 00:00:00)", default="00:00:00")
    # time related
    parser.add_argument("--duration", type=float, help="Observation duration in seconds " \
                            "(Default: 10.24)", default=10.24)
    parser.add_argument("--tstart", type=str, help="Start time (UTC), e.g. 2017-01-01 00:00:00 " \
                            "(Default: now + 30 seconds)", default="default")
    # either start and end beam or list of beams: make beams and sbeam mutually exclusive
    beamgroup = parser.add_mutually_exclusive_group()
    beamgroup.add_argument("--sbeam", type=int, help="No of first CB to record " \
                            "(Default: 21)", default=21)
    beamgroup.add_argument("--beams", type=str, help="List of beams to process. Use instead of sbeam and ebeam")
    parser.add_argument("--ebeam", type=int, help="No of last CB to record " \
                            "(Default: same as sbeam)", default=0)
    # observing modes
    parser.add_argument("--obs_mode", type=str, help="Observation mode. Can be dump, scrub, fil, fits, amber, survey" \
                            "(Default: fil)", default="fil")
    parser.add_argument("--science_case", type=int, help="Science case " \
                            "(Default: 4)", default=4)
    parser.add_argument("--science_mode", type=str, help="Science mode. Can be I+TAB, IQUV+TAB, I+IAB, IQUV+IAB " \
                            "(Default: I+IAB)", default="I+IAB")
    # amber and trigger processing
    parser.add_argument("--amber_mode", type=str, help="AMBER dedispersion mode, can be bruteforce or suband " \
                            "(Default: subband)", default="subband")
    parser.add_argument("--snrmin", type=float, help="AMBER minimum S/N " \
                            "(Default: 10)", default=10)
    parser.add_argument("--proctrigger", help="Process and email triggers. "\
                            "(Default: False)", action="store_true")
    # MAC
    parser.add_argument("--mac", help="Using MAC. Enables beamlet reordering and non-zero starting subband. " \
                            "(Default: False)", action="store_true")

    # make sure dec does not start with -
    try:
        decind = sys.argv.index('--dec')
    except ValueError:
        # dec not in args
        pass
    else:
        sys.argv[decind+1] = sys.argv[decind+1].replace('-', 'm')

    args = parser.parse_args()

    # even if using only defaults, user should supply at least one argument
    # to prevent accidental observations
    if len(sys.argv) == 1:
        print "Please provide at least one argument"
        parser.print_help()
        exit()

    # proctrigger is only valid in survey mode
    if args.proctrigger and not args.obs_mode == 'survey':
        print "ERROR: proctrigger can only be used in survey mode"
        exit()

    start_survey(args)
