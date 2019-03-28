#!/usr/bin/env python
#
# Send trigger emails 
# Author: L.C. Oostrum

import os
import shutil
import sys
import ast
import socket
import smtplib
from time import sleep
from datetime import datetime
import errno
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import numpy as np
import yaml

CONFIG = "config.yaml"
WEBDIR='{home}/public_html/triggers'.format(home=os.path.expanduser('~'))

def log(message):
    """
    Log a message. Prepends mesage with a fixed string
    """
    print "Master-emailer: {}".format(message)


if __name__ == '__main__':
    master_dir = sys.argv[1]
    expected_beams = np.array(ast.literal_eval(sys.argv[2]), dtype=int)
    try:
        ntab = int(sys.argv[3])
    except IndexError:
        # old IAB mode
        ntab = 1
    nbeam = len(expected_beams)

    # load config file
    config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), CONFIG)
    with open(config_file, 'r') as f:
        config = yaml.load(f)['emailer']
    # message recipients
    to = ", ".join(config['to'])

    # get obs date and name from master dir
    obsdate, obsname = master_dir.split('/')[-2:]
    # get full path for web dir
    web_path = os.path.join(WEBDIR, obsdate, obsname)
    http_link = 'http://arts041.apertif/~arts/triggers/{}/{}'.format(obsdate, obsname)
    # create the directory
    upload = True
    try:
        os.makedirs(web_path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            log("Failed to create web path, will not upload triggers. ({})".format(e))
            upload = False

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
        beamstats += "<tr><td>{:02d}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(beam, summary['ncand_raw'], summary['ncand_trigger'], summary['ncand_skipped'], summary['ncand_classifier'])
        if summary['success']:
            trigger_file = os.path.join(master_dir, "CB{:02d}_triggers.txt".format(beam))
            triggers[beam] = np.loadtxt(trigger_file, dtype=str, ndmin=2)
            attachments.append(os.path.join(master_dir, "CB{:02d}_candidates_summary.pdf".format(beam)))

    # convert triggers to one big numpy array we can sort
    alltriggers = []
    for beam in triggers.keys():
        for trigger in triggers[beam]:
            trigger = np.concatenate([trigger, np.array(["{:02d}".format(beam)])])
            alltriggers.append(tuple(trigger))
    # try loading TAB
    have_TAB = True
    try:
        dtypes_tmp = [('SNR', float), ('DM', 'S10'), ('Width', 'S10'), ('T0', 'S10'), ('p', float), ('TAB', 'S10'), ('beam', 'S10')]
        dtypes = [('SNR', 'S10'), ('DM', 'S10'), ('Width', 'S10'), ('T0', 'S10'), ('p', 'S10'), ('TAB', 'S10'), ('beam', 'S10')]
        alltriggers = np.array(alltriggers, dtype=dtypes_tmp)
    except ValueError:
        dtypes_tmp = [('SNR', float), ('DM', 'S10'), ('Width', 'S10'), ('T0', 'S10'), ('p', float), ('beam', 'S10')]
        dtypes = [('SNR', 'S10'), ('DM', 'S10'), ('Width', 'S10'), ('T0', 'S10'), ('p', 'S10'), ('beam', 'S10')]
        have_TAB = False
        alltriggers = np.array(alltriggers, dtype=dtypes_tmp)
    # sort by p, then SNR if equal
    alltriggers = np.sort(alltriggers, order=('p', 'SNR'))[::-1]
    # convert SNR and p back to string
    plist = ["{:.2f}".format(p) for p in alltriggers['p']]
    snrlist = ["{:.2f}".format(snr) for snr in alltriggers['SNR']]
    alltriggers = np.array(alltriggers, dtype=dtypes)
    alltriggers['p'] = np.array(plist, dtype='S10')
    alltriggers['SNR'] = np.array(snrlist, dtype='S10')
    total_triggers = len(alltriggers)
    

    # convert triggers to html
    # cols of trigger:  SNR DM Width T0 p (TAB) beam
    # order in email: p SNR DM T0 Width beam (TAB)
    # nrs: 4 0 1 3 2 5 (no TAB)
    # 4 0 1 3 2 6 5 (with TAB)
    triggerinfo = ""
    ntrig_email = 0
    for line in alltriggers:
        if have_TAB:
            triggerinfo += "<tr><td>{4}</td><td>{0}</td><td>{1}</td><td>{3}</td><td>{2}</td><td>{6}</td><td>{5}</td></tr>".format(*line)
        else:
            triggerinfo += "<tr><td>{4}</td><td>{0}</td><td>{1}</td><td>{3}</td><td>{2}</td><td>{5}</td></tr>".format(*line)
        ntrig_email += 1
        if ntrig_email >= 250:
            if have_TAB:
                triggerinfo += "<tr><td>truncated</td><td>truncated</td><td>truncated</td><td>truncated</td><td>truncated</td><td>truncated</td><td>truncated</td></tr>"
            else:
                triggerinfo += "<tr><td>truncated</td><td>truncated</td><td>truncated</td><td>truncated</td><td>truncated</td><td>truncated</td></tr>"
                
            break

    # full info for html page
    triggerinfo_full = ""
    for line in alltriggers:
        if have_TAB:
            triggerinfo_full += "<tr><td>{4}</td><td>{0}</td><td>{1}</td><td>{3}</td><td>{2}</td><td>{6}</td><td>{5}</td></tr>".format(*line)
        else:
            triggerinfo_full += "<tr><td>{4}</td><td>{0}</td><td>{1}</td><td>{3}</td><td>{2}</td><td>{5}</td></tr>".format(*line)
    
        
    # create email
    # kwarg for tables
    kwargs = dict(beamstats=beamstats, coordinfo=coordinfo, triggerinfo=triggerinfo, total_triggers=total_triggers, http_link=http_link)
    webkwargs = dict(beamstats=beamstats, coordinfo=coordinfo, triggerinfo=triggerinfo_full, total_triggers=total_triggers, http_link=http_link)
    # add obs info
    kwargs.update(obsinfo)
    webkwargs.update(obsinfo)
    frm = "ARTS FRB Alert System <arts@{}.apertif>".format(socket.gethostname())

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "ARTS FRB Alert System Date: {utc_start} UTC; Field: {source}".format(**kwargs)
    msg['From'] = frm
    msg['To'] = to

    template = """<html>
    <head><title>FRB Alert System</title></head>
    <body>


    <p>
    <table style="width:20%">
    <tr>
        <th style="text-align:left">UTC start</th><td colspan="4">{utc_start}</td>
    </tr><tr>
        <th style="text-align:left">Source</th><td colspan="4">{source}</td>
    </tr><tr>
        <th style="text-align:left">Observation duration</th><td colspan="4">{tobs}</td>
    </tr><tr>
        <th style="text-align:left">Classifier probability threshold</th><td colspan="4">0.5</td>
    </tr><tr>
        <th style="text-align:left">NE2001 DM (central beam)</th><td colspan="2">TBD</td>
    </tr><tr>
        <th style="text-align:left">YMW16 DM (central beam)</th><td colspan="2">{ymw16}</td>
    </tr><tr>
        <th style="text-align:left">Total number of candidates</th><td colspan="2">{total_triggers}</td>
    </tr><tr>
        <th style="text-align:left">Trigger web link</th><td colspan="2">{http_link}</td>
    </tr>
    </table>
    </p>

    <hr align="left" width="50%" />

    <p><h2>Compound Beam statistics</h2><br />
    <table style="width:50%">
    <tr style="text-align:left">
        <th>CB</th>
        <th>Raw candidates</th>
        <th>Candidates after grouping</th>
        <th>Candidates below local S/N threshold</th>
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

    <hr align="left" width="50%" />

    <p><h2>FRB Detections</h2><br />
    <table style="width:50%">
    <tr style="text-align:left">
        <th>Probability</th>
        <th>S/N</th>
        <th>DM (pc/cc)</th>
        <th>Arrival time (s)</th>
        <th>Width (ms)</th>
        <th>CB</th>
        <th>TAB</th>
    </tr>
    {triggerinfo}
    </table>
    </p>

    </body>
    </html>"""

    emailtxt = template.format(**kwargs)
    webtxt = template.format(**webkwargs)


    msg.attach(MIMEText(emailtxt, 'html'))

    # Add files to website
    for fname in attachments or ():
        outname = os.path.join(web_path, os.path.basename(fname).replace('_candidates_summary', ''))
        shutil.copyfile(fname, outname)
    # add info html to website
    info_html = os.path.join(web_path, 'info.html')
    with open(info_html, 'w') as f:
        f.writelines(webtxt)
        

    # Add files to email
    for fname in attachments or ():
        with open(fname, 'rb') as f:
            part = MIMEApplication(f.read(), 'pdf', Name=os.path.basename(fname))
        part['Content-Disposition'] = 'attachment; filename="{}"'.format(os.path.basename(fname).replace('_candidates_summary', ''))
        msg.attach(part)
    
            

    log("Sending email to: {}".format(to))
    smtp = smtplib.SMTP()
    smtp.connect()
    try:
        smtp.sendmail(frm, to, msg.as_string())
    except smtplib.SMTPSenderRefused as e:
        # assume attachments are too large
        # resend without attachments
        # first element of payload is main text, rest are attachments
        log('Could not send email, trying again without attachments')
        msg.set_payload(msg.get_payload()[0])
        smtp.sendmail(frm, to, msg.as_string())
        
    smtp.close()
