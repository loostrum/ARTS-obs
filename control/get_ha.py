#!/usr/bin/env python

import sys
import warnings

import numpy as np
try:
    from astropy.time import Time, TimeDelta
    import astropy.coordinates as c
    import astropy.units as u
except ImportError:
    print "Cannot import astropy"
    exit()


if __name__ == '__main__':
    if not len(sys.argv) in [2, 3]:
        print 'Please provide the RA of the object in hh:mm:ss format'
        print 'Also provide DEC if you want the correct rise and set time for DEC<0'
        exit()

    # don't complain about Unicode conversion warning
    warnings.filterwarnings('ignore', category=UnicodeWarning)

    RA = c.Angle(sys.argv[1]+' hours').to(u.degree)
    try:
        tmp = sys.argv[2]
    except IndexError:
        tmp = '00:00:00'
    DEC = c.Angle(tmp+' degrees')

    # WSRT coordinates
    lat = 52.915184*u.degree
    lon = 6.60387*u.degree
    UT = Time.now()
    UT.delta_ut1_utc = 0
    LST = UT.sidereal_time('mean', lon)
    HA = LST - RA

    # make sure HA is between -180 and 180
    if HA < -180*u.degree:
        HA += 360*u.degree
    elif HA > 180*u.degree:
        HA -= 360*u.degree


    # HA where altitude = 0. Doesn't work if DEC > lat, so limited by DEC
    if DEC > 0:
        # limited by HA
        ha_min = -90*u.degree
        ha_max = 90*u.degree
    elif DEC < -35*u.degree:
        print "DEC < -35, not observable with WSRT"
        exit()
    else:
        ha_tmp = np.arccos(-1*np.tan(lat)*np.tan(DEC))
        if ha_tmp > 0:
            ha_max = ha_tmp
            ha_min = -1*ha_tmp
        else:
            ha_max = -1 * ha_tmp
            ha_min = ha_tmp
            print ha_min, ha_max

    # Get rise and set time
    visible=False
    if ha_min < HA < ha_max:
        # Source is currently up
        visible = True
        dt_rise = ha_min - HA
        dt_set = dt_rise + ha_max - ha_min
    else:
        dt_rise = 360*u.degree + ha_min - HA
        dt_rise = dt_rise % (360*u.degree)
        dt_set = dt_rise + ha_max - ha_min

    # unit trick to combine hours and degrees.
    # Probably astropy has a way to do this but I can't find it
    dt_rise = dt_rise.to(u.hourangle) * u.hour/u.hourangle
    dt_set = dt_set.to(u.hourangle) * u.hour/u.hourangle
    t_rise = UT + dt_rise
    t_set = UT + dt_set

    # Current altitude (Note: reordering gives the formula to calculate HA at altitude=0)
    h_now = np.arcsin(np.sin(lat)*np.sin(DEC) + np.cos(lat)*np.cos(DEC)*np.cos(HA))

    # Convert LST to a time
    LST = LST.to(u.hourangle) * u.hour/u.hourangle

    print 'UT:', UT.value.strftime("%X")
    print 'LST:', LST
    print 'RA:', RA.to_string(u.degree, decimal=True)
    print 'DEC:', DEC.to_string(u.degree, decimal=True)
    print 'HA:', HA.to_string(u.degree, decimal=True)
    print 'Altitude:', h_now.to(u.degree)
    print 'T rise:', t_rise
    print 'T set:', t_set
    print 'HA at rise:', ha_min.to(u.degree)
    print 'HA at set:', ha_max.to(u.degree)
