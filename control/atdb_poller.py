#!/usr/bin/env python
#
# This script actively polls ATDB and schedules
# upcoming observations on the ARTS cluster

import sys
import os
import requests
import json
import logging
import signal
import errno
import subprocess
from time import sleep, gmtime

import numpy as np
from astropy.time import Time, TimeDelta
from astropy.coordinates import SkyCoord
import astropy.units as u

# interval for cheking new observations
INTERVAL= 60
# how long before start time to start obs (must be more than INTERVAL)
STARTUPTIME = 120
# main dir
ROOTDIR = '{home}/observations/atdb_poller'.format(home=os.path.expanduser('~'))
# log file
LOGFILE = '{}/atdb_poller.log'.format(ROOTDIR)
# file with taskids
OBSFILE = '{}/observations.txt'.format(ROOTDIR)
# folder for parsets
PARSETDIR = '{}/parsets'.format(ROOTDIR)
# lock to ensure only one instance is running
LOCKFILE = '{}/.lock'.format(ROOTDIR)


# From Vanessa's ATDBQuery (https://github.com/cosmicpudding/atdbquery)
def query_database(obs_mode='sc4'):
    """
    Query ATDB database
    arguments:
        obs_mode: sc1 / sc4 / imaging
    returns
        success: bool
        obs_list: list
    """

    # Define the URL for query
    url = 'http://atdb.astron.nl/atdb/observations/?my_status__in=defined,scheduled,starting,running&observing_mode__icontains={}'.format(obs_mode)

    # First, determine how many results there are
    # Do the query
    try: 
        response = requests.get(url)
    except Exception as e:
        logging.error('Error getting data from ATDB: {}'. format(e))
        return False, []

    # Can only do 100 per page
    result_num = json.loads(response.text)['count']
    logging.info('Total number of results found in ATDB with status in [defined, scheduled, starting, running] for {}: {}'.format(obs_mode.upper(),result_num))
    pagenum = result_num // 100
    if result_num % 100 != 0:
        pagenum += 1

    # Define the observation list
    obs_list = []

    for page in range(1,pagenum+1):
        url = 'http://atdb.astron.nl/atdb/observations/?my_status__in=defined,scheduled,starting,running&observing_mode__icontains={}&page={}'.format(obs_mode,page)

        # Do the query
        try: 
            response = requests.get(url)
        except Exception as e:
            logging.error('Error getting data from ATDB: {}'. format(e))
            return False, []

        # Parse the data
        metadata = json.loads(response.text)['results']

        # Return all information
        for i in range(0,len(metadata)):
            obs_list.append(metadata[i])

    return True, np.array(obs_list)


def remove_lockfile():
    """
    Remove the lock file
    """
    if os.path.isfile(LOCKFILE):
        try:
            os.remove(LOCKFILE)
        except Exception as e:
            logging.error('Failed to remove lock file: {}'.format(e))
    else:
            logging.error('Failed to remove lock file: it did not exist')
    return


def signal_handler(sig, frame):
    """
    Handle exit
    """
    signal_num_to_name = dict((k, v) for v, k in reversed(sorted(signal.__dict__.items()))
                             if v.startswith('SIG') and not v.startswith('SIG_'))
    sig_name = signal_num_to_name.get(sig, 'Unknown signal {}'.format(sig))
    logging.info('Received signal: {}'.format(sig_name))
    remove_lockfile()
    logging.info('Exiting')
    sys.exit(1)


def gen_obs_command(obs):
    """
    Generate ARTS cluster observation command
    """
    template = ". $HOME/software/ARTS-obs/setup_env.sh; start_obs --source {src} --ra {ra} --dec {dec} --tstart {tstart} --duration {duration} --sbeam 0 --ebeam 39 --atdb --taskid {taskid} --science_mode {science_mode} --obs_mode {obs_mode} {other} 2>&1 > {taskid}.log &"

    # command options
    kwargs = {'src': obs['field_name'], 
              'taskid': obs['taskID'],
              'other': ''}

    pulsars = ['B1933+16', 'B0950+08', 'B0531+21', 'B0329+54']

    # Add coordinates
    # Convert to hms/dms instead of decimal degree
    coord = SkyCoord(obs['field_ra'], obs['field_dec'], unit=u.degree)
    kwargs['ra'] = coord.ra.to_string(unit=u.hourangle, sep=':', pad=True)
    kwargs['dec'] = coord.dec.to_string(unit=u.degree, sep=':', pad=True)

    # Add start time and duration
    kwargs['tstart'] = obs['starttime'].replace(' ', 'T')
    kwargs['duration'] = obs['duration']

    # Add modes
    kwargs['obs_mode'] = obs['observing_mode'].split('_')[-1]
    kwargs['science_mode'] = 'i+' + obs['science_mode'].lower()

    # Add pulsar option
    if kwargs['src'] in pulsars:
        kwargs['other'] += ' --pulsar'

    # Add processing option
    if kwargs['obs_mode'] == 'survey': #and kwargs['science_mode'] == 'i+iab':
        kwargs['other'] += ' --proctrigger'

    # Try getting the parset
    parset_source_path = 'ccu-corr.apertif:/opt/apertif/share/parsets/{taskid}.parset'.format(**kwargs)
    parset_target_path = os.path.join(PARSETDIR, '{taskid}.parset'.format(**kwargs))
    cmd = ['scp', parset_source_path, parset_target_path]
    have_parset = True
    try:
        subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        logging.warning("Failed to get parset from ccu-corr: {}".format(e))
        have_parset = False
    # Check if the parset is really there
    if not os.path.isfile(parset_target_path):
        have_parset = False

    # Add the parset option
    if have_parset:
        kwargs['other'] += ' --parset {}'.format(parset_target_path)

    return template.format(**kwargs)


def check_and_start_obs():
    """
    Check for observations and start as needed
    """
    # Check ATDB
    success, obs_list = query_database()
    if not success:
        logging.warning('Failed to query ATDB, tryin again')
        success, obs_list = query_database()
        if not success:
            logging.error('Still failed to query ATDB, giving up')
            return

    if len(obs_list) == 0:
        logging.info("No new observations found")
        return 

    # Keys we get from ATDB:
    # [u'node', u'start_band', u'number_of_bins', u'my_status', u'skip_auto_ingest', u'duration', u'generated_dataproducts', u'id', u'beamPattern', u'task_type', u'science_mode', u'control_parameters', u'new_status', u'process_type', u'observing_mode', u'field_beam', u'taskID', u'field_dec', u'field_ra', u'integration_factor', u'endtime', u'field_name', u'telescopes', u'data_location', u'name', u'par_file_name', u'creationTime', u'status_history', u'starttime', u'parset_location', u'central_frequency', u'irods_collection', u'end_band']

    # Sort by taskid
    taskids = np.array([obs['taskID'] for obs in obs_list], dtype=int)
    order = np.argsort(taskids)
    obs_list = obs_list[order]

    # "defined" observations are only ok for drift scan mode, i.e. "drift" has to be in name"
    sources = np.array([obs['field_name'] for obs in obs_list])
    states = np.array([obs['my_status'] for obs in obs_list])
    # check for drift in name and state is defined
    is_driftscan = np.array(['drift' in source.lower() for source in sources])
    is_defined = np.array([state == 'defined' for state in states])
    # remove observations that are defined but not drift scan
    to_keep = is_defined & ~is_driftscan
    obs_list = obs_list[to_keep]

    # Find start time relative to now in seconds
    now = Time.now()
    start_times = np.array([(Time(obs['starttime']) - now).sec for obs in obs_list])
    # Find next obs
    # ignore past observations
    start_times[start_times < 0] = 1E9
    next_obs_ind = np.argmin(start_times)
    next_obs = obs_list[next_obs_ind]

    # Check if start time is within 2 minutes
    if (Time(next_obs['starttime']) - Time.now()).sec <= STARTUPTIME:
        logging.info('Observation {} starting within {:.1f} minutes'.format(next_obs['taskID'], STARTUPTIME/60.))
    else:
        logging.info('No observation starting within {:.1f} minutes'.format(STARTUPTIME/60.))
        return

    # find previous obs
    # is just previous in list because it's already sorted by taskID
    # next obs might be first in list, which means all previous ones are done/archived
    if next_obs_ind != 0:
        prev_obs = obs_list[next_obs_ind - 1]
        # check if endtime is in the future
        if Time(prev_obs['endtime']) > Time.now():
            logging.info("Previous observation not yet finished")
            return
    else:
        logging.info('No previous observation found')

    # Check if obs was already started
    with open(OBSFILE, 'r') as f:
        raw_obs = f.read()
    started_obs = raw_obs.strip().split()
    next_obs_id = next_obs['taskID']
    if str(next_obs['taskID']) in started_obs:
        logging.info("Observation {} was already started".format(next_obs['taskID']))
        return

    # start the obs
    logging.info('Starting observation {}'.format(next_obs['taskID']))
    command = gen_obs_command(next_obs)
    logging.info('Running command: {}'.format(command))
    os.system(command)

    # Add the taskid of the started obs to the obs file
    with open(OBSFILE, 'a') as f:
        f.write(str(next_obs_id)+'\n')

    return


if __name__ == '__main__':
    # Create root dir
    try:
        os.makedirs(ROOTDIR)
    except OSError as e:
        if e.errno != errno.EEXIST:
            sys.stderr.write('Cannot create root directory: {}\n'.format(e))
            logging.info('Exiting')
            sys.exit(1)

    # Create parset dir
    try:
        os.makedirs(PARSETDIR)
    except OSError as e:
        if e.errno != errno.EEXIST:
            sys.stderr.write('Cannot create parset directory: {}\n'.format(e))
            logging.info('Exiting')
            sys.exit(1)

    # Create lock file
    if os.path.isfile(LOCKFILE):
        sys.stderr.write('Lock file already exists\n')
        sys.stderr.write('Is another instance of atdb_poller already running?\n')
        sys.stderr.write('If not: manually remove the lock file: {}\n'.format(LOCKFILE))
        sys.stderr.write('Exiting\n')
        sys.exit(1)
    else:
        try:
            with open(LOCKFILE, 'wr'):
                pass
        except IOError as e:
            sys.stderr.write('Failed to create lock file: {}\n'.format(e))
            sys.stderr.write('Exiting\n')
            sys.exit(1)

    # setup logger
    logging.basicConfig(format='%(asctime)s - %(levelname)s: %(message)s', 
                        level=logging.DEBUG, filename=LOGFILE)
    # set to UTC
    logging.Formatter.converter = gmtime

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # main loop
    next_check_time = Time.now()
    while True:
        # wait until next check
        while Time.now() < next_check_time:
            sleep(1)
        # start the check
        logging.info('Starting next check')
        try:
            check_and_start_obs()
        except Exception as e:
            logging.error('Caught Exception: {}'.format(e))

        next_check_time += TimeDelta(INTERVAL, format='sec')
        logging.info("Check done, sleeping util {}".format(next_check_time))
