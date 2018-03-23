#!/usr/bin/env python
#
# Plot the sky location of triggers
# Author: L.C. Oostrum

import os
import sys
import argparse

import numpy as np
import matplotlib.pyplot as plt
from astropy import units as u
from astropy.time import Time, TimeDelta
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from sigpyproc.Readers import FilReader


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Plot azimuth and elevation dependence of triggers")
    # path to trigger file
    parser.add_argument("triggers", type=str, help="Path to .trigger or .singlepulse file")
    # path to filterbank file (for header)
    parser.add_argument("filterbank", type=str, help="Path to filterbank filterbank file")

    args = parser.parse_args()

    # check if files exist
    if not os.path.isfile(args.filterbank):
        print "Cannot find filterbank file {}".format(args.filterbank)
        sys.exit(1)
    if not os.path.isfile(args.triggers):
        print "Cannot find trigger file {}".format(args.trigger)
        sys.exit(1)

    # get header info
    hdr = FilReader(args.filterbank).header
    radec = SkyCoord(hdr.ra, hdr.dec, unit=(u.hourangle, u.deg))
    starttime = Time(hdr.tstart, format='mjd', scale='utc')

    # define coordinates
    wsrt = EarthLocation(lat=52.915184*u.deg, lon=6.60387*u.deg, height=0*u.m)
    altazstart = radec.transform_to(AltAz(obstime=starttime, location=wsrt))

    # check alt az start
    assert np.abs(hdr.az_start - altazstart.az.deg) < 1E-4 and \
           np.abs(hdr.za_start - (90 - altazstart.alt.deg)) < 1E-4

    # load triggers
    triggers = np.loadtxt(args.triggers, unpack=True)
    if args.triggers.endswith('.trigger'):
        try:
            dm, sigma, t0, downs = triggers[6], triggers[8], triggers[5], triggers[3]
        except:
            dm, sigma, t0, downs = triggers[-2], triggers[-1], triggers[-3], triggers[3]
    elif args.triggers.endswith('.singlepulse'):
        try:
            dm, sigma, t0, downs = triggers[0], triggers[1], triggers[2], triggers[4]
        except:
            dm, sigma, t0, downs = triggers[0], triggers[1], triggers[2], triggers[3]
    else:
        print "Can only load AMBER or PRESTO trigger files"
        sys.exit(1)
    print "Found {} triggers".format(len(t0))

    # get alt and az of each trigger
    utc_trigger = starttime + TimeDelta(t0, format='sec')
    altaz = radec.transform_to(AltAz(obstime=utc_trigger, location=wsrt))
    altarray = altaz.alt.deg
    azarray = altaz.az.deg

    # create plot
    bins = 20
    fig ,ax = plt.subplots()
    cax = ax.hist2d(azarray, altarray, bins=bins)[-1]
    cbar = fig.colorbar(cax)
    ax.set_xlabel('Azimuth (deg)')
    ax.set_ylabel('Altitude (deg)')
    plt.savefig('altaz.pdf')
