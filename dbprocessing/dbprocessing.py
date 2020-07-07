from __future__ import print_function

import datetime
import imp
import os
import shutil
import sys
import tempfile
import time
import traceback
from operator import itemgetter

import DBfile
import DBlogging
import DBqueue
import DButils
import Utils
import runMe
from Utils import strargs_to_args

try:  # new version changed this annoyingly
    from sqlalchemy.exceptions import IntegrityError
except ImportError:
    from sqlalchemy.exc import IntegrityError


class ProcessQueue(object):
    """
    Main code used to process the Queue, looks in incoming and builds all
    possible files

    @author: Brian Larsen
    @organization: Los Alamos National Lab
    @contact: balarsen@lanl.gov

    @version: V1: 02-Dec-2010 (BAL)
    """

    def __init__(self,
                 mission, instrument, dryrun=False, echo=False):

        self.dryrun = dryrun
        self.mission = mission
        self.instrument = instrument
        dbname = os.environ['PGDATABASE']
        self.tempdir = None
        dbu = DButils.DButils(dbname, instrument, echo=echo)  #
        self.runme_list = []
        self.dbu = dbu
        self.childrenQueue = DBqueue.DBqueue()
        self.moved = DBqueue.DBqueue()
        self.depends = DBqueue.DBqueue()
        self.queue = DBqueue.DBqueue()
        self.findChildren = DBqueue.DBqueue()
        DBlogging.dblogger.debug("Entering ProcessQueue")

    def __del__(self):
        """
        attempt a bit of up
        """
        self.rm_tempdir()
        try:
            del self.dbu
        except AttributeError:
            pass

    def set_filename(self, filename):
        """
        Setter for filename, this is cleaner than just random sets

        :param filename: filename to set to self.filename
        :type filename: str
        :return: None
        """
        self.filename = filename
        self.basename = os.path.basename(self.filename)

    def rm_tempdir(self):
        """
        remove the temp directory
        """
        try:
            if self.tempdir != None:
                name = self.tempdir
                shutil.rmtree(self.tempdir)
                self.tempdir = None
                DBlogging.dblogger.debug("Temp dir deleted: {0}".format(name))
        except AttributeError:
            pass

    def mk_tempdir(self, suffix='_dbprocessing_{0}'.format(os.getpid())):
        """
        create a secure temp directory
        """
        self.tempdir = tempfile.mkdtemp(suffix)

    def checkIncoming(self, glb='*'):
        """
        Goes out to incoming and grabs all files there adding them to self.queue

        @author: Brian Larsen
        @organization: Los Alamos National Lab
        @contact: balarsen@lanl.gov

        @version: V1: 02-Dec-2010 (BAL)
        """
        DBlogging.dblogger.debug("Entered checkIncoming:")

        self.queue.extendleft(self.dbu.checkIncoming(glb=glb))
        # step through and remove duplicates
        # if python 2.7 deque has a .count() otherwise have to use
        #  this workaround
        for i in range(len(self.queue)):
            try:
                if list(self.queue).count(self.queue[i]) != 1:
                    self.queue.remove(self.queue[i])
            except IndexError:
                pass  # this means it was shortened
        #DBlogging.dblogger.debug("Queue contains (%d): %s" % (len(self.queue),
        #                                                      self.queue))

    def moveToError(self, fname):
        """
        Moves a file from incoming to error
        """
        DBlogging.dblogger.debug("Entered moveToError: {0}".format(fname))

        path = self.dbu.getErrorPath()
        # if the file is a link then don;t move it to incoming just delete the link
        if os.path.islink(fname):
            os.unlink(fname)  # Remove a file (same as remove(path)).
            DBlogging.dblogger.info("moveToError file {0} was a link, so link removed not moved to error".format(fname))
        else:
            try:
                shutil.move(fname, os.path.join(path, os.path.basename(fname)))
            except IOError:
                DBlogging.dblogger.error(
                    "file {0} was not successfully moved to error".format(os.path.join(path, os.path.basename(fname))))
            else:
                DBlogging.dblogger.info("moveToError {0} moved to {1}".format(fname, path))

    def diskfileToDB(self, df):
        """
        given a diskfile go through and do all the steps to add it into the db
        """
        if df is None:
            DBlogging.dblogger.info("Found no product moving to error, {0}".format(self.basename))
            if not self.dryrun:
                self.moveToError(self.filename)
            else:
                print('<dryrun> Found no product moving to error, {0}'.format(self.basename))
            return None

        # create the DBfile
        dbf = DBfile.DBfile(df, self.dbu)
        try:
            if not self.dryrun:
                f_id = dbf.addFileToDB()
                DBlogging.dblogger.info("File {0} entered in DB, f_id={1}".format(df.filename, f_id))
            else:
                print('<dryrun> File {0} entered in DB'.format(df.filename))
        except (ValueError, DButils.DBError) as errmsg:
            if not self.dryrun:
                DBlogging.dblogger.warning("Except adding file to db so" + \
                                           " moving to error: %s" % (errmsg))
                self.moveToError(os.path.join(df.path, df.filename))
            else:
                print('<dryrun> Except adding file to db so' +
                      ' moving to error: %s' % (errmsg))
            return None

        # move the file to the its correct home
        if not self.dryrun:
            dbf.move()

        if not self.dryrun:
            try:
                self.dbu.session.commit()
            except IntegrityError as IE:
                self.session.rollback()
                raise (DButils.DBError(IE))
            # add to processqueue for later processing
            self.dbu.Processqueue.push(f_id)
            return f_id
        else:
            return None

    def importFromIncoming(self):
        """
        Import a file from incoming into the database
        """
        DBlogging.dblogger.debug("Entering importFromIncoming, {0} to import".format(len(self.queue)))

        if not self.dryrun:
            vals = self.queue.popleftiter()
        else:
            vals = self.queue

        T0 = time.time()
        for ii, val in enumerate(vals, 1):
            self.set_filename(val)
            DBlogging.dblogger.debug("popped '{0}' from the queue: {1} left".format(self.basename, len(self.queue)))
            # see if the file is in the db, if so then don't call the inspectors
            try:
                id = self.dbu.getFileID(self.basename)
                if self.dbu.checkIncomingFileSHA(id): #Added 2019-02-11 XYang, do update if file is in db with different checksum
                    DBlogging.dblogger.info(
                        'File {0}:{1} was already in DB, not inspecting'.format(id, self.basename))
                    self.moveToError(self.filename)
                    T1 = time.time() - T0
                    print('{1}:{2} Removed from incoming: {0} - already present  {3:.2f}s'.format(self.basename, ii, len(self.queue), T1))
                    T0 = time.time()
                    continue
                else:
                    df = self.figureProduct()
                    dbf = DBfile.DBfile(df, self.dbu)
                    dbf.move()
                    self.dbu.updateFileSHA(id)
                    self.dbu.Processqueue.push(id)
                    T1 = time.time() - T0
                    print('{1}:{2} Removed from incoming: {0} - ingested  {3:.2f}s'.format(self.basename, ii, len(self.queue), T1))
                    T0 = time.time()
            except DButils.DBNoData:
                DBlogging.dblogger.info('File {0} was not in DB, inspecting'.format(self.basename))
            df = self.figureProduct()
            if df is not None:
                self.diskfileToDB(df)
                T1 = time.time() - T0
                print('{1}:{2} Removed from incoming: {0} - ingested   {3:.2f}s'.format(self.basename, ii, len(self.queue), T1))
                T0 = time.time()

    def figureProduct(self, filename=None):
        """
        This function imports the inspectors and figures out which inspectors claim the file
        """
        if filename is None:
            filename = self.filename
        act_insp = self.dbu.getActiveInspectors()
        claimed = []
        for code, arg, product in act_insp:
            try:
                inspect = imp.load_source('inspect', code)
            except IOError as msg:
                DBlogging.dblogger.error('Inspector: "{0}" not found: {1}'.format(code, msg))
                if os.path.isfile(code + ' '):
                    DBlogging.dblogger.info('---> However inspector: "{0}" was found'.format(code + ' '))
                    print('---> However inspector: "{0}" was found.'.format(code + ' '))
                continue
            if arg is not None:
                kwargs = strargs_to_args(arg)
                try:
                    df = inspect.Inspector(filename, self.dbu, product, **kwargs)
                except:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    DBlogging.dblogger.error(
                        "File {0} inspector threw an exception: {1} {2} {3}".format(filename, str(exc_type), exc_value,
                                                                                    traceback.print_tb(
                                                                                        exc_traceback)))  # exc_traceback.tb_lineno))
                    continue  # try the next inspector
            else:
                try:
                    df = inspect.Inspector(filename, self.dbu, product, )
                except:
                    DBlogging.dblogger.error("File {0} inspector threw an exception".format(filename))
                    continue  # try the next inspector
            if df is not None:
                claimed.append(df)
                DBlogging.dblogger.debug("Match found: {0}: {1}".format(filename, code, ))
                break  # lets call it done after we find one

        if len(claimed) == 0:  # no match
            DBlogging.dblogger.info("File {0} found no inspector match".format(filename))
            return None
        if len(claimed) > 1:
            DBlogging.dblogger.error("File {0} matched more than one product, there is a DB error".format(filename))
            raise (DButils.DBError("File {0} matched more than one product, there is a DB error".format(filename)))

        return claimed[0]  # return the diskfile

    def _getRequiredProducts(self, process_id, file_id, utc_file_date, debug=False):
        #####################################################
        ## get all the input products for that process, and if they are optional
        T0 = time.time()
        input_product_id = self.dbu.getInputProductID(process_id)  # this is a list of tuples (id, optional)
        if debug: print("21:    {0}: self.dbu.getInputProductID: {1}".format(time.time() - T0, input_product_id))
        T0 = time.time()

        DBlogging.dblogger.debug(
            "Finding input files for file_id:{0} process_id:{1} date:{2}".format(file_id, process_id, utc_file_date))

        ## here decide how we build output and do it.

        timebase = self.dbu.getProcessTimebase(process_id)
        if debug: print("22:    {0}: self.dbu.getProcessTimebase: {1}".format(time.time() - T0, timebase))
        T0 = time.time()


        DBlogging.dblogger.debug("Doing {0} based processing".format(timebase))
        if timebase in ['FILE', 'DAILY', 'RUN']:  # taking one file to the next file
            # for file based processing we are going to look to the "process_keywords" and cull the
            #   returned files based on making sure they are all the same
            #   If process_keywords is none it will fall back to current behavior (since they will all be the same)
            files = []
            # get all the possible files based on dates that we might want to put into the process now

            for iprod_id, opt in input_product_id:
                # accept a datetime.datetime or datetime.date
                dt = Utils.datetimeToDate(utc_file_date)

                tmp_files = self.dbu.getFilesByProductDate(iprod_id, [dt] * 2, newest_version=False)
                #if debug: print("23:    {0}: self.dbu.getFilesByProductDate,format {1} {2} {3}.format(time.time() - T0, iprod_id, dt, tmp_files))
                T0 = time.time()
                if not tmp_files and not opt:
                    return None, input_product_id
                else:
                    files.extend(tmp_files)

            #DBlogging.dblogger.debug("buildChildren files: ".format(str(files)))

            ###############
            # BAL 30 March 2017, dropping this clean step as they should all be newest version per above
            # remove all the files that are not the newest version, they all should be
            # files = self.dbu.file_id_Clean(files)
            ###############

            if timebase == 'FILE':  # taking one file to the next file
                files_out = []
                # grab the process_keywords column for the file_id and all the possible other files
                #   they have to match in order for the file to be the same
                infile_process_keywords = self.dbu.getEntry('File', file_id).process_keywords
                try:
                    files_process_keywords = [v.process_keywords for v in files]
                except AttributeError:
                    files_process_keywords = []
                # now if the process_keywords in files_process_keywords does not match that in infile_process_keywords
                #   drop it
                for ii, v in enumerate(files_process_keywords):
                    if v == infile_process_keywords:
                        files_out.append(files[ii])
                # and give it the right name
                files = files_out
        else:
            raise (NotImplementedError('Not implemented yet: {0} based processing'.format(timebase)))
            raise (ValueError('Bad timebase for product: {0}'.format(process_id)))
        return files, input_product_id

    def buildChildren(self, file_id, debug=False):
        """
        go through and all the runMe's and add to the runme_list variable
        """
        T0 = time.time()
        DBlogging.dblogger.debug("Entered buildChildren: file_id={0}".format(file_id))
        if debug: print("Entered buildChildren: file_id={0}".format(file_id))
        # if this file is not a newest_version we do not ant to run
        #print("{1}: Entered buildChildren: file_id={0}".format(file_id, time.time()-T0))
        T0 = time.time()
        #if not self.dbu.fileIsNewest(file_id[0]):
        #    DBlogging.dblogger.debug("Was not newest version in buildChildren: file_id={0}".format(file_id))
        #    print("    Was not newest version in buildChildren: file_id={0}".format(file_id))
        #    return  # do nothing
        #    if debug: print("    {1}: was newest moving on in buildChildren: file_id={0}".format(file_id, time.time()-T0))
        T0 = time.time()

        children = self.dbu.getChildrenProcesses(file_id[0])  # returns process
        if debug: print("11:   {1}: done self.dbu.getChildrenProcesses buildChildren: file_id={0} : {2}".format(file_id, time.time()-T0, children))
        T0 = time.time()
        daterange = self.dbu.getFileDates(file_id[0])  # this is the dates that this file spans
        if debug: print("12:   {1}: done self.dbu.getFileDates  buildChildren: file_id={0} : {2}".format(file_id, time.time()-T0, daterange))
        T0 = time.time()

        if debug: print("children: {0}".format(children))
        for child_process in children:

            # iterate over all the days between the start and stop date from above (including stop date)
            for utc_file_date in Utils.expandDates(*daterange):
                if debug: print("    utc_file_date: {0}".format(utc_file_date))
                files, input_product_id = self._getRequiredProducts(child_process, file_id[0], utc_file_date)
                #if debug: print("13:   {0}: self._getRequiredProducts   {1} {2} {3}".format(time.time()-T0, files, input_product_id, timebase)
                T0 = time.time()
                if not files:
                    # figure out the missing products
                    DBlogging.dblogger.debug("For file: {0} date: {1} required files not present {2}"
                                             .format(file_id[0], utc_file_date, input_product_id))
                    continue  # go on to the next file

                    # ==============================================================================
                    # do we have the required files to do the build?
                    # ==============================================================================
                    ##             if not self._requiredFilesPresent(files, input_product_id, process_id):
                    ##                 DBlogging.dblogger.debug("For file: {0} date: {1} required files not present".format(file_id[0], utc_file_date))
                    ##                 continue # go on to the next file

                try:
                    input_files = [v.file_id for v in files]
                    if len(input_files) > 1:
                       #print("        Input files to be removed....")
                       self.dbu.Processqueue.remove(input_files)
                       #Dblogging .....
                except AttributeError:
                    continue
                #DBlogging.dblogger.debug("Input files found, {0}".format(input_files))
                if self.dbu.dbprocessCurrentlyrunning(child_process):  #exit if the same process ....
                    DBlogging.dblogger.debug("The same process is running, can't run")
                    continue
                if self.dbu.relateddbprocessrunning(child_process):  #exit if the same process ....
                    DBlogging.dblogger.debug("The related process is running, can't run")
                    continue
                timebase = self.dbu.getProcessTimebase(child_process)
                if child_process in [p.process_id for p in self.runme_list] and timebase == 'DAILY': # Added check on process_id to ....
                    DBlogging.dblogger.debug("The same process is in the runme list, can't run")
                    continue
                runme = runMe.runMe(self.dbu, utc_file_date, child_process, input_files, self)
                #print("{0}:  runMe.runMe".format(time.time()-T0))
                #T0 = time.time()
                # only add to runme list if it can be run
                if runme.ableToRun and (runme not in self.runme_list):
                    self.runme_list.append(runme)
                    DBlogging.dblogger.info("Filename: {0} is not in the DB, can process".format(runme.filename))

    def onStartup(self):
        """
        Processes can be defined as output timebase "STARTUP" which means to run
        them each time to processing chain is run
        """
        proc = self.dbu.getAllProcesses(timebase='STARTUP')
        # TODO just going to run there here for now.  This should move to runMe
        for p in proc:  # run them all
            code = self.dbu.getEntry('Code', p.process_id)
            # print code.codename

        # need to call a "runner" with these processes
        ######
        ##
        # not sure how to deal with having to specify a filename and handle that in the DB
        # things made here will also have to have inspectors
        raise (NotImplementedError('Not yet implemented'))

    def _reprocessBy(self,
                     startDate="1970-01-01",
                     endDate="2070-01-01",
                     level=None,
                     product=None,
                     code=None,
                     instrument=None,
                     incVersion=None):
        """
        Given parameters, add all files to processqueue so that next
        -p run they will be reprocessed

        incVersion sets which of the version numbers to increment {0}.{1}.{2}
        """
        startDate = Utils.datetimeToDate(startDate)
        endDate = Utils.datetimeToDate(endDate)
        f_ids = [val.file_id for val in self.dbu.getFiles(startDate=startDate,
                                                          endDate=endDate,
                                                          level=level,
                                                          product=product,
                                                          code=code,
                                                          instrument=instrument,
                                                          newest_version=True)]

        return self.dbu.Processqueue.rawadd(f_ids, incVersion)

    def reprocessByCode(self, id_in, startDate=None, endDate=None, incVersion=2):
        try:
            code_id = self.dbu.getCodeID(id_in)
            return self._reprocessBy(code=code_id, startDate=startDate, endDate=endDate,
                                     incVersion=incVersion)
        except DButils.DBNoData:
            DBlogging.dblogger.error('No code_id {0} found in the DB'.format(id_in))
            
    def reprocessByProduct(self, id_in, startDate=None, endDate=None, incVersion=None):
        try:
            prod_id = self.dbu.getProductID(id_in)
            return self._reprocessBy(product=prod_id, startDate=startDate, endDate=endDate,
                                     incVersion=incVersion)
        except DButils.DBNoData:
            DBlogging.dblogger.error('No product_id {0} found in the DB'.format(id_in))

    def reprocessByDate(self, startDate=None, endDate=None, incVersion=None, level=None):
        return self._reprocessBy(startDate=startDate, endDate=endDate,
                                 incVersion=incVersion, level=level)

    def reprocessByInstrument(self, id_in, level=None, startDate=None, endDate=None, incVersion=None):
        try:
            inst_id = self.dbu.getInstrumentID(id_in)
            return self._reprocessBy(instrument=inst_id, level=level, startDate=startDate, endDate=endDate,
                                     incVersion=incVersion)
        except DButils.DBNoData:
            DBlogging.dblogger.error('No inst_id {0} found in the DB'.format(id_in))

    def reprocessByAll(self, level=None, startDate=None, endDate=None):
        """
        this is a raw call into the db meant to be fast and all every file
        between the dates into the process queue
        - there is no version increment allowed
        """
        return self._reprocessBy(level=level, startDate=startDate, endDate=endDate,
                                incVersion=None)
