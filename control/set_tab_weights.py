#!/usr/bin/env python

import sys
from textwrap import dedent
import argparse
import numpy as np

try:
    from pi_arts_tab_beamformer_weights import BeamformerWeights
    import test_case
    import node_io
except ImportError:
    sys.stderr.write("Cannot import uniboard environment.\nCheck you are running "
                     "on ccu-corr and veriy PYTHONPATH includes the uniboard env\n")
    sys.exit(1)


class TABWeights(object):

    def __init__(self, science_case, mode, dish, **kwargs):
        """
        Set TAB weights
        science_case: 3 or 4
        mode: survey/fly/coherence
        dishes: comma-separated list of dishes
        kwargs: ignored
        """
        num_beamlet = 1
        num_weight_bits = 9
        # settings
        if science_case == 3:
            num_dish = 8
            num_tab = 9
        else:
            num_dish = 10
            num_tab = 12
        self.num_tab = num_tab
        self.num_dish = num_dish
        self.science_case = science_case
        self.dish = dish.split(',')

        # Initalize weight utility
        # test case uses sys.argv for settings
        app = 'arts_sc{:.0f}'.format(science_case)
        del sys.argv[1:]
        sys.argv.extend(['--app', app, '--unb', '0:15', '--fn', '0:3', '--bn', '0:3', '--tel', dish, '-v', '2'])
        tc = test_case.Testcase('UTIL - ', '')
        tc.set_result('PASSED')
        tc.append_log(0, '>>> Title : Set TAB weights on %s' % tc.unb_nodes_string(''))
        io = node_io.NodeIO(tc.nodeImages, tc.base_ip)
        self.bf_weights = BeamformerWeights(tc, io, n_tabs=num_tab, n_inputs=num_dish, n_beamlets=num_beamlet,
                                            n_weight_bits=num_weight_bits)
        # cmd 3 is to set weight per TAB
        self.bf_weights.set_cmd(cmd=3)


        # first set all weights to zero
        self.set_zero()
        # then enable append mode so weights do not get overwritten in for loops
        self.bf_weights.append = True
        # then set weights for requested mode
        if mode == 'survey':
            self.set_weights_survey()
        elif mode == 'fly':
            self.set_weights_fly()
        elif mode == 'coherence':
            self.set_weights_coherence()

        return

    def set_zero(self):
        """
        Set all TAB weights to zero
        """
        self.bf_weights.select(tabs=range(self.num_tab), inputs=range(self.num_dish))
        self.bf_weights.set_weights(complex(0, 0))
        self.bf_weights.run()

    def set_weights_survey(self):
        """
        Set weights for survey mode
        TAB 0 = central beam
        TAB 1 = 1 HPWB offset from TAB 0
        ...
        TAB 11 = 11 HPWB offsets from TAB 0 = -1 HPBW offset from TAB 0
        """
        for tab in range(self.num_tab):
            for dish in range(self.num_dish):
                phase = 2 * np.pi * dish * tab/float(self.num_tab)
                norm = max(255.0/np.sqrt(len(self.dish)), 200)
                weight_re = int(round(norm * np.cos(phase)))
                weight_im = int(round(norm * np.sin(phase)))
                self.bf_weights.select(tabs=[tab], inputs=[dish])
                self.bf_weights.set_weights(complex(weight_re, weight_im))
                self.bf_weights.run()
        
    def set_weights_fly(self):
        """
        Set weights for flys eye mode
        TAB  0 = RT2
        TAB  1 = RT3
        ...
        TAB  8 = RTA (SC4) / 0 (SC3)
        TAB  9 = RTB (SC4) / 0 (SC3)
        TAB 10 = 0
        TAB 11 = 0
        
        """
        for dish in range(self.num_dish):
            tab = dish
            # max weight per dish
            weight_re = 255.0
            weight_im = 0
            self.bf_weights.select(tabs=[tab], inputs=[dish])
            self.bf_weights.set_weights(complex(weight_re, weight_im))
            self.bf_weights.run()

    def set_weights_coherence(self):
        """
        Set weights for coherence testing mode
        TAB  0 = RT2
        TAB  1 = RT2 - RT3
        ...
        TAB  7 = RT2 - RT9
        TAB  8 = RT2 - RTA (SC4) / 0 (SC3)
        TAB  9 = RT2 - RTB (SC4) / 0 (SC3)
        TAB 10 = 0
        TAB 11 = 0
        """
        # max TAB index = max dish index
        for tab in range(self.num_dish):
            n_dish = tab + 1
            inputs = range(n_dish)
            weight_re = max(255.0/np.sqrt(n_dish), 200)
            weight_im = 0
            self.bf_weights.select(tabs=[tab], inputs=range(n_dish))
            self.bf_weights.set_weights(complex(weight_re, weight_im))
            self.bf_weights.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Set ARTS TAB weights. Run with -H for extended help")
    parser.add_argument('--science_case', type=int, default=4, choices=[3, 4], help="ARTS science case (default: %(default)s)")
    parser.add_argument('--mode', default='survey', choices=['survey', 'fly', 'coherence'],  help="ARTS TAB mode (default: %(default)s)")
    parser.add_argument('--dish', help="Comma-separated list of dishes to use. Default: RT2-9 for SC3, RT2-B for SC4")

    parser.add_argument('-H', action='store_true', help="Show extended help")

    args = parser.parse_args()

    # extended help
    if args.H:
        print dedent("""\
        This utility sets the ARTS TAB beamformer weights in the central system.
        Dishes that were not enabled when setting up the firmware will remain *disabled* even
        when trying to enable them through this utility.

        Supported modes are:
        survey = normal suvey operations: the TAB cover the full field of view of the compound beams
        fly = fly's eye mode: each TAB corresponds to a different dish, TAB0 = RT2, TAB1=RT3, etc.
        coherence = coherence testing mode: each TAB coresponds to a different sum of dishes, TAB0 = RT2, TAB1 = RT2 and RT3, etc.
        """)
        sys.exit(0)

    # set dishes
    if not args.dish:
        if args.science_case == 3:
            args.dish = '2,3,4,5,6,7,8,9'
        else:
            args.dish = '2,3,4,5,6,7,8,9,a,b'

    # apply the weights
    TABWeights(**vars(args))
