#!/usr/bin/env python2.6

import datetime
import glob
import os
import sys
import re
from optparse import OptionParser
import tempfile
import shutil
import time
import stat

import dateutil
from sqlalchemy import func

import rbsp #rbsp.mission_day_to_UTC

from dbprocessing import Utils, inspector
from rbsp import Version

from dbprocessing import DBUtils

def EventTimer(Event, Time1):
    """
    Times an event then prints out the time and the name of the event,
    nice for debugging and seeing that the code is progressing
    """
    Time2 = time.time()
    print "%4.2f" % (Time2 - Time1), Event
    return Time2

class product(object):
    """
    class to hold product info
    """
    def __init__(self, dbu, prod):
        """
        prod is a dbutils instance
        """
        self.product_name = prod.product_name
        self.product_id = prod.product_id
        self.level = prod.level
        self.satellite = dbu.getTraceback('Product', prod.product_id)['satellite'].satellite_name

class file_(object):
    """
    class to hold file info
    """
    def __init__(self, dbu, f):
        """
        f is a dbutils file instance
        """
        self.filename = f.filename
        self.version = dbu.getVersion(f)
        self.utc_file_date = f.utc_file_date


def getInfo(mission):
    """
    connect to the db and get the information that we need into a dict
    """
    Time2 = time.time()

    info = {}

    dbu = DBUtils.DBUtils(mission)
    # get all the products then break them by spacecraft
    prods = dbu.getAllProducts()

    products = [product(dbu, v) for v in prods]

    # loop over all the products and put them into a dict
    for ii, p in enumerate(products):
        if p.satellite not in info:
            info[p.satellite] = {}
        info[p.satellite][p.product_name] = [p,]

    Time2 = EventTimer ('     Products collected', Time2) 

    # loop over each product and add the files to the tuple
    for sc in info:
        for p in info[sc]: # p is the product name
            info[sc][p].append([file_(dbu, f) for f in dbu.getFilesByProduct(info[sc][p][0].product_id, newest_version=True)])
        Time2 = EventTimer ('     {0} files collected'.format(sc), Time2) 

    return info, dbu


def makeHTML(dbu, info, satellite, delta_days=3):
    """
    given the info dict mak the html that we want to write out
    """
    header = """
    <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
    <html><head>
      <meta content="text/html; charset=ISO-8859-1" http-equiv="content-type"><title>MagEphem Pre Coverage</title>
        <style type="text/css">
            table, td, th
            {
            border:1px solid green;
            padding:3px 7px 2px 7px;
            }
            th
            {
            background-color:green;
            color:white;
            }
            tr.alt td
            {
            color:#000000;
            background-color:#EAF2D3;
            }
        </style>

    </head>


    <body>

    """
    footer = \
    """
    <br>
    <br>
    </body></html>
    """
    output = tempfile.NamedTemporaryFile(delete=False, suffix='_htmlCoverage')
    output.writelines(header)

    output.write('<h1>{0}</h1>\n'.format(dbu.mission))
    output.write('<h2>{0}</h2>\n'.format(datetime.datetime.utcnow().isoformat()))
    output.write('<h2>{0}</h2>\n'.format(satellite))

    output.write('<h2>{0}</h2>\n'.format('Files Present'))

    products = sorted(info[satellite].keys(), key=lambda x: (info[satellite][x][0].level, info[satellite][x][0].product_name))

    def makeHeader():
        # make the table structure now for the products
        output.write('<tr>')
        output.write('<td></td>') #date
        output.write('<td></td>') # mission day

        for prod in products:
            output.write('<th>{0}</th>'.format(prod))
        output.write('<td></td>')
        output.write('</tr>\n')
        output.write('<tr>')
        output.write('<td></td>') #date
        output.write('<td></td>') # mission day
        for prod in products:
            output.write('<th>{0}</th>'.format(info[satellite][prod][0].product_id))
        output.write('<td></td>')
        output.write('</tr>\n')

    # now add in all the data
    startdate = dbu.session.query(func.min(dbu.File.utc_file_date)).first()[0]
    enddate = dbu.session.query(func.max(dbu.File.utc_file_date)).first()[0] + datetime.timedelta(days=delta_days)
    d_d = enddate - startdate

    dates = [startdate + datetime.timedelta(days=v) for v in range(d_d.days)]

    output.write('<table>\n')

    # and write all the data
    for ii, d in enumerate(list(dates)[::-1]):
        if d.day == 1:
             makeHeader()
        if ii % 2 == 0:
            output.write('<tr>')
        else:
            output.write('<tr class="alt">')
        output.write('<td>{0}</td>'.format(d.isoformat()))
        output.write('<td>{0}</td>'.format(
            int(rbsp.UTC_to_mission_day(satellite[-1],
                                        datetime.datetime.combine(d, datetime.time(0))))))

        for p in products:
            fdates = [v.utc_file_date for v in info[satellite][p][1]]
            try:
                ind = fdates.index(d)
                output.write('<td>[{0}]</td>'.format(info[satellite][p][1][ind].version))
            except ValueError:
                output.write('<td>{0}</td>'.format(None))

        output.write('</tr>\n')

    output.write('</table>\n')

    output.writelines(footer)

    output.close()
    return output.name



if __name__ == "__main__":
    usage = "usage: %prog [options] -m mission_db outhtmlbase\n    outhtmlbase is th base name _mission.html is appended"
    parser = OptionParser(usage=usage)
    parser.add_option("-m", "--mission", dest="mission", type="string",
                      help="mission to connect to", default='~ectsoc/RBSP_processing.sqlite')
    parser.add_option("-d", "--deltadays", dest="deltadays", type="int",
                      help="days past last file to make table", default=3)

    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    Time1 = time.time()
    info, dbu = getInfo(options.mission)
    Time1 = EventTimer ('Info collected', Time1) 

    for sat in info:
        filename = makeHTML(dbu, info, sat, delta_days=options.deltadays)
        outname = args[0] + '_{0}.html'.format(sat)
        shutil.move(filename, outname)
        os.chmod(outname, 0664)
        Time1 = EventTimer ('Created: {0}'.format(outname), Time1) 




