#!/usr/bin/env python
# Script to start IAB observation.
# Author: L. Oostrum

import optparse
import sys
import os
import datetime
from time import sleep
import subprocess

import numpy as np
from astropy.time import Time

class IAB(object):
    """Class for setting up an IAB FRB search observation.
    """

    # set all fixed values and directories
    headerdir = '/home/arts/sc4/header/'          # PSRDADA header directory
    output_dir = '/home/arts/sc4/searchoutput/'   # Output of AMBER goes here
    dbdisk_dir = '/data/{disk:02d}/IAB/'          # Output of dada_dbdisk goes here
    fil_dir = '/data/{disk:02d}/filterbank'       # Output of dadafilterbank goes here
    fits_dir = '/data/{disk:02d}/fits'            # Output of dadafits goes here
    log_dir = '/home/arts/sc4/log/'               # Logs go here
    conf_dir = '/home/arts/sc4/code/confs/'       # AMBER configuration files
    keyfile = headerdir + 'keys.txt'              # List of keys to use for ringbuffer
    fill_ringbuffer = '/home/arts/sc4/code/pipeline/ringbuffer/bin/fill_ringbuffer'
    amber = '/home/arts/sc4/code/pipeline/TransientSearch/bin/TransientSearch'
    dadafilterbank = '/home/arts/sc4/code/pipeline/dadafilterbank/dadafilterbank'
    dadafits = '/home/arts/sc4/code/pipeline/dadafits/dadafits'
    dadafits_template = '/home/arts/sc4/code/pipeline/dadafits/templates/sc34_1bit_I_reduced.txt'
    dadafilterbank_mode = 0  # IAB, 1 is TAB
    dadafits_mode = 2  # I+IAB
    killringbuffers = '/home/arts/sc4/code/IAB/kill_sc4_keys.sh'
    pointing_to_cb_position = '/home/arts/sc4/code/IAB/pointing_to_CB_position.py'
    nbit = 8
    tsamp = 40.96E-6
    sc = 4                       # Only science case 3 and 4 are supported.
    time_unit = 781250           # Timestamps are in units of 1/781250 seconds since 1970
    fill_ringbuffer_mode = 2     # 0=I+TAB, 1=IQUV+TAB, 2=I+IAB, 3=IQUV+IAB
    padded_size = 25000
    ringbuffer_size = 1536 * padded_size  # = Nchan * padded_size
    nbuffer = 5                  # number of spots in each buffer
    batchlen = 25000             # 25000 = 1.024 s, 25600 factorizes well for integration steps
    device_platform = 0
    device_name = 'ARTS'
    dm_first = 0.0
    dm_step = 0.2
    num_dm = 512
    subbands = 32
    subband_dm_first = 0.0
    subband_dms = 32
    subband_dm_step = subband_dms * dm_step

    nbeams = 40
    missing_beams = [4, 9, 14, 19, 24, 29, 34, 39] # these are reserved for 6 bit. Don't try to use them
    ports = np.arange(nbeams) + 5000
    with open(keyfile) as f:
        keys = f.read().split()

    # CB to data disk mapping, note every 5th CB is missing
    datadisks = [1, 1, 2, 2, None, 3, 3, 4, 4, None, 5, 5, 6, 6, None, 7, 7, 8, 8, None, 9, 9, 10, 10, None, \
                 11, 11, 12, 12, None, 13, 13, 14, 14, None, 15, 15, 16, 16, None]
    # TMP: CB 20 to disk 16, CB15 to disk 6
    #datadisks = [1, 1, 2, 2, None, 3, 3, 4, 4, None, 5, 5, 6, 6, None, 6, 7, 8, 8, None, 16, 9, 10, 10, None, \
    #             11, 11, 12, 12, None, 13, 13, 14, 14, None, 15, 15, 16, 16, None]
    # CBs still divided over all ifaces, so which core doesn't really matter.
    cpu_affil = np.array(range(1, 24) + range(1, 18))
    # CPU0 = even cores = GPU0. Bind AMBER to GPU @ same CPU
    gpu_affil = np.ones(nbeams).astype(int)
    gpu_affil[cpu_affil % 2 == 0] = 0

    # class to hold parameteres
    class pars_cls:
        bruteforce = False
        subband = False
        dump = False
        scrub = False
        fil = False
        fits = False
        dual = False
        key = None
        port = None
        tobs = None
        ra = None
        dec = None
        startutc = None
        startmjd = None
        startpacket = None
        nchan = 1536
        bw = 300
        freq = 1400
        chan_width = 300./1536
        min_freq = freq - bw / 2. #+ chan_width / 2.
        sbeam = None
        ebeam = None

    # class for logging
    class log_cls:
        path = None
        basefilename = None
        io = None
        ringbuffer = None
        search = None
        dump = None
        scrub = None
        fill_ringbuffer = None
        dadafilterbank = None
        dadafits = None


    def parse_args(self, args):
        if args.mode not in ['bruteforce', 'subband', 'dump', 'scrub', 'fil', 'fits']:
            sys.stderr.write('Error: observation mode not valid: {0}\n'.format(args.mode))
            sys.exit(1)
        pars = self.pars_cls()
        # obs mode
        if args.mode == 'bruteforce':
            pars.bruteforce = True
        if args.mode == 'subband':
            pars.subband = True
        if args.mode == 'dump':
            pars.dump = True
        if args.mode == 'scrub':
            pars.scrub = True
        if args.mode == 'fil':
            pars.fil = True
        if args.mode == 'fits':
            pars.fits = True
        if args.mode == 'dual':
            pars.dual = True
            pars.bruteforce = True
            pars.fil = True
        pars.source = args.source
        pars.snrmin = args.snrmin
        # round up obs time to integer number of ringbuffer pages
        #pars.tobs = pars.nbatch * self.batchlen * self.tsamp
        pars.tobs = np.ceil(args.tobs / 1.024) * 1.024
        # floor, so may skip part of last batch, which is <~1 second anyway. Important?
        pars.nbatch = np.floor(pars.tobs/(self.tsamp * self.batchlen)).astype(int)
        if args.tstart == 'default':
            tstart = datetime.datetime.utcnow() + datetime.timedelta(seconds=5)
            pars.startutc = tstart.strftime('%Y-%m-%d %H:%M:%S')
        else:
            pars.startutc = args.tstart
        start = Time(pars.startutc, format='iso', scale='utc')
        pars.date = '%04d%02d%02d' % tuple([int(el) for el in str(start.datetime).replace('-', ' ').split()[0:3]]) # Turn UTC into yyymmdd
        pars.datetimesource = '%04d.%02d.%02d-%02d:%02d:%02d.%s' % (tuple([int(el) for el in str(start.datetime).replace('-', ' ').replace(':', '     ').split()[0:6]])+(pars.source,))   # Turn UTC into yyyy.mm.dd-hh:mm:ss.source
        pars.startmjd = start.mjd
        pars.startpacket = start.unix * self.time_unit
        # beams: list or range
        if not args.beamrange == 'none':
            pars.beams = [ int(beam) for beam in args.beamrange.split(',') ]
        else:
            pars.sbeam = args.sbeam
            # ebeam default
            if args.ebeam == 0:
                pars.ebeam = pars.sbeam
            elif args.ebeam < pars.sbeam:
                print "WARNING: ebeam cannot be smaller than sbeam. Setting ebeam to sbeam ({})".format(pars.sbeam)
                pars.ebeam = pars.sbeam
            else:
                pars.ebeam = args.ebeam
            pars.beams = range(pars.sbeam, pars.ebeam+1)
        pars.ra = args.ra
        pars.dec = args.dec
        # remove the missing beams
        for beam in self.missing_beams:
            try: 
                pars.beams.remove(beam)
            except ValueError:
                # missing beam was not in list of beams anyway
                continue
        # LCO - tmp
        if pars.dump:
            if not args.beamrange == 'none':
                os.system("echo ~/sc4/code/IAB/convert_to_filterbank.py {} {} {} >> /home/arts/sc4/filterbank_cmds.txt".format(pars.date, pars.datetimesource, ','.join(map(str, pars.beams))))
            else:
                os.system("echo ~/sc4/code/IAB/convert_to_filterbank.py {} {} {} {} >> /home/arts/sc4/filterbank_cmds.txt".format(pars.date, pars.datetimesource, pars.sbeam, pars.ebeam))
        self.pars = pars


    def create_logs(self):
        log = self.log_cls()
        log.path = '{0}/{1}/{2}'.format(self.log_dir, self.pars.date, self.pars.datetimesource)
        os.system('mkdir -p {0}'.format(log.path))
        log.basename = '{0}/{1}'.format(log.path, self.pars.datetimesource)
        log.controller = '{0}.controller'.format(log.basename)

        log.ringbuffer = []
        log.fill_ringbuffer = []
        log.search = []
        log.dump = []
        log.scrub = []
        log.dadafilterbank = []
        log.dadafits = []

        for beam in range(self.nbeams):
            log.ringbuffer.append('{0}.ringbuffer.{1:02d}'.format(log.basename, beam))
            log.fill_ringbuffer.append('{0}.fill_ringbuffer.{1:02d}'.format(log.basename,beam))
            if self.pars.bruteforce or self.pars.subband or self.pars.dual:
                log.search.append('{0}.amber.{1:02d}'.format(log.basename, beam))
            elif self.pars.dump:
                log.dump.append('{0}.dada_dbdisk.{1:02d}'.format(log.basename, beam))
            elif self.pars.scrub:
                log.scrub.append('{0}.dada_dbscrubber.{1:02d}'.format(log.basename, beam))
            elif self.pars.fil or self.pars.dual:
                log.dadafilterbank.append('{0}.dadafilterbank.{1:02d}'.format(log.basename, beam))
            elif self.pars.fits:
                log.dadafits.append('{0}.dadafits.{1:02d}'.format(log.basename, beam))
        self.log = log
            

    def clean(self):
        sys.stdout.write('Removing old SC4 ringbuffers.\n')
        self.log.io.write(self.killringbuffers+'\n')
        # killing a non-existing buffer gives an error, we don't care about those
        os.system('{0} 2>/dev/null'.format(self.killringbuffers))
        # removing the ringbuffers makes any fill_ringbuffer connected to those keys stop too.
        #cmd = 'killall -u $(whoami) -9 fill_ringbuffer'
        #self.log.io.write(cmd+'\n')
        #os.system(cmd)
        #cmd = 'killall -u $(whoami) -9 AMBER'
        #self.log.io.write(cmd+'\n')
        #os.system(cmd)

    def create_header(self):
        sys.stdout.write('Creating header.\n')
        template = """HEADER       DADA
HDR_VERSION  1.0
HDR_SIZE     4096
DADA_VERION  1.0
PIC_VERSION  1.0
OBS_ID       0000000
PRIMARY      unset
SECONDARY    unset
FILE_NAME    IAB
FILE_SIZE    {fsize}
FILE_NUMBER  0
UTC_START    {utc_start}
MJD_START    {mjd_start}
OBS_OFFSET   0
OBS_OVERLAP  0
SOURCE       {source}
RA           {ra}
DEC          {dec}
TELESCOPE    WSRT
INSTRUMENT   ARTS0
FREQ         {freq}
BW           {bw}
TSAMP        {tsamp}
MIN_FREQUENCY {min_freq}
CHANNELS     {nchan}
NCHAN        {nchan}
CHANNEL_BANDWIDTH {chan_width}
SAMPLES_PER_BATCH {batchlen}
BEAM         {beam}
NBIT         {nbit}
NDIM         2
NPOL         2
IN_USE       1
RESOLUTION {resolution}
BYTES_PER_SECOND {bps}
"""

        bps = self.pars.nchan * 1./self.tsamp
        #filesize = int(10 * bps)  # has to be an integer number of samples to be able to process individual files
        filesize = 10 * self.pars.nchan * self.padded_size  # 10 * 1.024 seconds 

        for beam in self.pars.beams:
            # Calculate the RA and DEC of this beam given the telescope pointing
            output = subprocess.check_output([self.pointing_to_cb_position, str(beam), self.pars.ra, self.pars.dec])
            ra, dec = output.strip().split()

            header = template.format(fsize=filesize, \
                utc_start=self.pars.startutc, \
                mjd_start=self.pars.startmjd, \
                source=self.pars.source, \
                ra=ra.replace(':',''), \
                dec=dec.replace(':',''), \
                freq=self.pars.freq, \
                bw=self.pars.bw, \
                tsamp=self.tsamp, \
                batchlen=self.batchlen, \
                min_freq = self.pars.min_freq, \
                nchan=self.pars.nchan, \
                chan_width=self.pars.chan_width, \
                beam=beam, \
                nbit=self.nbit, \
                resolution=self.pars.nchan * self.padded_size, \
                bps=bps)
            headerfile = self.headerdir + 'header{0:02d}.txt'.format(beam)
            with open(headerfile, 'w') as f:
                f.write(header)


    def create_ringbuffer(self):
        sys.stdout.write('Creating ringbuffer.\n')
        # two readers if dual mode
        if self.pars.dual:
            nreader = 2
        else:
            nreader = 1
        for beam in self.pars.beams:
            cmd = 'taskset -c {4} dada_db -k {0} -b {1} -n {2} -p -r {5} &> {3} &'.format(self.keys[beam], self.ringbuffer_size, self.nbuffer, self.log.ringbuffer[beam], self.cpu_affil[beam], nreader)
            self.log.io.write(cmd+'\n')
            os.system(cmd)


    def search(self):
        sys.stdout.write('Starting AMBER.\n')
        folder = '{0}/{1}/{2}'.format(self.output_dir, self.pars.date, self.pars.datetimesource)
        os.system('mkdir -p {0}'.format(folder))
        outputfile = "{0}/{1}-{2}.band".format(folder, self.pars.date, self.pars.datetimesource)
        nbeam = 1  # no TABs or multiples SBs for IAB
        if self.pars.bruteforce:
            sys.stdout.write('Dedispersion mode: bruteforce.\n')
            for beam in self.pars.beams:
                cmd = 'taskset -c {16} {0} -opencl_platform {1} -opencl_device {2} -device_name {3} -padding_file {4}/padding.inc -zapped_channels {4}/zap.inc -integration_steps {4}/integration_steps.inc -dedispersion_file {4}/dedispersion.inc -integration_file {4}/integration.inc -snr_file {4}/snr.inc -input_bits {5} -output {6} -dms {7} -dm_first {8} -dm_step {9} -threshold {10} -dada -dada_key {11} -beams {12} -synthesized_beams {12} -batches {13} -compact_results -sampling_time {14} &> {15} &'.format(self.amber, \
                            self.device_platform, self.gpu_affil[beam], self.device_name, self.conf_dir, self.nbit, outputfile+'{0:02d}'.format(beam), \
                            self.num_dm, self.dm_first, self.dm_step, self.pars.snrmin, self.keys[beam], \
                            nbeam, self.pars.nbatch, self.tsamp, self.log.search[beam], self.cpu_affil[beam])
                self.log.io.write(cmd+'\n')
                os.system(cmd)
        elif self.pars.subband:
            sys.stdout.write('Dedispersion mode: subband.\n')
            for beam in self.pars.beams:
                cmd = 'taskset -c {16} {0} -opencl_platform {1} -opencl_device {2} -device_name {3} -padding_file {4}/padding.inc -zapped_channels {4}/zap.inc -integration_steps {4}/integration_steps.inc -subband_dedispersion -dedispersion_step_one_file {4}/dedispersionOne.inc -dedispersion_step_two_file {4}/dedispersionTwo.inc -integration_file {4}/integration.inc -snr_file {4}/snr.inc -input_bits {5} -output {6} -dms {7} -dm_first {8} -dm_step {9} -threshold {10} -dada -dada_key {11} -beams {12} -synthesized_beams {12} -batches {13} -sampling_time {14} -subbands {15} -subbanding_dms {16} -subbanding_dm_first {17} -subbanding_dm_step {18} -compact_results&> {19} &'.format(self.amber, \
                            self.device_platform, self.gpu_affil[beam], self.device_name, self.conf_dir, self.nbit, outputfile+'{0:02d}'.format(beam), \
                            self.num_dm, self.dm_first, self.dm_step, self.pars.snrmin, self.keys[beam], \
                            nbeam, self.pars.nbatch, self.tsamp, self.subbands, self.subband_dms, 
                            self.subband_dm_first, self.subband_dm_step, self.log.search[beam], self.cpu_affil[beam])
                self.log.io.write(cmd+'\n')
                os.system(cmd)


    def dump(self):
        sys.stdout.write('Starting dada_dbdisk.\n')
        for beam in self.pars.beams:
            disk_dir = self.dbdisk_dir.format(disk=self.datadisks[beam])
            folder = '{0}/{1}/{2}/CB{3:02d}'.format(disk_dir, self.pars.date, self.pars.datetimesource, beam)
            os.system('mkdir -p {0}'.format(folder))
            cmd = 'dada_dbdisk -b {3} -k {0} -D {1} &> {2} &'.format(self.keys[beam], folder, self.log.dump[beam], \
                                                                     self.cpu_affil[beam])
            self.log.io.write(cmd+'\n')
            os.system(cmd)


    def scrub(self):
        sys.stdout.write('Starting dada_dbscrubber.\n')
        for beam in self.pars.beams:
            cmd = 'dada_dbscrubber -v -k {0} &> {1} &'.format(self.keys[beam], self.log.scrub[beam])
            self.log.io.write(cmd+'\n')
            os.system(cmd)

    def fil(self):
        sys.stdout.write('Starting dadafilterbank.\n')
        for beam in self.pars.beams:
            disk_dir = self.fil_dir.format(disk=self.datadisks[beam])
            folder = '{0}/{1}/{2}/'.format(disk_dir, self.pars.date, self.pars.datetimesource)
            os.system('mkdir -p {0}'.format(folder))
            prefix = '{0}/CB{1:02d}'.format(folder, beam)
            cmd = 'taskset -c {8} {0} -c {1} -m {2} -k {3} -s 0 -b {5} -n {6} -l {7} &'.format(self.dadafilterbank, self.sc, self.dadafilterbank_mode, self.keys[beam], self.pars.startpacket, self.padded_size, prefix, self.log.dadafilterbank[beam], self.cpu_affil[beam])
            self.log.io.write(cmd+'\n')
            os.system(cmd)

    def fits(self):
        sys.stdout.write('Starting dadafits.\n')
        for beam in self.pars.beams:
            disk_dir = self.fits_dir.format(disk=self.datadisks[beam])
            folder = '{0}/{1}/{2}/'.format(disk_dir, self.pars.date, self.pars.datetimesource)
            os.system('mkdir -p {0}'.format(folder))
            cmd = 'taskset -c {6} {0} -c {1} -m {2} -k {3} -b {4} -l {5} -t {7} -d {8} &'.format(self.dadafits, self.sc, self.dadafits_mode, self.keys[beam], self.padded_size, self.log.dadafits[beam], self.cpu_affil[beam], self.dadafits_template, folder)
            self.log.io.write(cmd+'\n')
            os.system(cmd)


    def create_fill_ringbuffer(self):
        sys.stdout.write('Starting fill_ringbuffer\n')
        for beam in self.pars.beams:
            cmd = 'chrt -f 99 taskset -c {10} {0} -h {1} -c {2} -m {3} -b {4} -k {5} -s {6:.0f} -d {7:f} -p {8} -l {9} &'.format(self.fill_ringbuffer, self.headerdir + 'header{0:02d}.txt'.format(beam), self.sc, self.fill_ringbuffer_mode, self.padded_size, self.keys[beam], self.pars.startpacket, self.pars.tobs, self.ports[beam], self.log.fill_ringbuffer[beam], self.cpu_affil[beam])
            self.log.io.write(cmd+'\n')
            os.system(cmd)


    def __init__(self, args):
        waittime = .5
        # parse aguments
        self.parse_args(args)
        # create loggers
        self.create_logs()
        self.log.io = open(self.log.controller, 'w')
        sys.stdout.write('Initializing ARTS0 for IAB observation.\n')
        self.log.io.write('Initializing ARTS0 for IAB observation.\n')
        # print Tobs as it has been rounded to an integer nr of samples by the arg parser
        sys.stdout.write('Tobs: {0}\n'.format(self.pars.tobs))
        self.log.io.write('Tobs: {0}\n'.format(self.pars.tobs))
        # remove running ringbuffers, AMBER, etc.
        self.clean()
        sleep(waittime)
        # create PSRDADA header
        self.create_header()
        # create ringbuffer
        self.create_ringbuffer()
        sleep(waittime)
        # check mode and start dada_dbdisk, dada_dbscrubber, AMBER or dadafilterbank
        # for dual mode, both fil and bruteforce are set to True
        if self.pars.bruteforce or self.pars.subband:
            # start AMBER
            self.search()
        if self.pars.dump:
            # start dada_dbdisk
            self.dump()
        if self.pars.scrub:
            # start dada_dbscrubber
            self.scrub()
        if self.pars.fil:
            self.fil()
        if self.pars.fits:
            self.fits()
        sleep(waittime)
        # start fill ringbuffer
        self.create_fill_ringbuffer()
        sleep(waittime)
        # Everything has been started
        sys.stdout.write('All started for IAB observation.\n')
        sys.stdout.flush()
        self.log.io.write('All started for IAB observation.\n')
        self.log.io.flush()
        self.log.io.close()
        

def main(opts):
    IAB(opts)


if __name__ == '__main__':
    usage = 'usage: %prog -m <mode> [options]'
    parser = optparse.OptionParser(usage)
    # mode
    parser.add_option('-m', '--mode', dest='mode', type='string', action='store', default=None, \
                        help='Observation mode. Can be bruteforce, subband, dump, scrub, fil, fits, dual.')
    # beams
    parser.add_option('--sbeam', dest='sbeam', type='int', action='store', default=21, \
                        help='No of first CB to record (default: 21)')
    parser.add_option('--ebeam', dest='ebeam', type='int', action='store', default=0, \
                        help='No of last CB to record (default: sbeam, max: 39) Note: Every 5th beam is skipped (starting at 4)')
    parser.add_option('--beams', dest='beamrange', type='str', action='store', default='none', \
                        help='List of beams to process. Use instead of sbeam and ebeam')
    # obsinfo
    parser.add_option('-T', '--tstart', dest='tstart', type='string', action='store', default='default', \
                        help='Start time (UTC), e.g. "2017-01-01 00:00:00". (default: now + 5 seconds)')
    parser.add_option('-d', '--duration', dest='tobs', type='float', action='store', default=10.24, \
                        help='Observation duration in seconds. (default: 10.24)')
    parser.add_option('-n', '--source',  dest='source', type='string', action='store', default='IAB', \
                        help='Source name (default: IAB)')
    parser.add_option('--ra', dest='ra', type='string', action='store', default='00:00:00', \
                        help='J2000 RA in hh:mm:ss.s format (default: 00:00:00)')
    parser.add_option('--dec', dest='dec', type='string', action='store', default='00:00:00', \
                        help='J2000 DEC in dd:mm:ss.s format (default: 00:00:00')
    # Transientsearch
    parser.add_option('-s', '--snr', dest='snrmin', type='float', action='store', default=10, \
                        help='Min S/N in sesarch. (default: 10)')
    opts, args = parser.parse_args()
    if not opts.mode:
        parser.print_help()
        sys.exit(0)
    main(opts)
