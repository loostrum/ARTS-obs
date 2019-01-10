#!/usr/bin/env python
# 
# Create pulsar inspection plot on worker node

import os
import sys
import socket

from argparse import ArgumentParser, RawTextHelpFormatter

def main(args):
    kwargs = vars(args)

    # get CB from host name
    hostname = socket.gethostname()
    kwargs['cb'] = "{:02d}".format(int(hostname[5:7]) - 1)
    # Set up file name and dir
    kwargs['data_dir'] = "{obs_dir}/filterbank".format(**kwargs)
    kwargs['fname'] = "{data_dir}/CB{cb}.fil".format(**kwargs)

    # check paths
    if not os.path.isdir(kwargs['data_dir']):
        print "FAILED - Data directory {} does not exist.".format(kwargs['data_dir'])
        exit()
    if not os.path.isfile(kwargs['fname']):
        print "FAILED - File {} does not exist.".format(kwargs['fname'])
        exit()

    # try to find par file, otherwise use psr option
    psr =  kwargs['obs_dir'].strip('/').split('.')[-1]
    parfile = "{}/tzpar/{}.par".format(os.environ['TEMPO'], psr[1:])
    if not os.path.isfile(parfile):
        opt = "-psr {}".format(psr)
    else:
        opt = "-par {}".format(parfile)

    # run fold in data directory
    os.chdir(kwargs['data_dir'])
    rfifind_cmd = "rfifind -time 1 -timesig 5 -freqsig 3 -o CB{cb}" \
                  " CB{cb}.fil".format(**kwargs)
    print "Running rfifind command: {}".format(rfifind_cmd)
    os.system(rfifind_cmd)
    prepfold_cmd = "prepfold -n 64 -nsub 128 -nodmsearch -nopdsearch {opt}" \
                   " -noxwin -mask CB{cb}_rfifind.mask -filterbank" \
                   " {fname}".format(opt=opt, **kwargs)
    print "Running prepfold command: {}".format(prepfold_cmd)
    os.system(prepfold_cmd)
    print "Done"

if __name__ == '__main__':
    home = os.path.expanduser('~')

    parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
    parser.add_argument('--obs_dir', type=str, help="Output folder of observation", required=True)

    # print help if not arguments are supplied
    if len(sys.argv) == 1:
        parser.print_help()
        exit()

    args = parser.parse_args()
    main(args)
