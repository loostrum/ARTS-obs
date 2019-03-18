#!/usr/bin/env python
#
# From an observation schedule and beam positions, 
# find which known pulsars are in the field

import os
import sys
import argparse
import time

import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u
from psrqpy import QueryATNF


class ApertifBeamSources(object):

    def __init__(self, csv_file):
        """
        csv_file: input csv with observation info
        """
        self.offsets_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'square_39p1.cb_offsets')
        self.csv_file = csv_file

        self.offsets = {}
        self.pointings = []
        self.positions = []
        self.pulsars = []

        self.do_query()
        self.parse_csv()
        self.parse_offsets()
        self.get_cb_positions()
        self.get_pulsars()

        self.print_results()

    def parse_csv(self):
        """
        Load the csv file and save the observation schedule
        """
        schedule = np.genfromtxt(self.csv_file, delimiter=',', names=True, dtype=None, encoding=None)
        self.schedule = schedule
        self.pointings = np.transpose([schedule['ra'], schedule['dec']])

    def parse_offsets(self):
        """
        Parse the CB offsets file 
        """
        raw_offsets = np.loadtxt(self.offsets_file, dtype=str, delimiter=',')
        offsets = {}
        for key, dRA, dDec in raw_offsets:
            # keys are like compoundBeam.0.offset
            cb = int(key.split('.')[1])
            dRA = float(dRA.strip())
            dDec = float(dDec.strip())
            offsets[cb] = [dRA, dDec]
        self.offsets = offsets

    def get_cb_positions(self):
        """
        Get the position of each CB for each pointing
        """
        for pointing_ra, pointing_dec in self.pointings:
            pointing_coord = SkyCoord(pointing_ra, pointing_dec, unit=(u.hourangle, u.degree), frame='icrs')
            positions = {}
            # get position of each CB
            for cb in self.offsets.keys():
                cb_dec = pointing_coord.dec.degree + self.offsets[cb][1]
                cb_ra = pointing_coord.ra.degree + self.offsets[cb][0] / np.cos(cb_dec * np.pi/180)
                positions[cb] = SkyCoord(cb_ra, cb_dec, unit=(u.degree, u.degree))
        self.positions.append(positions)

    def do_query(self):
        """
        Query ATNF 
        """
        params = ['JNAME', 'RAJ', 'DECJ', 'S1400', 'DM', 'P0']
        condition = "S1400 > 1 && DECJ > -35"
        sys.stderr.write("Querying ATNF\n")
        tstart = time.time()
        result = QueryATNF(params=params, condition=condition)
        time_taken = time.time() - tstart
        sys.stderr.write("Query took {:.1f} seconds\n".format(time_taken))
        sys.stderr.write("Found {} results for {}\n\n".format(len(result.table), condition))
        self.ATNFtable = result.table
        # store coordinates as SkyCoord
        self.ATNFtable['coordinates'] = SkyCoord(self.ATNFtable['RAJ'], self.ATNFtable['DECJ'], unit=(u.hourangle, u.deg))

    def get_pulsars(self):
        """
        Find which pulsars are within the Apertif FoV for each pointing
        """
        max_dist = 3*u.degree  # covers entire FoV
        for i, (pointing_ra, pointing_dec) in enumerate(self.pointings):
            # skycoord of this pointing
            pointing_coord = SkyCoord(pointing_ra, pointing_dec, unit=(u.hourangle, u.degree), frame='icrs')
            # get separation to each pulsar
            sep = pointing_coord.separation(self.ATNFtable['coordinates'])
            visible = sep < max_dist
            self.pulsars.append(self.ATNFtable[visible])

    def print_results(self):
        """
        Print which pulsars are detectable for each pointing
        """
        for ind, obs in enumerate(self.schedule):
            pointing = self.pointings[ind]
            pulsars = self.pulsars[ind]
            print "Survey pointing: {}\t RA: {}\t DEC: {}".format(obs['source'], obs['ra'], obs['dec'])
            print "Number of pulsars within field: {}".format(len(pulsars))
            if len(pulsars) > 0:
                print "Pulsars:"
                cols = ['JNAME', 'S1400', 'DM', 'P0', 'RAJ', 'DECJ']
                print pulsars[cols]

            print "\n\n"
            

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--schedule', help="Observing schedule in csv format.", required=True)

    args = parser.parse_args()

    ApertifBeamSources(args.schedule)
    
