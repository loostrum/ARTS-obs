#!/usr/bin/env python

import sys 
import contextlib
import warnings

import numpy as np
from astropy.time import Time, TimeDelta
import astropy.coordinates as c
import astropy.units as u

from drift_scan import calc_drift


@contextlib.contextmanager
def nostdout():
    saved_stdout = sys.stdout
    sys.stdout = open('/dev/null', 'w')
    yield
    sys.stdout = saved_stdout


if __name__ == '__main__':
    # don't complain about Unicode conversion warning
    warnings.filterwarnings('ignore', category=UnicodeWarning)

    # wait time between observations
    wait_time = TimeDelta(180, format='sec')

    # rows of PAF
    cb_sets = [(0,), range(1, 8), range(8, 15), range(15, 21), range(21, 27), range(27, 33), range(33, 40)]

#    # 3C286
#    src = '3C286'
#    RA = c.Angle('13:31:08.2883035 hours').to(u.degree)
#    Dec = c.Angle('+30:30:32.962130 degrees').to(u.degree)

#    # 3C147
#    src = '3C147'
#    RA = c.Angle('05:42:36.1378984 hours').to(u.degree)
#    Dec = c.Angle('+49:51:07.233725 degrees').to(u.degree)

    # Crab
    src = 'B0531+21'
    RA = c.Angle('05:34:31.973 hours').to(u.degree)
    Dec = c.Angle('+22:00:52.06 degrees').to(u.degree)

    # start times
    #stimes = ["2019-03-19 01:28:51", "2019-03-19 23:18:28", "2019-03-21 00:15:28", "2019-03-22 01:09:18" , "2019-03-23 02:00:29", "2019-03-23 23:44:49", "2019-03-25 00:41:07"]
    stimes = ["2019-04-03 16:18:24"]

    for t in stimes:
        fname = t.replace(' ', '_') + '.csv'
        with open(fname, 'w') as f:
            # add header
            hdr = 'source,ra,dec,date1,time1,date2,time2,freq,weight,sbeam,ebeam,pulsar\n'
            f.write(hdr)

            print "Calculating drift scans of {} starting at {}".format(src, t)
            stime = Time(t, scale='utc', out_subfmt='date_hms')

            # loop over beams
            for cb_set in cb_sets:
                nbeam = len(cb_set)
                min_beam = min(cb_set)
                max_beam = max(cb_set)
                ref_beam = max_beam
                print "PAF row: CB{:02d} to CB{:02d}".format(min_beam, max_beam)

                # get pointing
                with nostdout():
                    pointing_ha, pointing_dec, duration = calc_drift(RA, Dec, stime, nbeam=nbeam)

                # get source name
                if nbeam == 1:
                    src_drift = src + "drift{:02d}".format(min_beam)
                else:
                    src_drift = src + "drift{:02d}{:02d}".format(min_beam, max_beam)

                # get start/end time strings
                etime = stime + TimeDelta(duration, format='sec')
                date1, time1 = stime.iso.split(' ')
                date2, time2 = etime.iso.split(' ')
                # remove subsecond
                time1 = time1.split('.')[0]
                time2 = time2.split('.')[0]

        
                # write pointing
                pointing = "{},{},{},{},{},{},{},1400,square_39p1,0,39,False\n".format(src_drift,
                            pointing_ha, pointing_dec, date1, time1, date2, time2)
                f.write(pointing)
                

                # new start time
                stime = etime + wait_time
