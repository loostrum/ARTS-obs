#!/usr/bin/env python
#
# Send trigger emails 
# Author: L.C. Oostrum

import os
import sys
import ast
import socket
import smtplib
from time import sleep
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import numpy as np
import yaml


def log(message):
    """
    Log a message. Prepends mesage with a fixed string
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
    coordinfo = ""
    for line in coordinates:
        coordinfo += "<tr>"
        for val in line:
            coordinfo += "<td>{}</td>".format(val)
        coordinfo += "</tr>"

    # load obs info file
    info_file = os.path.join(master_dir, 'info.yaml')
    with open(info_file, 'r') as f:
        obsinfo = yaml.load(f)
        
    # wait until summary file for all beams is present
    log("Expecting {} beams".format(nbeam))
    received_beams = 0
    while received_beams < nbeam:
        sleep(5)
        received_beams = 0
        for beam in expected_beams:
            summary_file = os.path.join(master_dir, "CB{:02d}_summary.yaml".format(beam))
            if os.path.isfile(summary_file):
                received_beams += 1 
        log("Received {} out of {} beams".format(received_beams, nbeam))

    # load beam stats
    log("Loading stats and triggers")
    triggers = {}
    attachments = []
    beamstats = ""
    for i, beam in enumerate(expected_beams):
        summary_file = os.path.join(master_dir, "CB{:02d}_summary.yaml".format(beam))
        with open(summary_file, 'r') as f:
            summary = yaml.load(f)
        beamstats += "<tr><td>{:02d}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(beam, summary['ncand_raw'], summary['ncand_trigger'], summary['ncand_classifier'])
        if summary['success']:
            trigger_file = os.path.join(master_dir, "CB{:02d}_triggers.txt".format(beam))
            triggers[beam] = np.loadtxt(trigger_file, dtype=str, ndmin=2)
            attachments.append(os.path.join(master_dir, "CB{:02d}_candidates.pdf".format(beam)))

    # convert triggers to one big numpy array we can sort
    alltriggers = []
    for beam in triggers.keys():
        for trigger in triggers[beam]:
            trigger = np.concatenate([trigger, np.array(["{:02d}".format(beam)])])
            alltriggers.append(tuple(trigger))
    dtypes = [('SNR', 'S10'), ('DM', 'S10'), ('Width', 'S10'), ('T0', 'S10'), ('p', 'S10'), ('beam', 'S10')]
    alltriggers = np.array(alltriggers, dtype=dtypes)
    # sort by p, then SNR if equal
    alltriggers = np.sort(alltriggers, order=('p', 'SNR'))[::-1]
    

    # convert triggers to html
    # cols of trigger:  SNR DM Width T0 p beam
    # order in email: p SNR DM T0 Width beam
    # nrs: 4 0 1 3 2 5
    triggerinfo = ""
    for line in alltriggers:
        triggerinfo += "<tr><td>{4}</td><td>{0}</td><td>{1}</td><td>{3}</td><td>{2}</td><td>{5}</td></tr>".format(*line)
    
        
    # create email
    # kwarg for tables
    kwargs = dict(beamstats=beamstats, coordinfo=coordinfo, triggerinfo=triggerinfo)
    # add obs info
    kwargs.update(obsinfo)
    frm = "ARTS FRB Alert System <arts@{}.apertif>".format(socket.gethostname())
    #to = ["oostrum@astron.nl", "connor@astron.nl"]
    #to = ["oostrum@astron.nl"]
    to = ["arts-alerts@astron.nl"]

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "ARTS FRB Alert System @ {}".format(datetime.utcnow())
    msg['From'] = frm
    msg['To'] = ", ".join(to)

    txt="""<html>
    <head><title>FRB Alert System</title></head>
    <body>


    <p>
    <table style="width:20%">
    <tr>
        <th style="text-align:left">UTC start</th><td colspan="4">{utcstart}</td>
    </tr><tr>
        <th style="text-align:left">Source</th><td colspan="4">{source}</td>
    </tr><tr>
        <th style="text-align:left">Observation duration</th><td colspan="4">{tobs}</td>
    </tr><tr>
        <th style="text-align:left">NE2001 DM (central beam)</th><td colspan="2">TBD</td>
    </tr><tr>
        <th style="text-align:left">YMW16 DM (central beam)</th><td colspan="2">{ymw16}</td>
    </tr>
    </table>
    </p>
    

    <hr align="left" width="50%" />

    <p><h2>FRB Detections</h2><br />
    <table style="width:50%">
    <tr style="text-align:left">
        <th>Probability</th>
        <th>SNR</th>
        <th>DM (pc/cc)</th>
        <th>Arrival time (s)</th>
        <th>Width (ms)</th>
        <th>CB</th>
    </tr>
    {triggerinfo}
    </table>
    </p>

    <hr align="left" width="50%" />

    <p><h2>Compound Beam statistics</h2><br />
    <table style="width:50%">
    <tr style="text-align:left">
        <th>CB</th>
        <th>Raw candidates</th>
        <th>Candidates after grouping</th>
        <th>Candidates after classifier</th>
    </tr>
    {beamstats}
    </table>
    </p>

    <hr align="left" width="50%" />

    <p><h2>Compound Beam positions</h2><br />
    <table style="width:50%">
    <tr style="text-align:left">
        <th>CB</th>
        <th>RA</th>
        <th>DEC</th>
        <th>Gl</th>
        <th>Gb</th>
    </tr>
    {coordinfo}
    </table>
    </p>

    </body>
    </html>""".format(**kwargs)

    msg.attach(MIMEText(txt, 'html'))

    for fname in attachments or ():
        with open(fname, 'rb') as f:
            part = MIMEApplication(f.read(), 'pdf', Name=os.path.basename(fname))
        part['Content-Disposition'] = 'attachment; filename="{}"'.format(os.path.basename(fname).replace('_candidates', ''))
        msg.attach(part)

    log("Sending email to: {}".format(", ".join(to)))
    smtp = smtplib.SMTP()
    smtp.connect()
    try:
        smtp.sendmail(frm, to, msg.as_string())
    except smtplib.SMTPSenderRefused:
        # assume attachments are too large
        # resend without attachments
        # first element of payload is main text, rest are attachments
        msg.set_payload(msg.get_payload()[0])
        smtp.sendmail(frm, to, msg.as_string())
        
    smtp.close()
