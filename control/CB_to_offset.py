#!/usr/bin/env python
#
# Convert IAB CB numbers to offset in RA and DEC
# 
# Author: L. Oostrum

import sys

import numpy as np

# generic element (gel) layout:
#
#  0-----55------110
#  |      |      |
#  |      |      |
#  5-----60------115
#  |      |      |
#  |      |      |
#  10----65------120
#
# +DEC = North = up, +HA is West = left
# +RA = east = right

# PAF is 11*11 grid of elements
nrows = 11
ncols = 11
# IAB uses 32 beams, every 5th starting at 4 is missing. every 5th starting at 3 is 200 MHz instead of 300 MHz
CBs = [0,1,2,3,5,6,7,8,10,11,12,13,15,16,17,18,20,21,22,23,25,26,27,28,30,31,32,33,35,36,37,38]


def CB_to_gel(CB):
    """
    Convert CB number to gel number
    See output of "python $UPE/base/unb_apertif.py"
    """
    
    gel_to_CB = [ -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,  -1,   0,  -1,  12,  -1,  26,  -1,  23,  -1,  -1,  -1,   3,   0,   6,  12,  20,  26,  32,  23,  -1,  -1,  -1,   3,   1,   6,  15,  20,  27,  32,  28,  -1,  -1,  -1,   8,   1,   7,  15,  21,  27,  35, 28, -1, -1, -1,  8,  2,  7, 16, 21, 30, 35, 33, -1, -1, -1, 13,  2, 10, 16, 22, 30, 36, 33, -1, -1, -1, 13,  5, 10, 17, 22, 31, 36, 38, -1, -1, -1, 18,  5, 11, 17, 25, 31, 37, 38, -1, -1, -1, 18, -1, 11, -1, 25, -1, 37, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1]

    CB_to_gel_X = {}
    CB_to_gel_Y = {}
    for gel, cb in enumerate(gel_to_CB):
        if gel % 2:
            CB_to_gel_Y[cb] = gel
        else:
            CB_to_gel_X[cb] = gel

    try:
        gel = [CB_to_gel_X[CB], CB_to_gel_Y[CB]]
    except KeyError:
        print "CB {} not currently present in IAB beam selection".format(CB)
        raise
    return gel


def gel_to_offset(gel):
    """
    Calculate offset in RA, DEC from the central element (60)
    """
    nrows = 11
    ncols = 11
    #offset_to_RADEC = 0.375  # degrees
    offset_to_RADEC = 0.7845*0.4630  # degrees
    #shift = 0.075  # degrees
    shift = 0

    # Negative offsets are up and left with respect to central element. 
    # That corresponds to a positive offset in DEC and a negative offset in RA
    # gels use fortran ordering: row = RA, col = DEC
    # rows: negative offset = left = negative RA: correct
    # cols: negative ofset = up = postive DEC: multiply by -1
    row = -1 * (np.floor(gel/ncols) - nrows//2)
    col = (gel % nrows - nrows//2)

    dRA = row * offset_to_RADEC 
    dDEC = col * offset_to_RADEC
    # apply shifts
    # RA (only row 3 and -3 from center, maybe more?)
    if row % 3 == 0:
        dRA -= shift * np.sign(dRA)
    # DEC (every odd row from center)
    if col % 2 == 1:
        # odd row, shift DEC
        dDEC -= shift * np.sign(dDEC)

    return dRA, dDEC


def hms_to_decimal(RA, DEC):
    """
    Convert hh:mm:ss RA and dd:mm:ss DEC to decimal degrees
    """

    RA = RA.split(':')
    RA = (float(RA[0]) + float(RA[1])/60 + float(RA[2])/3600) * 15
    # Remove + from positive DEC if present
    if DEC[0] == '+':
        DEC = DEC[1:]
    DEC = DEC.split(':')
    if float(DEC[0]) < 0:
        sign = -1
    else:
        sign = 1
    DEC = float(DEC[0]) + sign*float(DEC[1])/60 + sign*float(DEC[2])/3600
    return RA, DEC


def decimal_to_hms(RA, DEC):
    """
    Convert decimal degree RA and DEC to hh:mm:ss and dd:mm:ss
    """
    if DEC < 0:
        sign = -1
    else:
        sign = 1

    # RA
    r = RA / 15.
    RA_hr = int(r)
    r -= RA_hr
    RA_min = int(r * 60.) 
    r -= RA_min / 60.
    RA_sec = r * 3600

    # DEC
    d = np.abs(DEC)
    DEC_deg = int(d) * sign
    d -= int(d)
    DEC_min = int(d * 60)
    d -= DEC_min/60.
    DEC_sec = d * 3600

    # formatting
    if RA_sec < 10:
        strRA_sec = "0{:.3f}".format(RA_sec)
    else:
        strRA_sec = "{:.3f}".format(RA_sec)

    if DEC_sec < 10: 
        strDEC_sec = "0{:.3f}".format(DEC_sec)
    else:
        strDEC_sec = "{:.3f}".format(DEC_sec)
    
    RA = "{:02d}:{:02d}:{}".format(RA_hr, RA_min, strRA_sec)
    DEC = "{:02d}:{:02d}:{}".format(DEC_deg, DEC_min, strDEC_sec)
    return RA, DEC



if __name__ == '__main__':

    if len(sys.argv) < 4:
        print "Usage: ./CB_to_offset.py CB RA DEC [pol]"
        print "Pol can by X (default), Y or avg"
        sys.exit(1)

    # Parse arguments
    CB = int(sys.argv[1])
    RA, DEC = sys.argv[2], sys.argv[3]
    try:
        pol = sys.argv[4]
    except IndexError:
        pol = 'X'

    RA, DEC = hms_to_decimal(RA, DEC)

    # get offsets
    gelX, gelY = CB_to_gel(CB)
    offsetX = gel_to_offset(gelX)
    offsetY = gel_to_offset(gelY)

    # fix offset in RA
    offsetX = (offsetX[0] / np.cos(DEC * np.pi/180), offsetX[1])
    offsetY = (offsetY[0] / np.cos(DEC * np.pi/180), offsetY[1])

    # mean offset
    offsetRA, offsetDEC = np.mean([offsetX, offsetY], axis=0)

    # add offset to input (converting to telescope pointing)
    RAX = RA - offsetX[0]
    RAY = RA - offsetY[0]
    RA = RA - offsetRA
    RAlist = (RAX, RAY, RA)

    DECX = DEC - offsetX[1]
    DECY = DEC - offsetY[1]
    DEC = DEC - offsetDEC
    DEClist = (DECX, DECY, DEC)

    #names = ('X-pol', 'Y-pol', 'Average')
    # Convert coords back to hh:mm:ss and print
    #for ra, dec, name in zip(RAlist, DEClist, names):
    #    ra, dec = decimal_to_hms(ra, dec)
    #    print "CB{} {}: point dishes to (RA,DEC) = ({} {})".format(strCB, name, ra, dec)

    # Return position for requested pol for pointing script
    if pol.upper() in ('0', 'X'):
        ra, dec = decimal_to_hms(RAX, DECX)
    elif pol.upper() in ('1', 'Y'):
        ra, dec = decimal_to_hms(RAY, DECY)
    else:
        ra, dec = decimal_to_hms(RA, DEC)

    print ra, dec
