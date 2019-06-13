'''Copy specific columns from one spreadsheet with data to another.

In this case, the contrib table has the proof-read abstracts, but the
abstr0518 tables has the current scheduling information.
'''

import csv
from astropy.table import Table, join


def read_csv(filename):
    out = []
    with open(filename, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            out.append(row)
    abstr = Table(rows=out[1:], names=out[0])
    return abstr[abstr['Timestamp'] != '']

allabstr = read_csv('../data/abstr0518.csv')
contrib = read_csv('../data/contribtalks.csv')

contrib.remove_columns(['day', 'time'])
allabstr.keep_columns(['Email Address', 'day', 'time'])

newcon = join(contrib, allabstr)
newcon.write('../data/contribtalks2.csv', format='ascii.csv')
