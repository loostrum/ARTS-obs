#!/usr/bin/env python
#
# Send trigger emails 
# Author: L.C. Oostrum

import os
import sys
import ast
from time import sleep

import numpy as np
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def log(message):
    """
    Log a message. Prints the hostname, then the message
    """
    print "Master-emailer: {}".format(message)


if __name__ == '__main__':
    master_dir = sys.argv[1]
    expected_beams = np.array(ast.literal_eval(sys.argv[2]), dtype=int)
    nbeam = len(expected_beams)

    # load coordinate file
    coord_file = os.path.join(master_dir, 'coordinates.txt')
    # columns are beam, ra, dec, gl, gb
    coordinates = np.loadtxt(coord_file, dtype=str, ndmin=2)
    # convert to html
    beaminfo = ""
    for line in coordinates:
        beaminfo += "<tr>"
        for val in line:
            beaminfo += "<td>{}</td>".format(val)
        beaminfo += "</tr>"
        

    log("Expecting {} beams".format(nbeam))
    # wait until summary file for all beams is present
    received_beams = 0
    while received_beams < nbeam:
        received_beams = 0
        for beam in expected_beams:
            summary_file = os.path.join(master_dir, "CB{:02d}_summary.yaml".format(beam))
            if os.path.isfile(summary_file):
                received_beams += 1 
        log("Received {} out of {} beams".format(received_beams, nbeam))
        sleep(5)

    # create email

    frm = "ARTS FRB Detection System <arts@arts041.apertif>"
    to = "oostrum@astron.nl"
    files = ['empty.pdf']

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "ARTS FRB Detection System"
    msg['From'] = frm
    msg['To'] = to

    txt="""<html>
    <head><title>FRB Alert System</title></head>
    <body>

    <p><b>UTC START</b><br />
    <b>Source</b><br />
    <b>NE2001 DM</b><br />
    <b>YMW16 DM</b><br />
    </p>

    <hr align="left" width="50%" />

    <p><h2>FRB Detections</h2><br />
    <b>Probablitiy&emsp;SNR&emsp;Time&emsp;DM&emsp;Length&emsp;Beam</b><br />
    </p>

    <hr align="left" width="50%" />

    <p><h2>Beam positions</h2><br />
    <table style="width:80%">
    <tr style="text-align:left">
        <th>Beam</th>
        <th>RA</th>
        <th>DEC</th>
        <th>Gl</th>
        <th>Gb</th>
    </tr>
    {beaminfo}
    </table>
    </p>

    </body>
    </html>""".format(beaminfo=beaminfo)

    msg.attach(MIMEText(txt, 'html'))

    for fname in files or ():
        with open(fname, 'rb') as f:
            part = MIMEApplication(f.read(), 'pdf', Name=os.path.basename(fname))
        part['Content-Disposition'] = 'attachment; filename="{}"'.format(os.path.basename(fname))
        msg.attach(part)

    smtp = smtplib.SMTP()
    smtp.connect()
    smtp.sendmail(frm, to, msg.as_string())
    smtp.close()
