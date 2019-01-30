#!/usr/bin/env python

import subprocess
import time

########################################################################
# Execute ifconfig twice with a one second interval to find the number 
# of packets received per second.
########################################################################

#NICS = ['eno1', 'ens21']
NICS = ['ens21']

for nic in NICS:

    cmd = 'ifconfig'
    args = nic
    
    cmd_output = []
    rx_packets_str = []
    rx_packets = []
    rx_bytes_str = []
    rx_bytes = []
    tx_packets_str = []
    tx_packets = []
    tx_bytes_str = []
    tx_bytes = []

    for i in range(2):
        p = subprocess.Popen([cmd, args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        cmd_output.append(out)
        time.sleep(1)

    for i in range(2):
        string_list = cmd_output[i].split()    
        rx_packets_str.append(string_list[23])
        rx_bytes_str.append(string_list[25])
        tx_packets_str.append(string_list[39])
        tx_bytes_str.append(string_list[41])
        rx_packets.append(int(rx_packets_str[i])) #.split(':')[1]))
        rx_bytes.append(int(rx_bytes_str[i])) #.split(':')[1]))
        tx_packets.append(int(tx_packets_str[i])) #.split(':')[1]))
        tx_bytes.append(int(tx_bytes_str[i])) #.split(':')[1]))

    rx_packets_per_second = rx_packets[1]-rx_packets[0]
    rx_gigabits_per_second = (float(rx_bytes[1]-rx_bytes[0])*8)/1000000000
    tx_packets_per_second = tx_packets[1]-tx_packets[0]
    tx_gigabits_per_second = (float(tx_bytes[1]-tx_bytes[0])*8)/1000000000
    print '\n', nic, 'Receiving:'
    print rx_packets_per_second, 'packets per second'
    print rx_gigabits_per_second, 'Gbps\n'
    print nic, 'Sending:'
    print tx_packets_per_second, 'packets per second'
    print tx_gigabits_per_second, 'Gbps\n'

