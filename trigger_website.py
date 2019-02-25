#!/usr/bin/env python
#
# Publish observation info and trigger pdfs on a simple html page

import os
import sys
import glob
import yaml

def find_observations():
    config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_file, 'r') as f:
        config = yaml.load(f)
    try:
        master_dir = config['general']['master_dir']
    except KeyError:
        print "Master dir not found in config"
        sys.exit(1)
    except Exception as e:
        print "Failed to get master dir in config: {}".format(e)
        sys.exit(1)

    home = os.path.expanduser('~')
    master_dir = master_dir.replace('{date}/{datetimesource}', '').format(home=home)

    # get dates
    date_glob = os.path.join(master_dir, '[0-9]'*8)
    date_all = glob.glob(date_glob)
    print date_all


if __name__ == '__main__':
    find_observations()

