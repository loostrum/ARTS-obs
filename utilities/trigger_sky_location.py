#!/usr/bin/env python
#
# Plot the sky location of triggers
# Author: L.C. Oostrum

import os
import sys
import argparse

import numpy as np
import matplotlib.pyplot as plot
from astropy import units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from sigpyproc.Readers import FilReader


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Plot azimuth and elevation dependence of triggers")
    # path to trigger file
    parser.add_argument("--trigger", "-t", type=str, help="Path to .trigger or .singlepulse file")
    # path to filterbank file (for header)
    parser.add_argument("--filterbank", "-f", type=str, help="Path to filterbank filterbank file")

    args = parser.parse_args()

    # check if files exist
    if not os.path.isfile(args.filterbank):
        print "Cannot find filterbank file {}".format(args.filterbank)
        sys.exit(1)
    if not os.path.isfile(args.trigger):
        print "Cannot find trigger file {}".format(args.trigger)
        sys.exit(1)

    # get header info
    hdr = FilReader(args.filterbank).header
    radec = SkyCoord(hdr.ra, hdr.dec, unit=(u.hourangle, u.deg))
    starttime = Time(hdr.utcstart, format='iso', scale='utc')

    # define coordinates
    wsrt = EarthLocation(lat=52.915184*u.deg, lon=6.60387*u.deg, height=0*u.m)
    altazstart = radec.transform_to(AltAz(obstime=starttime, location=wsrt))

    # check alt az start
    assert hdr.az_start == altazstart.az.deg and hdr.za_start == (90 - altazstart.alt.deg)


    # load triggers
    triggers = np.loadtxt(args.trigger, unpack=True)
    if args.trigger.endswith('.trigger')
        try:
            dm, sigma, t0, downs = triggers[6, 8, 5, 3]
        except:
            dm, sigma, t0, downs = triggers[-2, -1, -3 ,3]
    elif args.trigger.endswith('.singlepulse'):
        dm, sigma, t0. downs = triggers[0, 1, 2, 4]
    else:
        print "Can only load AMBER or PRESTO trigger files"
        sys.exit(1)

    # get alt and az of each trigger
    altarray = np.zeros(len(t0))
    azarray = np.zers(len(t0))
    for i, t in enumerate(t0):
        utc_trigger = starttime + TimeDelta(t0, format='sec')
        altaz = radec.transform_to(AltAz(obstime=utc_trigger), location=wsrt)
        altarray[i] = altaz.alt.deg
        azarray[i] = altaz.az.deg

    print altarray
    print azarray