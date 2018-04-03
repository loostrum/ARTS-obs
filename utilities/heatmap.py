#!/usr/bin/env python
#
# Create heat map of triggers per beam

import os
import sys
import argparse

import numpy as np
import yaml
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.colors import Normalize
from matplotlib.colors import LogNorm
from matplotlib.colorbar import ColorbarBase
from matplotlib.patches import Rectangle
from mpl_toolkits.axes_grid1 import make_axes_locatable


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Plot heat map of triggers in each compound beam")
    # path to trigger file
    parser.add_argument("folder", type=str, help="folder with observation summary files")
    # which triggers to plot
    parser.add_argument("--field", type=str, help="Which field to plot, can be raw, trigger, classifier (Default: raw)", 
                        default="raw")

    args = parser.parse_args()

    if not os.path.isdir(args.folder):
        print "Cannot find folder {}".format(args.folder)
        sys.exit(1)
    if not args.field in ('raw', 'trigger', 'classifier'):
        print "Field invalid: {}. Valid options are raw, trigger, classifier".format(field)
        sys.exit(1)


    # rectangle sizes
    width = 2
    height = 1

    # map of CB to x,y coordinate of lower left corner
    beams = range(40)
    coords = ((-4.5,2.5), (-2.5,2.5), (-0.5,2.5), (-3.5,3.5), (None, None), (1.5,2.5), (-3.5,1.5), (-1.5,1.5), (-1.5,3.5), (None, None), (0.5,1.5), (2.5,1.5), (-4.5,0.5), (0.5,3.5), (None,None), (-2.5,0.5), (-0.5,0.5), (1.5,0.5), (2.5,3.5), (None, None), (-3.5,-0.5), (-1.5,-0.5), (0.5,-0.5), (-4.5,-3.5), (None,None), (2.5,-0.5), (-4.5,-1.5), (-2.5,-1.5), (-2.5,-3.5), (None,None), (-0.5,-1.5), (1.5,-1.5), (-3.5,-2.5), (-0.5,-3.5), (None, None), (-1.5,-2.5), (0.5,-2.5), (2.5,-2.5), (1.5,-3.5), (None,None))
    coordmap = dict(zip(beams, coords))

    # load triggers
    triggers = {}
    for cb in beams:
        fname = os.path.join(args.folder, 'CB{:02d}_summary.yaml'.format(cb))
        if not os.path.isfile(fname):
            triggers[cb] = -np.inf  # so we can still do arithmetic with invalid beams
            continue
        else:
            with open(fname) as f:
                info = yaml.load(f)
                triggers[cb] = info["ncand_{}".format(args.field)]

    # create colorbar mappable
    vals = np.array(triggers.values())
    vals = vals[np.isfinite(vals)]
    minval = np.amin(vals)
    maxval = np.amax(vals)
    norm = Normalize(minval, maxval)
    #norm = LogNorm(minval, maxval)


    fig, ax = plt.subplots()
    for cb in coordmap.keys():
        x0, y0 = coordmap[cb]
        if not (x0 is None and  y0 is None):
            rect = Rectangle((x0, y0), width, height, facecolor=cm.Reds(norm(triggers[cb])), alpha=1, edgecolor='k')
            ax.add_artist(rect)
            # add label
            x = x0 + width / 2.
            y = y0 + height / 2.
            ax.text(x, y, "{:02d}".format(cb), ha='center', va='center')

    ax.set_xlim(-4.5, 4.5)
    ax.set_ylim(-3.5, 4.5)
    ax.set_aspect('equal')
    ax.set_xlabel('<- RA')
    ax.set_ylabel('<- DEC')
    # add colorbar
    div = make_axes_locatable(ax)
    cax = div.new_horizontal(size="5%", pad=0.05)
    ColorbarBase(cax, cmap=cm.Reds, norm=norm, orientation='vertical')
    fig.add_axes(cax)
    plt.savefig('beammap.pdf')
    plt.close(fig)
