#!/usr/bin/env python
import sys
import socket
from time import sleep
import argparse

import numpy as np
from astropy.time import Time, TimeDelta


class Trigger(object):


    def __init__(self, args)
        """
        args: settings through argument parser
        """

        config = vars(args)
        # Convert start time to an Astropy time object
        config['tstart'] = Time(config['tstart'], format='unix')

        for key, value in config.items():
            setattr(self, key, value)

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
        try:
            alltrigs = np.loadtxt(self.fname, dtype=float, ndmin=2)
        except IOError:
            print "Trigger file does not exist yet"
            return
        if len(alltrigs) == 0:
            print alltrigs
            print "No triggers yet"
            return
        if len(alltrigs) == self.ntrig:
            print "No new triggers"
            return

        print "Found new triggers"
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
        dm = trigger[6]
        age = (Time.now() - TimeDelta(trigger[5], format='sec') - self.tstart ).sec
        print age, self.maxage
        if snr >= self.snrmin and age <= self.maxage and dm >= self.dmmin and dm <= self.dmmax:
            print "Trigger ok, creating command"
            command = self.create_trigger(trigger)
            print "Sending trigger"
            self.send_trigger(command)
        else:
            print "Trigger not ok"


    def create_trigger(self, trig):
        beam, batch, sample, integration_step, compacted_integration_steps, time, DM, compacted_DMs, SNR = trig
        width = integration_step * 4.096e-5

        t_event = self.tstart + TimeDelta(time, format='sec')
        utc_start = self.tstart.datetime.strftime('%Y-%m-%d-%H:%M:%S')

        t_start = t_event - TimeDelta(.5*self.dt, format='sec')
        t_start_frac = 0 #t_start.unix - int(t_start.unix)
        t_end = t_event + TimeDelta(.5*self.dt, format='sec')
        t_end_frac = 0 #t_end.unix - int(t_end.unix)
        t_start = t_start.datetime.strftime('%Y-%m-%d-%H:%M:%S')
        t_end = t_end.datetime.strftime('%Y-%m-%d-%H:%M:%S')
        print "Trigger: t={0:.2f}    DM={1:.2f}    SNR={2:.2f}".format(time, DM, SNR)

        command="""N_EVENTS 1
{utc_start}
{t_start} {t_start_frac} {t_end} {t_end_frac}  {DM} {SNR} {width} {beam}
""".format(utc_start=utc_start, t_start=t_start, t_start_frac=t_start_frac, t_end=t_end, t_end_frac=t_end_frac, DM=DM, SNR=SNR, width=width, beam=int(beam))

        with open('trigger.txt', 'w') as f:
            f.writelines(command)

        return command


    def send_trigger(self, trigger):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))
        s.sendall(trigger.encode())
        s.shutdown(socket.SHUT_WR)
        s.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Watch triggers and start I/IQUV data dump")

    parser.add_argument("--tstart", type=float, help="Observation start time (unix timestamp)", required=True)
    parser.add_argument("--fname", type=str, help="Filename to watch", required=True)

    parser.add_argument("--interval", type=float, help="Interval for checking triggers (s) " \
                            "(Default: 2)", default="2")
    parser.add_argument("--snrmin", type=float, help="Minium S/N" \
                            "(Default: 20)", default=20)
    parser.add_argument("--dmmin", type=float, help="Minimum DM" \
                            "(Default: 100)", default=100)
    parser.add_argument("--dmmax", type=float, help="Maximum DM" \
                            "(Default: 5000)", default=5000)
    parser.add_argument("--dumpsize", type=float, help="Size of data dump (s)" \
                            "(Default: 6.0)", default=6.0)
    parser.add_argument("--host", type=str, help="Host name to send events to" \
                            "(Default: localhost)", default="localhost")
    parser.add_argument("--port", type=int, help="Port to send events to" \
                            "(Default: 30000)", default=30000)


    args = parser.parse_args()
    t = Trigger(args)
    t.run()
