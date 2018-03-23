#!/usr/bin/env python
#
# Convert input Alt Az to RA+DEC for WSRT
# Author: L.C. Oostrum

import sys

from astropy import units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy.time import Time, TimeDelta
from datetime import datetime

if __name__ == '__main__':
    try:
        alt = float(sys.argv[1])
        az = float(sys.argv[2])
    except IndexError:
        print "Usage: altaz_to_radec.py alt az"
        sys.exit(1)

    wsrt = EarthLocation(lat=52.915184*u.deg, lon=6.60387*u.deg, height=0*u.m)
    now = Time(datetime.utcnow(), scale='utc')
    altaz = AltAz(alt=alt*u.deg,az=az*u.deg,obstime=now,location=wsrt)
    radec= altaz.transform_to(SkyCoord(0,0,unit=(u.hourangle,u.degree)))
    ra = radec.ra.to_string(unit=u.hourangle, sep=':', pad=True, precision=1)
    dec = radec.dec.to_string(unit=u.degree, sep=':', pad=True, precision=1)
    print ra, dec
