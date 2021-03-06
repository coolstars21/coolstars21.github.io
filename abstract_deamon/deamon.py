import sys
import os
import smtplib
import subprocess
from warnings import warn
from tempfile import TemporaryDirectory
from email.message import EmailMessage
import re
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from astropy.table import Table
import gspread
from oauth2client.service_account import ServiceAccountCredentials

sys.path.append('../pagepy')
from contributions import process_google_form_value


def compile_pdf(dat):
    template = env.get_template('single_abstract.tex')
    with TemporaryDirectory() as tempdir:
        with open(os.path.join(tempdir, 'abstract.tex'), "w") as tex_out:
            tex_out.write(template.render(t=dat))

        out = 'Rerun'
        while 'Rerun' in str(out):
            latex = subprocess.Popen(['pdflatex', '-interaction=nonstopmode',
                                      os.path.join(tempdir, 'abstract')],
                                     cwd=tempdir,
                                     stdout=subprocess.PIPE)
            out, err = latex.communicate()

        with open(os.path.join(tempdir, 'abstract.pdf'), 'rb') as fp:
            pdf_data = fp.read()
    return pdf_data


def set_timestamp(sheet, col, row, status=''):
    '''Put timestamp into a specific cell in a Google sheet.

    The timestamp is written in the same string format that Google uses
    by default to mark the time a Google from entry was written.

    Parameters
    ----------
    sheet : gspread worksheet
    col : int
        column number (0 based as in Python)
    row : int
        row number (0 based as in Python)
    status : string
        A prefix to the time stamp. This can be used to
        mark a cell that is currently processed.
    '''
    val = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
    sheet.update_cell(row + 1, col + 1, status + val)


def send_conf_email(dat):
    if len(dat) != 1:
        raise ValueError('Table with data for email needs to have exactly one row.')
    with open('../../gmail.txt') as f:
        password = f.read()
    password = password[:-1]
    process_google_form_value(dat, autoacceptposters=True)

    # Create the container email message.
    msg = EmailMessage()
    msg['From'] = 'coolstarsbot@gmail.com'
    msg['To'] = dat['Email Address']
    msg['Subject'] = 'CS20 Abstract submission - proofs'
    emailtext = env.get_template('abstract_email.txt')
    msg.set_content(emailtext.render(dat=dat[0]))
    msg.preamble = 'HTML and PDF files are attached, but it seems your email reader is not MIME aware.\n'

    htmltext = env.get_template('single_abstract.html')
    msg.add_attachment(htmltext.render(row=dat[0]),
                       subtype='html',
                       filename='abstract.html')
    pdf_data = compile_pdf(dat[0])
    msg.add_attachment(pdf_data,
                       filename='abstract.pdf',
                       maintype='application', subtype='pdf')

    with smtplib.SMTP('smtp.gmail.com', 587) as s:
        s.ehlo()
        s.starttls()
        s.login(msg['From'], password)
        s.send_message(msg)
    print('{}: Send email to: {}'.format(datetime.now().strftime('%m/%d/%Y %H:%M:%S'),
                                             msg['To']))


env = Environment(loader=FileSystemLoader(['../templates']),
                  autoescape=select_autoescape(['html']))

parse_sheet_timestamp = re.compile("(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<year>[0-9]+) (?P<hour>[0-9]+):(?P<minute>[0-9]+):(?P<second>[0-9]+)")

# pip install --upgrade google-auth-oauthlib
# use creds to create a client to interact with the Google Drive API
scope = ['https://spreadsheets.google.com/feeds']
creds = ServiceAccountCredentials.from_json_keyfile_name('../../CS20Gkey.json', scope)
client = gspread.authorize(creds)

# Find a workbook by name and open the first sheet
# Make sure you use the right name here.
sheet = client.open("Cool Stars 20 abstract submission (Responses)").sheet1

list_of_lists = sheet.get_all_values()
g_sheet = Table(rows=list_of_lists[1:], names=list_of_lists[0])

ind_conf = list_of_lists[0].index('confemail')

for i, ts in enumerate(g_sheet['Timestamp']):
    match = parse_sheet_timestamp.match(ts)
    # The following loop is not written in the most concise way,
    # but is a way that makes it easy to follow the logic
    if match:
        # New entry. No conf email send yet or timestamp removed
        # by hand in sheet to trigger resending
        if g_sheet['confemail'][i] == '':
            set_timestamp(sheet, ind_conf, i + 1, status='Working on ')
            send_conf_email(g_sheet[[i]])
            set_timestamp(sheet, ind_conf, i + 1)
        else:
            matchconf = parse_sheet_timestamp.match(g_sheet['confemail'][i])
            if matchconf is None:
                warn('Cannot parse time for confemail: {}'.format(g_sheet['confemail'][i]))
            else:
                # entry has been modified
                if (datetime(**{k: int(v) for k, v in match.groupdict().items()}) >
                   datetime(**{k: int(v) for k, v in matchconf.groupdict().items()})):
                    set_timestamp(sheet, ind_conf, i + 1, status='Working on ')
                    send_conf_email(g_sheet[[i]])
                    set_timestamp(sheet, ind_conf, i + 1)
