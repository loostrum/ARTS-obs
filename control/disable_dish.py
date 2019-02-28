#!/usr/bin/env python
#
# Disable dish data path for ARTS beamformer
# Based on dish-to-fpga mapping:
# X-pol connect to central UNB-FN:
# . Central UNB-0:15, FN 0, link 0,1,2 connects to X-pol, FN-0:15 on dish UNB-0:3 of RT 2,3,4"
# . Central UNB-0:15, FN 1, link 0,1,2 connects to X-pol, FN-0:15 on dish UNB-0:3 of RT 5,6,7"
# . Central UNB-0:15, FN 2, link 0,1,2 connects to X-pol, FN-0:15 on dish UNB-0:3 of RT 8,9,a"
# . Central UNB-0:15, FN 3, link 0,1,2 connects to X-pol, FN-0:15 on dish UNB-0:3 of RT b,c,d"
# Y-pol connect to central UNB-BN:
# . Central UNB-0:15, BN 0, link 0,1,2 connects to Y-pol, FN-0:15 on dish UNB-4:7 of RT 2,3,4"
# . Central UNB-0:15, BN 1, link 0,1,2 connects to Y-pol, FN-0:15 on dish UNB-4:7 of RT 5,6,7"
# . Central UNB-0:15, BN 2, link 0,1,2 connects to Y-pol, FN-0:15 on dish UNB-4:7 of RT 8,9,a"
# . Central UNB-0:15, BN 3, link 0,1,2 connects to Y-pol, FN-0:15 on dish UNB-4:7 of RT b,c,d"

import os
import sys
import argparse
import subprocess


class DisableDish(object):

    def __init__(self, args):
        # Define dish to central FPGA mapping
        self.dish_to_node = {'2': 0, '3': 0, '4': 0,
                             '5': 1, '6': 1, '7': 1,
                             '8': 2, '9': 2, 'A': 2,
                             'B': 3, 'C': 3, 'D': 3}

        # Define dish to input link mapping
        self.dish_to_link = {'2': 0, '3': 1, '4': 2,
                             '5': 0, '6': 1, '7': 2,
                             '8': 0, '9': 1, 'A': 2,
                             'B': 0, 'C': 1, 'D': 2}

        self.args = args

    def disable(self):
        fpga = self.dish_to_node[self.args.rt]
        link = self.dish_to_link[self.args.rt]

        if self.args.pol == 'X':
            nodes = "--fn {}".format(fpga)
        elif self.args.pol == 'Y':
            nodes = "--bn {}".format(fpga)
        elif self.args.pol == 'XY':
            nodes = "--fn {0} --bn {0}".format(fpga)

        cmd = "ssh arts@ccu-corr 'python $UPE/peripherals/util_bsn_monitor.py --unb {unb} {nodes} -n 2 -r {link} -s INPUT'".format(
              unb=self.args.unb, nodes=nodes, link=link)
        print cmd
        os.system(cmd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rt', type=str, help="Dish to disable", required=True)
    parser.add_argument('--pol', type=str, default='XY', 
                        help="Polarization to disable (Default: %(default)s)")
    parser.add_argument('--unb', type=str, default='0:15',
                        help="Central uniboards to use (Default: %(default)s)")

    args = parser.parse_args()

    # ensure upper case
    args.rt = args.rt.upper()
    args.pol = args.pol.upper()

    # check pol
    valid_pol = ('X', 'Y', 'XY')
    if not args.pol.upper() in valid_pol:
        print "--pol should be on of {}".format(valid_pol)
        sys.exit(1)

    dd = DisableDish(args)
    dd.disable()
