import difflib
import re
import numpy as np
from astropy.table import Table
from astropy.table import join

from pagepy.abstracts import read_abstracts_table

### Step 0 - Check the abstract list ###
abstr = read_abstracts_table('../data/abstr0727.csv', autoacceptposters=False)
abstr['Email Address'] = [s.lower() for s in abstr['Email Address']]
ar, counts = np.unique(abstr['Email Address'], return_counts=True)
print('The following email addresses are associated with more than one abstract.')
print(ar[counts > 1])
print('')
ar, counts = np.unique(abstr['First author'], return_counts=True)
print('The following first authors submitted more than one abstract.')
print(ar[counts > 1])

### Step 1: Clean and check Jenine's file (i.e. remove canceled transactions etc.) ###
# - remove cancelled transaction
# - normalize name field in caps (some people use ALL CAPS NAMES)
# - remove title
jenine = Table.read('../data/jenine0727.csv', format='ascii')
# Remove rows at the end that don't have names in them
jenine = jenine[~jenine['Last Name'].mask]
# remove last row where headers are repeated
#jenine = jenine[:-1]
for c in ['First Name', 'Last Name']:
    # The following is not correct for "van Dyck" etc, but good enough to match
    # and we won't use those names later on anyway.
    jenine[c] = [s.capitalize() for s in jenine[c]]
jenine['Email'] = [s.lower() for s in jenine['Email']]

jenine['name'] = ['{} {}'.format(jenine['First Name'][i], jenine['Last Name'][i]) for i in range(len(jenine))]

# Make the registration type column that Jenine deleted (or something similar)
# paid = [float(r.replace('$','').replace('-', '0')) for r in jenine['Dollar Amount PD']]
# jenine['Registration Type'] = table.MaskedColumn(data=paid, mask=np.array(paid) < 400)

### Step 2: Identify people with waivers in Jenine's list ###
## 2a) LOC members
LOC = Table.read('data/LOCmembers.csv', format='ascii')
LOC['name'] = [n.replace('(chair)', '').strip() for n in LOC['name']]
LOC['waiver'] = 'LOC'
LOC['mergeid'] = np.arange(len(LOC))
# OK, this gives us exact matches in name
tab = join(jenine, LOC, join_type='left')
# Now for those that are not matched yet
for mid in LOC['mergeid']:
    if not mid in tab['mergeid']:
        dname = difflib.get_close_matches(LOC['name'][mid], tab['name'], cutoff=0.8)
        # and here comes some hand sorting
        print(dname)
        if dname == ['Sarah Schmidt']:
            dname = []
        if len(dname) == 0:
            print('No match found for {}'.format(LOC['name'][mid]))
        else:
            ind = tab['name'] == dname[0]
            print('Matching {} to {}'.format(LOC['name'][mid], dname[0]))
            for c in ['waiver', 'mergeid']:
                tab[c][ind] = LOC[c][mid]

print('The following LOC members are not yet registered')
print(LOC['name'][np.isin(LOC['mergeid'], tab['mergeid'][~tab['mergeid'].mask], invert=True)])
tab.remove_column('mergeid')
## 2b) financial aid recipients
finaid = Table.read('../data/financialaid.csv', format='ascii')
finaid.keep_columns(['Email Address', 'Name'])
finaid['waiver'] = 'aid'
# table has all applicants, now restrict to people with approved aid
finaid = finaid[:74]
finaid.remove_row(-3)  # declined aid, so remove from list, too.

# OK, this gives us exact matches in name
tab.rename_column('Email', 'Email Address')
finaid['mergeid'] = np.arange(len(finaid))
tab2 = join(tab, finaid, join_type='left', keys=['Email Address'])
# Which email addresses are matched more than once?
mid, n = np.unique(tab2['mergeid'], return_counts=True)
mids = mid[(n > 1) & ~(mid.mask)]
print('Financial aid email addresses that turn up more than once in the registration list')
for n in mids:
    print (finaid[n])
print('-----')
tab2.rename_column('waiver_1', 'waiver')
tab2['waiver'][~tab2['waiver_2'].mask] = tab2['waiver_2'][~tab2['waiver_2'].mask]
tab2.remove_column('waiver_2')
# Now for those that are not matched yet use name
for mid in finaid['mergeid']:
    if not mid in tab2['mergeid']:
        dname = difflib.get_close_matches(finaid['Name'][mid], tab2['name'], cutoff=0.7)
        if len(dname) == 0:
            print('No match found for {}'.format(finaid['Name'][mid]))
        else:
            if len(dname) > 1:
                print("Name {} appears more than once. Assigning to first occurence.".format(dname))
            dname = [dname[0]]
            ind = tab2['name'] == dname[0]
            print('Matching {} to {}'.format(finaid['Name'][mid], dname[0]))
            for c in ['waiver', 'mergeid']:
                tab2[c][ind] = finaid[c][mid]

print('')
print('The following fin aid people are not yet registered')
print(finaid[np.isin(finaid['mergeid'], tab2['mergeid'][~tab2['mergeid'].mask], invert=True)])
tab2.remove_column('mergeid')

print('')
print('The following people are marked as WAIVER by Jenine, but do not have a waiver:')
ind_jan_waive = tab2['Comments'] == 'WAIVED'
print(tab2[ind_jan_waive & (tab2['waiver'] == '')]['Name', 'Email Address'])

### The following people with waivers paid for registration
print("The following people with waivers paid for registration and should be refunded")
tab2[~tab2['Registration Type'].mask & ~tab2['waiver'].mask]['Name', 'Email Address', 'waiver','Registration Type']

#### Now match to the abstracts
abstrshort = abstr[:]
#abstrshort.keep_columns(['Email Address', 'First author', 'Title', 'PaymentID'])
abstrshort.rename_column('PaymentID', 'Tran#')
abstrshort['LastName'] = [s.split()[-1] for s in abstrshort['First author']]

abstrshort['mergeid'] = np.arange(len(abstrshort))
confreg = ~tab2['Registration Type'].mask
for c in ['One Day Conference: Jul. 30th, 2018',
          'One Day Conference: Jul. 31st, 2018',
          'One Day Conference: Aug 1st, 2018',
          'One Day Conference: Aug 2nd, 2018',
          'One Day Conference: Aug 3rd, 2018',
          'waiver']:
    confreg = confreg | ~tab2[c].mask

confreg = confreg | (tab2['Comments'] == 'PYMNT PENDING')

confreg = tab2[confreg]
inddays = ~tab2['One Day Conference: Jul. 30th, 2018'].mask
for c in ['One Day Conference: Jul. 30th, 2018',
          'One Day Conference: Jul. 31st, 2018',
          'One Day Conference: Aug 1st, 2018',
          'One Day Conference: Aug 2nd, 2018',
          'One Day Conference: Aug 3rd, 2018']:
    inddays = inddays | ~tab2[c].mask

inddays = inddays
print("Number of registrations with financial aid: {}".format((confreg['waiver'] == 'aid').sum()))
print("Number of registrations from LOC: {}".format((confreg['waiver'] == 'LOC').sum()))

print("Number of total registrations (full, one day, or waved): {}".format(len(confreg)))
print("Number of people who registered for one or more days individually: {}".format(inddays.sum()))
print("Number of paid full registration (early + normal + late): {}".format((~tab2['Registration Type'].mask ).sum()))

tab2.rename_column('Title', 'Nametitle')

tab3 = join(tab2, abstrshort, join_type='left', keys=['Email Address'])
# Make to string because that's the format the abstract table has
tab3['Tran#'] = ['{}'.format(i) for i in tab3['Tran#_1']]

# Which email addresses are matched more than once?
mid, n = np.unique(tab3['mergeid'], return_counts=True)
mids = mid[(n > 1) & ~(mid.mask)]
print('Abstract email addresses that turn up more than once in the registration list')
for n in mids:
    print (abstrshort[n]['Email Address'])

print('-----')
print('Matching by Payment ID number given to me')
abstr_with_pymentid = abstrshort[abstrshort['Tran#'] != '']
abstrshort2 = abstrshort[abstrshort['Tran#'] == '']
if not (len(abstrshort2) + len(abstr_with_pymentid)) == len(abstrshort):
    raise ValueError('Tran# column is suspect')

tabtest1 = join(tab3, abstr_with_pymentid, join_type='outer', keys='Tran#')
tabtest2 = join(tab3, abstr_with_pymentid, join_type='left', keys='Tran#')
if len(tabtest1) != len(tabtest2):
    raise ValueError('Not all payment IDs exisit')

print(set(tabtest1['Tran#']) - set(tabtest2['Tran#']))

for mid in abstrshort['mergeid']:
    if not mid in tab3['mergeid']:
        if abstrshort['Tran#'][mid] != '':
            ind = tab3['Tran#'] == abstrshort['Tran#'][mid]
            for c in ['First author', 'Title', 'mergeid', 'type']:
                tab3[c][ind] = abstrshort[c][mid]

print('-----')
print('Matching by full name')
# Now for those that are not matched yet use Full Name
for mid in abstrshort['mergeid']:
    if not mid in tab3['mergeid']:
        dname = difflib.get_close_matches(abstrshort['First author'][mid], tab3['name'], cutoff=0.8)
        if len(dname) == 0:
            pass
            # print('No match found for {}'.format(abstrshort['First author'][mid]))
        else:
            if len(dname) > 1:
                print("Name {} appears more than once. Assigning to first occurence.".format(dname))
            dname = [dname[0]]
            ind = tab3['name'] == dname[0]
            print('Matching {} to {} using key {}'.format(abstrshort['First author'][mid], tab3['name'][ind].data, dname[0]))
            for c in ['First author', 'Title', 'mergeid', 'type']:
                tab3[c][ind] = abstrshort[c][mid]


# Then try last name
print('----')
print('Matching by last name and first name as far as known')
for mid in abstrshort['mergeid']:
    if not mid in tab3['mergeid']:
        dname = difflib.get_close_matches(abstrshort['LastName'][mid], tab3['Last Name'], cutoff=0.95)
        if len(dname) > 0:
            # initialize all False array
            ind = np.zeros(len(tab3), dtype=bool)
            for n in dname:
                ind = ind | (tab3['Last Name'] == n)
            # Now check that the first name matches as far as we know it (until the first "." or " ")
            abstrfirst = re.match('[\w]+', abstrshort['First author'][mid])
            for n in ind.nonzero()[0]:
                tabfirst = re.match('[\w]+', tab3['First Name'][n])
                minlen = min(abstrfirst.span()[1], tabfirst.span()[1])
                if abstrfirst.group()[:minlen] != tabfirst.group()[:minlen]:
                    ind[n] = False
            if ind.sum() == 1:
                print('Matching {} to {} using key {} {}'.format(abstrshort['First author'][mid], tab3['name'][ind].data, abstrfirst.group()[:minlen], dname[0]))
                for c in ['First author', 'Title', 'mergeid', 'type']:
                    tab3[c][ind] = abstrshort[c][mid]
            elif ind.sum() > 1:
                print('Multiple possible matches for {}: {} - match by hand'.format(abstrshort['First author'][mid], tab3['name'][ind].data))

#print('The following abstr people are not yet registered')
abstrnoregistered = abstrshort[np.isin(abstrshort['mergeid'], tab3['mergeid'][~tab3['mergeid'].mask], invert=True)]
#print(abstrnoregistered)
#print('The following registered people did not submit an abstract:')
regnoabstr = tab3[tab3['mergeid'].mask]
#print(tab3[tab3['mergeid'].mask]['name', 'Email Address'])
#tab3.remove_column('mergeid')

abstrnoregistered.sort('LastName')
regnoabstr.sort('Last Name')

#abstrnoregistered['First author', 'LastName', 'Tran#'].show_in_browser(jsviewer=True)
#regnoabstr['First Name', 'Last Name', 'Tran#'].show_in_browser(jsviewer=True)

print('Number of posters from registered participants: {}'.format((tab3['type'] == 'poster').sum()))

abstrregistered = abstrshort[np.isin(abstrshort['mergeid'], tab3['mergeid'][~tab3['mergeid'].mask])]

# Write out a table that allows me to find which authors are registered
abstrregistered[['Email Address']].write('../data/abstr0725_reg.csv', format='ascii.csv')

### Read in hand edited table of participants
useabs = Table.read('../data/abstr0718_reg.csv', format='ascii.csv')
useabs['registered'] = True
abstrregistered = join(abstrshort, useabs)
abstrregistered = abstrregistered[abstrregistered['type'] == 'poster']

# Sort by last name but keep Alexander Brown and Fred Walter together
fredmergeid = abstrregistered['mergeid'][abstrregistered['LastName'] == 'Walter']
abstrregistered['LastName'][abstrregistered['mergeid'] == fredmergeid] = "Brown"
abstrregistered.sort('LastName')
abstrregistered['LastName'][abstrregistered['mergeid'] == fredmergeid] = "Walter"
abstrregistered['poster number'] = np.arange(1, len(abstrregistered) + 1)
abmerge = abstrregistered['Email Address', 'poster number']

# Make a column that is long enough
abstr.remove_column('poster number')
abstr['poster number'] = 'a really long string'
abstr['poster number'] = ''

for row in abmerge:
    ind = abstr['Email Address'] == row['Email Address']
    ind = ind.nonzero()[0]
    abstr['poster number'][ind] = row['poster number']

abstr['Email Address', 'poster number'].write('../data/asignposternumber.csv', format='ascii.csv')
# Then load this new table into google docs and manually copy and paste the poster number column.
# Export Google docs again and use that to build booklet and website.


#### Build participants list as needed for website or badges.
# A) Fill institutions
tab3['First author', 'LastName', 'First Name', 'Last Name', 'Institution']
jfull = Table.read('../data/Coolstars20070318_shifted.csv', format='ascii')
for i in range(len(tab3)):
    if tab3['Institution'].mask[i]:
        ind = jfull['Trans#'] == tab3['Tran#'][i]
        tab3['Institution'][i] = jfull['Affil'][ind.nonzero()[0][0]]

# Step X - read in full Jenine table
# Shift last few rows manually that were added
jfull = Table.read('../data/Coolstars20070318_shifted.csv', format='ascii')
# Check for double rows
# Cross match rows with each other
mid, uniqueind, n = np.unique(jfull['Trans#'], return_index=True, return_counts=True)
print('Transaction IDs turning up more than once:')
for i in (n>1).nonzero()[0]:
    print (jfull['Trans#'][i])

jfull1 = jfull[uniqueind]

for i in (n > 1).nonzero()[0]:
    # Fill,because we can't compare masked rows
    tabdub = (jfull[jfull['Trans#']== jfull1['Trans#'][i]]).filled()
    for row in tabdub.filled():
        if not row == tabdub[0]:
            print(row)
# I don't see anything, so those are really just dublicate entries

# Check numbers compared to the other spreadsheet I have
reg = ~jfull1['Reg'].mask
jfull2 = jfull1[reg]

mid, unique_ind,  n = np.unique(jfull2['Email'], return_index=True, return_counts=True)
for m in mid:
    # find all associated transaction ids:
    ids = jfull2['Trans#'][jfull2['Email'] == m]
    if not (np.isin(ids, tab2['Tran#'])).sum() == 1:
        print(jfull2['FirstName', 'LastName', 'Trans#'][jfull2['Email'] == m])
        print(m, np.isin(ids, tab2['Tran#']))


mids = mid[(n > 1)]

jfull3 = jfull2[unique_ind]

tab3['affil1'] = ['' if a is np.ma.masked else a.split(';')[0] for a in tab3['affiliations']]

for i, row in enumerate(tab3):
    if row['Institution'] is np.ma.masked:
        ind = jfull3['Trans#'] == int(row['Tran#'])
        if np.any(ind):
            tab3['Institution'][i] = jfull3['Affil'][ind][0]


tab3['First author', 'LastName', 'First Name', 'Last Name', 'Institution', 'affil1', 'waiver']

ldays = []
for i, row in enumerate(tab3):
    lrow = []
    for a, b in zip([ 'One Day Conference: Jul. 30th, 2018',
                  'One Day Conference: Jul. 31st, 2018',
                  'One Day Conference: Aug 1st, 2018',
                  'One Day Conference: Aug 2nd, 2018',
                  'One Day Conference: Aug 3rd, 2018'],
                 ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']):
        if row[a] is not np.ma.masked:
            lrow.append(b)
    ldays.append(lrow)

tab3['days'] = [' / '.join(a) for a in ldays]


tab3['First author', 'LastName', 'First Name', 'Last Name', 'Institution', 'affil1', 'Tran#', 'Email Address'].write('reglist.csv', format='../data/ascii.csv')


full = Table.read('../data/Coolstarsfull_shifted.csv', format='ascii.csv')
full.rename_column('col43', 'Tran#')
with open('../data/Coolstarsfull_shifted.csv') as f:
    fulllines = [line for line in f.readlines()]

full['text'] = fulllines

for col in ['One Day Conference: Jul. 30th, 2018',
 'One Day Conference: Jul. 31st, 2018',
 'One Day Conference: Aug 1st, 2018',
 'One Day Conference: Aug 2nd, 2018',
 'One Day Conference: Aug 3rd, 2018']:
    for row in jenine:
        if not row[col] is np.ma.masked and row['Tran#'] is not np.ma.masked:
            indrow = row['Tran#'] == full['Tran#']
            if indrow.sum() == 0:
                print('full list has no tran:',  row['Tran#'])
            else:
                rowfull = full[row['Tran#'] == full['Tran#']]
                if not col in rowfull['text'][0]:
                    print(col, row['First Name'], row['Last Name'], row['Tran#'])

full.rename_column('col15', 'Printed Booklet_full')

from astropy.table import join

tabbook = join(jenine, full, keys='Tran#')

for row in jenine:
    indrow = row['Tran#'] == full['Tran#']
    if indrow.sum() == 0:
        print('full list has no tran:',  row['Tran#'])
    else:
        if row['Printed Booklet'] != full['Printed Booklet']


bu = Table.read('../data/BUdorms.csv', format='ascii.csv')
bu = bu[:-2]
bu['first name'] = [n.lower() for n in bu['First Name']]
bu['last name'] = [n.lower() for n in bu['Last Name']]
bu.rename_column('Booking Ref #', 'BU dorm #')
bu = bu['first name', 'last name', 'BU dorm #']
jenine['first name'] = [n.lower() for n in jenine['First Name']]
jenine['last name'] = [n.lower() for n in jenine['Last Name']]
jenine['order'] = np.arange(len(jenine))

mtab = join(jenine, bu, join_type='left')

ind = ~np.isin(bu['BU dorm #'], mtab['BU dorm #'])

jenine['BUdorm'] = 0


jenine = Table.read('../data/jenine0727.csv', format='ascii')
# Remove rows at the end that don't have names in them
jenine = jenine[~jenine['Last Name'].mask]
# remove last row where headers are repeated
#jenine = jenine[:-1]
indcancel = np.isin(jenine['Tran#'], [8448, 8466, 8754])
tab3 = tab3[~indcancel]

for col in ['Printed Booklet', 'Meal Choice', 'DIETARY Restriction', 'PrintComment']:
    tab3[col].fill('')

for row in tab3:
    dorm = 'y' if row['BU dorm'] != '' else ''
    extrarec = 'y' if row['Extra Reception Ticket'] != '' else ''
    if (row['waiver'] == 'aid') or (row['Registration Type'] is np.ma.masked):
        ban = 'NOT PAID'
    elif 'reception and ban' in row['Registration Type']:
        if row['Meal Choice'] is np.ma.masked:
            ban = 'Select meat / fish / veg'
        else:
            ban = row['Meal Choice']
    else:
        ban = 'Banquet not included'
    if row['Extra Banquet Ticket'] is not np.ma.masked:
        extraban = 'Select meat / fish / veg'
    else:
        extraban = ''
    excur = ''
    for col in [ 'Brewery Tour',
 'Extra Brewery Tickets',
 'Freedom Trail Walking Tour',
 'Kayak Tour Early Afternoon',
 'Kayak Tour Late Afternoon',
 'Extra Kayak Late Afternoon',
 'Fenway Park',
 'Duck Tour',
 'Extra Duck Tour Tickets']:
        if (row[col] is not np.ma.masked) and (row[col][0] is not np.ma.masked):
            excur += row[col][0]

    c.execute('UPDATE badges SET booklet=?, banquet=?, extrabanquet=?, diet=?, comment=?, budorm=?, extrarec=? WHERE regid=?',
              ('' if row['Printed Booklet'] is np.ma.masked else row['Printed Booklet'],
               ban,
               extraban,
               '' if row['DIETARY Restriction'] is np.ma.masked else row['DIETARY Restriction'],
               '' if row['PrintComment'] is np.ma.masked else row['PrintComment'] , dorm,extrarec, int(row['Tran#_1'])))



regi    if title == 'LOC':
        color = 'ForestGreen'
    elif title == 'SOC':
        color = 'blue'
    elif title == "Press":
        color = 'red'
    elif title == "Industry Panel":
        color = 'BurntOrange'
    else:
        color = 'black'

def make_one_badge(regid):
    c.execute('SELECT pronoun, name, affil, image1, image2, email, title, booklet, extrarec, banquet, extrabanquet, excursion, diet, comment, budorm FROM badges WHERE regid=?', [str(regid)])
    fetch = c.fetchone()
    data = {}
    for i, j in zip(['pronoun', 'name', 'inst', 'image1', 'image2', 'email', 'typetext', 'booklet', 'extrarec', 'banquet', 'extrabanquet', 'excursion', 'diet', 'comment', 'budorm'], fetch):
        data[i] = j
    print('Preparing badge for: {}'.format(data['name']))
    title = data['typetext']
    if title == 'LOC':
        color = 'ForestGreen'
    elif title == 'SOC':
        color = 'blue'
    elif title == "Press":
        color = 'red'
    elif title == "Industry Panel":
        color = 'BurntOrange'
    else:
        color = 'black'
    data['typecolor'] = color
    data['regid'] = regid

    badge_deamon.compile_pdf(regid, data)
