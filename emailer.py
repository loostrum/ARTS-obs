#!/usr/bin/env python
#
# Send trigger emails 
# Author: L.C. Oostrum

import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


if __name__ == '__main__':
    frm = "ARTS FRB Detection System <arts@arts041.apertif>"
    to = "oostrum@astron.nl"
    files = ["empty.pdf"]

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "subject"
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

    <hr />

    <p><h2>FRB Detections</h2><br />
    <b>SNR&emsp;Time&emsp;DM&emsp;Length&emsp;Beam</b><br />
    </p>

    <hr .>

    <p><h2>Beam positions</h2><br />
    <b>Beam&emsp;RA&emsp;DEC&emsp;Gl&emsp;Gb</b><br />
    </p>

    </body>
    </html>"""

    msg.attach(MIMEText(txt, 'html'))

    for fname in files or ():
        with open(fname, 'rb') as f:
            part = MIMEApplication(f.read(), Name=os.path.basename(fname))
        part['Content-Disposition'] = 'attachment; filename="{}"'.format(os.path.basename(fname))
        msg.attach(part)

    smtp = smtplib.SMTP()
    smtp.connect()
    smtp.sendmail(frm, to, msg.as_string())
    smtp.close()
