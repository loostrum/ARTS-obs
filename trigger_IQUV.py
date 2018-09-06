#!/usr/bin/env python
import sys
from time import sleep

import numpy as np
from astropy.time import Time, TimeDelta


class Trigger(object):

    def __init__(self, tstart, fname):
        """
        fname : amber output file to watch
        tstart: astropy time object with start time of observation
        """
        self.fname = fname
        self.tstart = tstart

        # Settings
        self.interval = 2  # interval between trigger checking
        self.snrmin = 10
        self.maxage = 10  # seconds
        self.dt = 5.0  # how many secs to save

        self.ntrig = 0

    def run(self):
        prev_time = Time(0, format='unix')
        while True:
            new_time = Time.now()
            delta = (new_time-prev_time)
            if (new_time-prev_time).sec >= self.interval:
                prev_time = new_time
                self.check_triggers()
            else:
                sleep(.05)

    def check_triggers(self):
        print "Checking triggers"
        # load new triggers
        alltrigs = np.loadtxt(self.fname, dtype=float, ndmin=2)
        if len(alltrigs) == 0:
            print "No triggers yet"
            return
        if len(alltrigs) == self.ntrig:
            print "No new triggers"
            return

        # skip already processed triggers
        triggers = list(alltrigs[self.ntrig:])
        # set number of processed triggesr
        self.ntrig += len(triggers)
        # sort by last column = S/N
        triggers.sort(key=lambda x: x[-1])
        # pick brightest
        trigger = triggers[0]
        # check S/N and age
        snr = trigger[-1]
        #age = (Time.now() - TimeDelta(trigger[5], format='sec') - self.tstart ).sec
        age = (Time(58367.56700231481481481481, format='mjd') - TimeDelta(trigger[5], format='sec') - self.tstart ).sec + 5
        if snr >= self.snrmin and age <= self.maxage:
            self.do_trigger(trigger)

    def do_trigger(self, trig):
        beam, batch, sample, integration_step, compacted_integration_steps, time, DM, compacted_DMs, SNR = trig
        width = integration_step * 4.096e-5

        t_event = self.tstart + TimeDelta(time, format='sec')
        utc_start = self.tstart.datetime.strftime('%Y-%m-%d-%H:%M:%S')

        t_start = t_event - TimeDelta(.5*self.dt, format='sec')
        t_end = t_event + TimeDelta(.5*self.dt, format='sec')
        t_start = t_start.datetime.strftime('%Y-%m-%d-%H:%M:%S')
        t_end = t_end.datetime.strftime('%Y-%m-%d-%H:%M:%S')
        print "Trigger: t={0:.2f}    DM={1:.2f}    SNR={2:.2f}".format(time, DM, SNR)

        command="""N_EVENTS 1
UTC_START {utc_start}
{t_start} 0 {t_end} {DM} {SNR} {width} {beam}
""".format(utc_start=utc_start, t_start=t_start, t_end=t_end, DM=DM, SNR=SNR, width=width, beam=int(beam))

        print command
        with open('trigger.txt', 'w') as f:
            f.writelines(command)
        #os.system('cat trigger.txt | ncat localhost 30000')

        # trigger format
        # N_EVENTS 1
        # UTC_START  {utc_start}
        # // yymmddss:hh:mm:ss_start fraction yymmddss:hh:mm:ss_end DM S/N width beam
        # {t_start} 0 {t_end} {DM} {SNR} {width} {beam}
            

if __name__ == '__main__':
    # give unix time as arg
    #t = Trigger(tstart=sys.argv[1], fname='/dev/null')
    t = Trigger(tstart=Time(58367.56700231481481481481, format='mjd'), fname='output/amber_step2.trigger')
    t.run()
