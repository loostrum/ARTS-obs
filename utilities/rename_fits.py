#!/usr/bin/env python
#
# rename tabA.fits etc to the name required by ATDB/ALTA

import os
import sys
import argparse


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Rename fits files for ATDB")
    parser.add_argument('--output_dir', type=str, help="Observation directory", required=True)
    parser.add_argument('--beam', type=int, help="CB number", required=True)
    parser.add_argument('--taskid', type=str, help="Task ID", required=True)
    parser.add_argument('--ntabs', type=int, help="Number of TABs", required=True)

    args = parser.parse_args()
    config = vars(args)

    fits_dir = "{output_dir}/fits/CB{beam:02d}".format(**config)
    os.chdir(fits_dir)

    # IAB mode: one dataproduct
    if config['ntabs'] == 1:
        input_name = "tabA.fits"
        output_name = "ARTS{taskid}_CB{beam:02d}.fits".format(**config) 
        sys.stdout.write("Renaming {} to {}\n".format(input_name, output_name))
        os.rename(input_name, output_name)

    # TAB mode: multiple dataproducts
    else:
        mapping = {1:'A', 2:'B', 3:'C', 4:'D', 5:'E', 6:'F', 7:'G', 8:'H', 9:'I', 10:'J', 11:'K', 12:'L'}
        for tab in range(1, config['ntabs']+1):
            input_name = "tab{}.fits".format(mapping[tab])
            output_name = "ARTS{taskid}_CB{beam:02d}_TAB{tab:02d}.fits".format(tab=tab, **config)
            sys.stdout.write("Renaming {} to {}\n".format(input_name, output_name))
            os.rename(input_name, output_name)
