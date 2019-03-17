#!/usr/bin/env python

import sys
import warnings

import numpy as np
from astropy.time import Time, TimeDelta
import astropy.coordinates as c
import astropy.units as u


if __name__ == '__main__':
    if not len(sys.argv) == 4:
        print 'Provide RA (hh:mm:ss) Dec (dd:mm:ss) startime ("yyyy-mm-dd hh:mm:ss")'
        exit()

    # don't complain about Unicode conversion warning
    warnings.filterwarnings('ignore', category=UnicodeWarning)

    # get RA
    try:
        RA = c.Angle(sys.argv[1]+' hours').to(u.degree)
    except c.errors.IllegalHourError:
        print 'Error: RA should be between 0 and 24 hours'
        exit()

    # get DEC
    DEC = c.Angle(sys.argv[2]+' degrees')
    if DEC > 90*u.degree or DEC < -90*u.degree:
        print 'Error: DEC should be between -90 and 90 degrees'
        exit()
    elif DEC < -35*u.degree:
        print "DEC < -35 degrees, not observable with WSRT"
        exit()

    # get start time
    stime = Time(sys.argv[3], scale='utc')
    stime.delta_ut1_utc = 0
    # convert to LST
    wsrt_lon = 6.60387*u.deg
    LST = stime.sidereal_time('mean', wsrt_lon) # - one minute?

    # scan one CB = 30 arcmin + extra 30 arcmin on each side -> 45 arcmin radius
    offset = 45*u.arcmin
    # one row of 6 beams = 180 arcmin + 30 extra on each side -> 120 arcmin radius
    offset_6beam = 120*u.arcmin
    # one row of 7 beams = 210 arcmin + 30 extra on each side -> 135 arcmin radius
    offset_7beam = 135*u.arcmin

    duration = (2*offset/np.cos(DEC.to(u.radian))).to(u.hourangle) * u.hour/u.hourangle + 1*u.minute
    duration_6beam = (2*offset_6beam/np.cos(DEC.to(u.radian))).to(u.hourangle) * u.hour/u.hourangle + 1*u.minute
    duration_7beam = (2*offset_7beam/np.cos(DEC.to(u.radian))).to(u.hourangle) * u.hour/u.hourangle + 1*u.minute

    # starting point
    start_RA = RA - offset/np.cos(DEC.to(u.radian))

    # get HA at start time
    HA = LST - start_RA
    if HA < - 180*u.degree:
        HA += 360*u.degree
    if HA > 180*u.degree:
        HA -= 360*u.degree

    print "Pointing RA:", start_RA.to_string(u.hourangle)
    print "Duration one beam: ", int(duration.to(u.second).value), 's'
    print "Duration six beams: ", int(duration_6beam.to(u.second).value), 's'
    print "Duration seven beams: ", int(duration_7beam.to(u.second).value), 's'
    #print "Pointing HA:", HA.to_string(u.hourangle, decimal=True, precision=8)
    print "Pointing decimal HA, Dec", HA.to_string(u.degree, decimal=True, precision=8), DEC.to_string(u.degree, decimal=True, precision=8)
    print "Source decimal RA, Dec", RA.to_string(u.degree, decimal=True, precision=8), DEC.to_string(u.degree, decimal=True, precision=8)
