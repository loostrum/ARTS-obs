#!/usr/bin/env python
#
# Script to set up a full survey mode observation on the ARTS cluster
# Should only be used on the master node
# Author: L.C. Oostrum

import os
import sys
import argparse
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
CHECKBSN = "utilities/get_init_bsn.sh"
CBOFFSETS = "square_39p1.cb_offsets"


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
    else:
        ssh_cmd = "ssh {} {}".format(hostname, command)
    log("Executing '{}'".format(ssh_cmd))
    os.system(ssh_cmd)


def log(message):
    """
    Log a message. Prints the hostname, then the message
    """
    print "Master: {}".format(message)


def pointing_to_CB_pos(CB, coord):
    """
    Convert dish pointing to RA and DEC of specified CB
    CB: number of CB to get position of
    coords: astropy.coordinates.SkyCoord object with dish pointing
    returns: SkyCoord object with shifted coordinates
    """

    # load offsets file
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), CBOFFSETS)
    raw_offsets = np.loadtxt(filename, dtype=str, delimiter=',')
    offsets = {}
    radec_shift = None
    for key, dRA, dDec in raw_offsets:
        # keys are like compoundBeam.0.offset
        this_cb = int(key.split('.')[1])
        if this_cb == int(CB):
            dRA = float(dRA.strip())
            dDec = float(dDec.strip())
            radec_shift = [dRA, dDec]

    if radec_shift is None:
        log("CB not found in cb_offsets file: {}. Returning input coordinates".format(CB))
        return coord

    # apply offset
    newdec = coord.dec.degree + radec_shift[1]
    newra = coord.ra.degree + radec_shift[0] / np.cos(newdec * np.pi/180)
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
    conf_sc = 'sc{:.0f}'.format(args.science_case)  # sc3 or sc4
    conf_mode = args.science_mode.lower()  # i+tab, iquv+tab, i+iab, iquv+iab
    # IQUV not yet supported
    if 'iquv' in conf_mode:
        log("ERROR: IQUV modes not yet supported")
        exit()
    # save user home dir
    pars['home'] = os.path.expanduser('~')
    # science case specific
    pars['affinity'] = config['affinity']
    pars['usemac'] = args.mac
    pars['parset'] = args.parset
    pars['science_case'] = args.science_case
    pars['time_unit'] = config[conf_sc]['time_unit']
    pars['nbit'] = config[conf_sc]['nbit']
    pars['nchan'] = config[conf_sc]['nchan']
    pars['pulsar'] = args.pulsar
    pars['ingest_to_archive'] = args.ingest_to_archive
    # debug options
    pars['debug'] = args.debug
    if args.debug and not '{cb}' in args.dada_dir:
        log("WARNING: {cb} not present in dada_dir")
    pars['atdb'] = args.atdb
    if args.atdb:
        pars['taskid'] = args.taskid
    pars['dada_dir'] = args.dada_dir
    pars['bw'] = config[conf_sc]['bw']
    pars['nbeams'] = config[conf_sc]['nbeams']
    pars['missing_beams'] = config[conf_sc]['missing_beams']
    pars['nbuffer'] = config[conf_sc]['nbuffer']
    pars['hdr_size'] = config[conf_sc]['hdr_size']
    pars['valid_modes'] = config[conf_sc]['valid_modes']
    pars['network_port_start'] = config[conf_sc]['network_port_start']
    pars['tsamp'] = config[conf_sc]['tsamp']
    pars['page_size'] = config[conf_sc]['page_size']
    pars['fits_templates'] = config[conf_sc]['fits_templates'].format(**pars)
    # pol and beam specific
    pars['ntabs'] = config[conf_mode]['ntabs']
    pars['nsynbeams'] = config[conf_mode]['nsynbeams']
    pars['science_mode'] = config[conf_mode]['science_mode']

    # derived values
    pars['chan_width'] = float(pars['bw']) / pars['nchan']
    pars['min_freq'] = config[conf_sc]['freq_low'] + config[conf_sc]['first_subband'] * pars['time_unit'] * 1E-6
    pars['freq'] = pars['min_freq'] - .5*pars['time_unit']*1E-6 + 0.5*pars['bw']
    if args.obs_mode == 'survey':
        # filterbank + fits + 3x AMBER
        pars['nreader'] = 5
    elif args.obs_mode == 'amber':
        # 3x AMBER
        pars['nreader'] = 3
    elif args.obs_mode == 'record':
        # dadailfterbank + dadafits
        pars['nreader'] = 2
    else:
        # filterbank or fits or dbdisk or dbscrubber
        pars['nreader'] = 1

    # load observation specific arguments
    pars['proctrigger'] = args.proctrigger
    pars['amber_mode'] = args.amber_mode
    pars['snrmin_amber'] = args.snrmin_amber
    pars['snrmin_processing'] = args.snrmin_processing
    pars['snrmin_processing_local'] = args.snrmin_processing_local
    pars['dmmin'] = args.dmmin
    pars['dmmax'] = args.dmmax
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
        starttime = Time(args.tstart, scale='utc')
        if ((starttime - Time.now()).sec < 30) and not pars['debug']:
            log("ERROR: start time should be at least 30 seconds in the future, got {}".format(starttime))
            exit()  

    # Time(pars['utc_start'], format='iso', scale='utc')
    # round to multiple of 1.024 s since sync time (=init bsn)
    # note: init bsn is multiple of 781250
    # then increases by 80000 every 1.024s
    # simply use user-provided value in debug mode
    if not pars['debug']:
        cmd = os.path.join(os.path.dirname(os.path.realpath(__file__)), CHECKBSN)
        try:
            init_bsn = float(subprocess.check_output(cmd).strip())
        except Exception:
            log("ERROR: Could not get init bsn from ccu-corr")
            exit()
        init_unix = init_bsn / pars['time_unit']
        unixstart = round((starttime.unix-init_unix) / 1.024) * 1.024 + init_unix
        delta_bsn = (unixstart - init_unix) * pars['time_unit']
        pars['startpacket'] = "{:.0f}".format(init_bsn + delta_bsn)
    else:
        unixstart = starttime.unix
        pars['startpacket'] = "{:.0f}".format(unixstart * pars['time_unit'])
    starttime = Time(unixstart, format='unix')
    # delta=0 means slightly less accurate (~10arcsec), but no need for internet
    starttime.delta_ut1_utc = 0
    endtime = starttime + TimeDelta(pars['tobs'], format='sec')

    pars['endtime'] = endtime.datetime.strftime('%Y-%m-%d %H:%M:%S')
    pars['utc_start'] = starttime.datetime.strftime('%Y-%m-%d-%H:%M:%S')
    pars['date'] = starttime.datetime.strftime("%Y%m%d")
    pars['datetimesource'] = "{}.{}".format(pars['utc_start'], pars['source'])
    pars['mjd_start'] = starttime.mjd
    pars['debug_dir'] = config[conf_sc]['debug_dir']
    # change output directories in debug mode
    if args.debug:
        config[conf_sc]['output_dir'] = '{debug_dir}/output/'.format(**pars)
        config[conf_sc]['amber_dir'] = '{debug_dir}/output/amber'.format(**pars)
        config[conf_sc]['log_dir'] = '{debug_dir}/output/log'.format(**pars)
        config[conf_sc]['master_dir'] = '{debug_dir}/output/results'.format(**pars)
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
    if args.beams is not None:
        pars['beams'] = [int(beam) for beam in args.beams.split(',')]
        # make sure each beam is present only once
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

    # create psrdada header and config file for each beam
    # config file
    cfg = {}
    cfg['buffersize'] = pars['ntabs'] * pars['nchan'] * pars['page_size']
    cfg['nbuffer'] = pars['nbuffer']
    cfg['nreader'] = pars['nreader']
    cfg['obs_mode'] = pars['obs_mode']
    cfg['startpacket'] = pars['startpacket']
    cfg['endtime'] = pars['endtime']
    cfg['duration'] = pars['tobs']
    cfg['nbatch'] = pars['nbatch']
    cfg['output_dir'] = pars['output_dir']
    cfg['ntabs'] = pars['ntabs']
    cfg['nsynbeams'] = pars['nsynbeams']
    cfg['amber_conf_dir'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), AMBERCONFDIR)
    cfg['amber_config'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), AMBERCONFIG)
    cfg['amber_dir'] = pars['amber_dir']
    cfg['log_dir'] = pars['log_dir']
    cfg['master_dir'] = pars['master_dir']
    cfg['snrmin_amber'] = pars['snrmin_amber']
    cfg['snrmin_processing'] = pars['snrmin_processing']
    cfg['snrmin_processing_local'] = pars['snrmin_processing_local']
    cfg['dmmin'] = pars['dmmin']
    cfg['dmmax'] = pars['dmmax']
    cfg['proctrigger'] = pars['proctrigger']
    cfg['amber_mode'] = pars['amber_mode']
    cfg['fits_templates'] = pars['fits_templates']
    cfg['min_freq'] = pars['min_freq']
    cfg['max_freq'] = pars['min_freq'] + pars['bw'] - pars['chan_width']
    cfg['usemac'] = pars['usemac']
    cfg['affinity'] = pars['affinity']
    cfg['page_size'] = pars['page_size']
    cfg['hdr_size'] = pars['hdr_size']
    cfg['pulsar'] = pars['pulsar']
    cfg['debug'] = pars['debug']
    cfg['atdb'] = pars['atdb']
    if pars['atdb']:
        cfg['taskid'] = pars['taskid']

    # load PSRDADA header template
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), TEMPLATE), 'r') as f:
        header_template = f.read()

    # define pointing coordinates
    coord = SkyCoord(pars['ra'], pars['dec'], unit=(u.hourangle, u.deg))
    # wsrt location required for alt/az calculation
    wsrt_lat = 52.915184*u.deg
    wsrt_lon = 6.60387*u.deg
    wsrt_loc = EarthLocation(lat=wsrt_lat, lon=wsrt_lon, height=0*u.m)
    # load the parset
    if not pars['parset'] == '':
        with open(pars['parset']) as f:
            parset = f.read().encode('bz2').encode('hex')
            if len(parset) > 24575:
                log("Error: compressed parset is longer than maximum for header (24575 characters)")
                exit()
    else:
        parset = 'no parset'

    for beam in pars['beams']:
        # add CB-dependent parameters
        cfg['beam'] = beam
        cfg['dadakey'] = pars['network_port_start'] + beam
        cfg['network_port'] = pars['network_port_start'] + beam
        cfg['header'] = os.path.join(os.path.dirname(os.path.realpath(__file__)), NODEHEADER.format(beam))
        if cfg['debug']:
            cfg['dada_dir'] = pars['dada_dir'].replace('{cb}', '{:02d}'.format(beam))

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
        temppars['resolution'] = pars['page_size'] * pars['nchan'] * pars['ntabs']
        temppars['file_size'] = pars['page_size'] * pars['nchan'] * pars['ntabs'] * 10  # 10 pages per file
        temppars['bps'] = int(pars['page_size'] * pars['nchan'] * pars['ntabs'] / 1.024)
        temppars['beam'] = beam
        temppars['parset'] = parset
        temppars['scanlen'] = pars['tobs']
        temppars['hdr_size'] = pars['hdr_size']

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
    for key in ['utc_start', 'source', 'tobs']:
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

    # start the trigger listener + emailer
    if pars['proctrigger']:
        email_script = os.path.join(script_path, "emailer.py")
        cmd = "(sleepuntil_utc {endtime}; python {email_script} {master_dir} '{beams}') &".format(email_script=email_script, **pars)
        log(cmd)
        os.system(cmd)

    # start the completion checker for ATDB
    if pars['atdb']:
        check_complete_script = os.path.join(script_path, "utilities/check_obs_complete.py")
        cmd = "(sleepuntil_utc {endtime}; sleep 15; python {check_complete_script} --date {date} --obs {datetimesource} --cbs '{beams}' --taskid {taskid}) &".format(check_complete_script=check_complete_script, **pars)
        log(cmd)
        os.system(cmd)

    # start the archiver
    if pars['ingest_to_archive']:
        archiver_script = os.path.join(script_path, "utilities/copy_to_alta.py")
        cmd = "(sleepuntil_utc {endtime}; sleep 10; {archiver_script} --date {date} --obs {datetimesource} --cbs '{beams}') &".format(archiver_script=archiver_script, **pars)
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
    parser.add_argument("--source", type=str, help="Source name "
                        "(Default: None)", default="None")
    parser.add_argument("--ra", type=str, help="J2000 RA in hh:mm:ss.s format "
                        "(Default: 00:00:00)", default="00:00:00")
    parser.add_argument("--dec", type=str, help="J2000 DEC in dd:mm:ss.s format "
                        "(Default: 00:00:00)", default="00:00:00")
    # time related
    parser.add_argument("--duration", type=float, help="Observation duration in seconds "
                        "(Default: 10.24)", default=10.24)
    parser.add_argument("--tstart", type=str, help="Start time (UTC), e.g. 2017-01-01 00:00:00 "
                        "(Default: now + 30 seconds)", default="default")
    # either start and end beam or list of beams: make beams and sbeam mutually exclusive
    beamgroup = parser.add_mutually_exclusive_group()
    beamgroup.add_argument("--sbeam", type=int, help="No of first CB to record "
                           "(Default: 21)", default=21)
    beamgroup.add_argument("--beams", type=str, help="List of beams to process. Use instead of sbeam and ebeam")
    parser.add_argument("--ebeam", type=int, help="No of last CB to record "
                        "(Default: same as sbeam)", default=0)
    # observing modes
    parser.add_argument("--obs_mode", type=str, help="Observation mode. Can be dump, scrub, fil, fits, amber, survey "
                        "(Default: fil)", default="fil")
    parser.add_argument("--science_case", type=int, help="Science case "
                        "(Default: 4)", default=4)
    parser.add_argument("--science_mode", type=str, help="Science mode. Can be I+TAB, IQUV+TAB, I+IAB, IQUV+IAB "
                        "(Default: I+IAB)", default="I+IAB")
    # amber and trigger processing
    parser.add_argument("--amber_mode", type=str, help="AMBER dedispersion mode, can be bruteforce or suband "
                        "(Default: subband)", default="subband")
    parser.add_argument("--snrmin_amber", type=float, help="AMBER minimum S/N "
                        "(Default: 10)", default=10)
    parser.add_argument("--proctrigger", help="Process and email triggers. "
                        "(Default: False)", action="store_true")
    parser.add_argument("--snrmin_processing", type=float, help="Trigger processing minimum S/N "
                        "(Default: 10)", default=10)
    parser.add_argument("--snrmin_processing_local", type=float, help="Trigger processing local minimum S/N after clustering"
                        "(Default: 7)", default=7)
    parser.add_argument("--dmmin", type=float, help="Trigger processing minimum DM "
                        "(Default: 20)", default=20)
    parser.add_argument("--dmmax", type=float, help="Trigger processing maximum DM "
                        "(Default: 5000)", default=5000)
    # MAC
    parser.add_argument("--mac", help="Using MAC. Enables beamlet reordering and non-zero starting subband "
                        "(Default: False)", action="store_true")
    # Parset
    parser.add_argument("--parset", type=str, help="Path to parset of this observation "
                            "(Default: no parset)", default='')
    # test pulsar mode
    parser.add_argument("--pulsar", help="Test pulsar mode. Creates prepfold plot after observation "
                            "(Default: False)", action="store_true")
    # ALTA
    parser.add_argument("--ingest_to_archive", help="Ingest to ALTA "
                            "(Default: False)", action="store_true")
    # ATDB connection to add dataproducts
    parser.add_argument("--atdb", help="Enable connection to ATDB "
                            "(Default: False)", action="store_true")
    parser.add_argument("--taskid", type=str, help="Task ID "
                            "(Default: None)", default="None")
    # debug mode; read from disk instead of network
    parser.add_argument("--debug", help="Debug mode: read from disk intead of network "
                            "(Default: False)", action="store_true")
    parser.add_argument("--dada_dir", type=str, help="Path to dada files to read in debug mode with {cb} for CB number, e.g. /home/arts/debugfiles/CB{cb}/dada", default='')

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

    # dada_dir is required in debug mode
    if args.debug and not args.dada_dir:
        print "ERROR: dada_dir is required in debug mode"
        exit()

    # taskid is required if ATDB is enabled
    if args.atdb and args.taskid == "None":
        print "ERROR: taskid is required if ATDB is enabled"
        exit()

    start_survey(args)
