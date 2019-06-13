import csv


def data(**kwargs):
    with open('data/attendees.csv') as f:
        r = csv.DictReader(f)
        attendees = [row for row in r]

    return {'attendees': attendees}
