#!/usr/bin/env python
#
# 
# Author: L.C. Oostrum

import os
import sys

if __name__ == '__main__':
    beams = range(41)

    online_links = []
    for beam in beams:
        node = beam + 1
        hostname = "arts0{:02d}.40g.apertif".format(node)
        cmd = "ping -W 1 -c 1 {} > /dev/null".format(hostname)
        if os.system(cmd) == 0:
            online_links.append("{:02d}".format(beam))
        else:
            if beam == 40:
                sys.stderr.write("WARNING: skipping offline link: Master @ {}\n".format(hostname))
            else:
                sys.stderr.write("WARNING: skipping offline link: CB{:02d} @ {}\n".format(beam, hostname))

    print ','.join(online_links)
