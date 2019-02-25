#!/usr/bin/env python

import sys
import warnings

import numpy as np
from astropy.time import Time, TimeDelta
import astropy.coordinates as c
import astropy.units as u


if __name__ == '__main__':
    if not len(sys.argv) == 3:
        print 'Provide RA (hh:mm:ss) and Dec (dd:mm:ss)'
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

    # scan one CB = 30 arcmin + extra 10 arcmin on each side -> 25 arcmin radius
    offset = 25*u.arcmin

    duration = (2*offset/np.cos(DEC.to(u.radian))).to(u.hourangle) * u.hour/u.hourangle

    # starting point
    start_RA = RA - offset/np.cos(DEC.to(u.radian))

    print "Pointing RA:", start_RA.to_string(u.hourangle)
    print "Duration: ", duration.to(u.second)
    print "Decimal RA, Dec", start_RA.to_string(u.degree, decimal=True), DEC.to_string(u.degree, decimal=True)
