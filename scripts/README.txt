This file describes the script sin this directory

Processing Chain
================
ProcessQueue.py - main file to run for the processing chain
 - 2 modes, ingest and process
   - ingest mode brings files form incoming into the db
   - process mode runs processing on files in the db table processqueue
Usage: ProcessQueue [-i] [-p] [-m Test]
   -i -> import
   -p -> process
   -m -> selects mission



Database interaction
====================
addProducts.py - add products to the database per a product configuration file
Usage: addProducts.py <filename>
   -> config file to read

updateProducts.py - update a product via a changes configuration file as written by writeProductsConf.py
Usage: updateProducts.py <filename>
   -> config file to update

writeProcessConf.py - write our a process configuration file based on existing DB entries
 - This works but the read does not follow this template, no real need to use this
Usage: writeProcessConf.py <process name> <filename>
   -> process name (or number) to write to config file

addProcess.py - add a process to the db via a configuration file
Usage: addProcess.py <filename>
   -> config file to read

deleteAllDBFiles.py - remove all file entries for the DB
 - this does not remove them from disk but does remove the DB entries
 - this has no confirmation, use sparingly

writeDBhtml.py - write out the database contents into html pages, a handy dump
Usage: writeDBhtml.py <mission> <filename>
   -> mission name to write to html

writeProductsConf.py - write out a config file for an existing product
 - all will write out config files for all products, this is the normal usage
Usage: writeProductsConf.py <product name> <filename>
   -> product name (or number) to write to config file

weeklyReport.py - write out an html suitable for a weekly report type use of what the chain has done
 - somewhat limited not but a good start
Usage: scripts/weeklyReport.py <input directory> <startTime> <stopTime> <filename>
   -> directory with the dbprocessing_log.log files (automatically grabs all)
   -> start date e.g. 2000-03-12
   -> stop date e.g. 2000-03-17
   -> filename to write out the report
Example:
~/dbUtils/weeklyReport.py ~/tmp 2012-08-08 2012-08-09 weeklyReport.html

qualityControlFileDates.py - write out a text file with the dates of non QC checked files for a given product
Usage: qualityControlFileDates.py [-f, --file= filename] [--html] product_name
        -f output filename (default <product_name>.txt/<product_name>.html)
        --html output in an html format
        product name (or ID)
Example:
~/dbUtils/qualityControlFileDates.py --html rbspb_pre_ect-rept-sci-L2

qualityControlEmail.py - send out a quality control email to the person in the config file
Usage: qualityControlEmail.py [-d, --dryrun] product_name
        -d dryrun mode just print the email to screen don't send
        -f config filename (default ~/dbUtils/QCEmailer_conf.txt)
        product name (or ID)
Example:
~/dbUtils/qualityControlEmail.py -d rbspa_rept-sw-L0

reprocessByCode.py - add files back to he process queue for a given code
Usage: reprocessByCode.py [options]
Options:
  -h, --help            show this help message and exit
  -s STARTDATE, --startDate=STARTDATE
                        Date to start reprocessing (e.g. 2012-10-02)
  -e ENDDATE, --endDate=ENDDATE
                        Date to end reprocessing (e.g. 2012-10-25)
Example:
~/dbUtils/reprocessByCode.py 993
~/dbUtils/reprocessByCode.py l05_to_l1.py

reprocessByProduct.py - add files back to the process queue for a given product
Usage: reprocessByProduct.py [options]
Options:
  -h, --help            show this help message and exit
  -s STARTDATE, --startDate=STARTDATE
                        Date to start reprocessing (e.g. 2012-10-02)
  -e ENDDATE, --endDate=ENDDATE
                        Date to end reprocessing (e.g. 2012-10-25)
Example:
~/dbUtils/reprocessByProduct.py 4361
~/dbUtils/reprocessByProduct.py rbspb_rept-cmdecho-L0



Other info
==========
Totally clean out the DB:  (leaves mission, instrument, satellite)
run these commands (done this way so it is hard to do)
from dbprocessing import DBUtils
a = DBUtils.DBUtils('rbsp')
a.deleteAllEntries()











Versions:
8Aug2012 BAL
 - initial revision


