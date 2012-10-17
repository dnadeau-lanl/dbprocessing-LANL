#!/usr/bin/env python2.6


"""
go through the DB and add all the files that went into this code onto the
processqueue so that the next ProcessQueue -p will run them
"""




#==============================================================================
# INPUTS
#==============================================================================
# code_id (or code name)
## startDate - date to start the reprocess
## endDate - date to end the reprocess

from optparse import OptionParser

from dateutil import parser as dup

import dbprocessing.DBlogging as DBlogging
import dbprocessing.dbprocessing as dbprocessing


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-s", "--startDate", dest="startDate", type="string",
                      help="Date to start reprocessing", default=None)
    parser.add_option("-e", "--endDate", dest="endDate", type="string",
                      help="Date to end reprocessing", default=None)
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    if options.startDate is not None:
        startDate = dup.parse(options.startDate)
    if options.endDate is not None:
        endDate = dup.parse(options.endDate)

    db = dbprocessing.ProcessQueue('rbsp')
    num = db.reprocessByCode(args[0], startDate=startDate, endDate=endDate)
    print('Added {0} files to be reprocessed for code {1}'.format(num, args[0]))
    DBlogging.dblogger.info('Added {0} files to be reprocessed for code {1}'.format(num, args[0]))

