#!/usr/bin/env python2.6

import imp
import glob
import os
import os.path
import shutil
import subprocess
import tempfile

import DBfile
import DBlogging
import DBStrings
import DBqueue
import DBUtils
import runMe
import Utils
from Utils import strargs_to_args
import Version

try: # new version changed this annoyingly
    from sqlalchemy.exceptions import IntegrityError
except ImportError:
    from sqlalchemy.exc import IntegrityError

__version__ = '2.0.4'


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
                 mission):

        self.mission = mission
        dbu = DBUtils.DBUtils(self.mission)
        self.tempdir = None
#        self.current_file = None
        self.runme_list = []
        self.dbu = dbu
        self.childrenQueue = DBqueue.DBqueue()
        self.moved = DBqueue.DBqueue()
        self.depends = DBqueue.DBqueue()
        self.queue = DBqueue.DBqueue()
        self.findChildren = DBqueue.DBqueue()
        DBlogging.dblogger.info("Entering ProcessQueue")

    def __del__(self):
        """
        attempt a bit of up
        """

    def rm_tempdir(self):
        """
        remove the temp directory
        """
        if self.tempdir != None:
            name = self.tempdir
            shutil.rmtree(self.tempdir)
            self.tempdir = None
            DBlogging.dblogger.debug("Temp dir deleted: {0}".format(name))

    def mk_tempdir(self, suffix='_dbprocessing'):
        """
        create a secure temp directory
        """
        self.tempdir = tempfile.mkdtemp(suffix)

    def checkIncoming(self):
        """
        Goes out to incoming and grabs all files there adding them to self.queue

        @author: Brian Larsen
        @organization: Los Alamos National Lab
        @contact: balarsen@lanl.gov

        @version: V1: 02-Dec-2010 (BAL)
        """
        DBlogging.dblogger.debug("Entered checkIncoming:")

        self.queue.extendleft(self.dbu._checkIncoming())
        # step through and remove duplicates
        # if python 2.7 deque has a .count() otherwise have to use
        #  this workaround
        for i in range(len(self.queue )):
            try:
                if list(self.queue).count(self.queue[i]) != 1:
                    self.queue.remove(self.queue[i])
            except IndexError:
                pass   # this means it was shortened
        DBlogging.dblogger.debug("Queue contains (%d): %s" % (len(self.queue),
                                                              self.queue))

    def moveToError(self, fname):
        """
        Moves a file from incoming to error

        @author: Brian Larsen
        @organization: Los Alamos National Lab
        @contact: balarsen@lanl.gov

        @version: V1: 02-Dec-2010 (BAL)
        """
        DBlogging.dblogger.debug("Entered moveToError: {0}".format(fname))

        path = self.dbu.getErrorPath()
        if os.path.isfile(os.path.join(path, os.path.basename(fname) ) ):
        #TODO do I really want to remove old version:?
            os.remove( os.path.join(path, os.path.basename(fname) ) )
            DBlogging.dblogger.warning("removed {0}, as it was under a copy".format(os.path.join(path, os.path.basename(fname) )))
        if path[-1] != os.sep:
            path = path+os.sep
        try:
            shutil.move(fname, path)
        except IOError:
            DBlogging.dblogger.error("file {0} was not successfully moved to error".format(os.path.join(path, os.path.basename(fname) )))
        else:
            DBlogging.dblogger.info("moveToError {0} moved to {1}".format(fname, path))

    def diskfileToDB(self, df):
        """
        given a diskfile go through and do all the steps to add it into the db
        """
        if df is None:
            DBlogging.dblogger.info("Found no product moving to error, {0}".format(self.filename))
            self.moveToError(self.filename)
            return None

        # creae the DBfile
        dbf = DBfile.DBfile(df, self.dbu)
        try:
            f_id = dbf.addFileToDB()
            DBlogging.dblogger.info("File {0} entered in DB, f_id={1}".format(df.filename, f_id))
        except (ValueError, DBUtils.DBError) as errmsg:
            DBlogging.dblogger.warning("Except adding file to db so" + \
                                       " moving to error: %s" % (errmsg))
            self.moveToError(os.path.join(df.path, df.filename))
            return None

        # move the file to the its correct home
        dbf.move()
        # set files in the db of the same product and same utc_file_date to not be newest version
        files = self.dbu.getFiles_product_utc_file_date(dbf.diskfile.params['product_id'], dbf.diskfile.params['utc_file_date'])
        if files:
            mx = max(zip(*files)[1]) # max on version
        for f in files:
            if f[1] != mx: # this is not the max, newest_version should be False
                fle = self.dbu.getEntry('File', f[0])
                fle.newest_version = False
                self.dbu.session.add(fle)
                # this seems good, TODO make sure .add() isn't needed as well
                DBlogging.dblogger.debug("set file: {0}.newest_version=False".format(f[0]))
        try:
            self.dbu.session.commit()
        except IntegrityError as IE:
            self.session.rollback()
            raise(DBUtils.DBError(IE))
        # add to processqueue for later processing
        self.dbu.Processqueue.push(f_id)
        return f_id

    def importFromIncoming(self):
        """
        Import a file from incoming into the database
        """
        DBlogging.dblogger.debug("Entering importFromIncoming, {0} to import".format(len(self.queue)))

        for val in self.queue.popleftiter() :
            self.filename = val
            DBlogging.dblogger.debug("popped '{0}' from the queue: {1} left".format(self.filename, len(self.queue)))
            df = self.figureProduct()
            self.diskfileToDB(df)

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
            except IOError, msg:
                DBlogging.dblogger.error("Inspector: {0} not found: {1}".format(code, msg))
                continue
            if arg is not None:
                kwargs = strargs_to_args(arg)
                try:
                    df = inspect.Inspector(filename, self.dbu, product, **kwargs)
                except:
                    DBlogging.dblogger.error("File {0} inspector threw an exception".format(filename))
                    self.moveToError(filename)
                    return None
            else:
                try:
                    df = inspect.Inspector(filename, self.dbu, product, )
                except:
                    DBlogging.dblogger.error("File {0} inspector threw an exception".format(filename))
                    self.moveToError(filename)
                    return None
            if df is not None:
                claimed.append(df)
                DBlogging.dblogger.debug("Match found: {0}: {1}".format(filename, code, ))
                break # lets call it done after we find one

        if len(claimed) == 0: # no match
            DBlogging.dblogger.info("File {0} found no inspector match".format(filename))
            return None
        if len(claimed) > 1:
            DBlogging.dblogger.error("File {0} matched more than one product, there is a DB error".format(filename))
            raise(DBUtils.DBError("File {0} matched more than one product, there is a DB error".format(filename)))

        return claimed[0]  # return the diskfile


    def _getRequiredProducts(self, process_id, file_id, utc_file_date, daterange):
        #####################################################
        ## get all the input products for that process, and if they are optional
        input_product_id = self.dbu.getInputProductID(process_id) # this is a list

        DBlogging.dblogger.debug("Finding input files for file_id:{0} process_id:{1} date:{2}".format(file_id, process_id, utc_file_date))

        ## here decide how we build output and do it.
        timebase = self.dbu.getEntry('Process', process_id).output_timebase
        if timebase == 'FILE': # taking one file to the next file
            DBlogging.dblogger.debug("Doing {0} based processing".format(timebase))
            files = []
            for val, opt in input_product_id:
                # TODO there is a suspect danger here that multiple files have the same date with different start stop
                tmp = self.dbu.getFiles_product_utc_file_date(val, utc_file_date)
                if tmp:  # != []
                    files.extend(tmp)
            DBlogging.dblogger.debug("buildChildren files: ".format(str(files)))
            files = self.dbu.file_id_Clean(files)

        elif timebase == 'DAILY':
            DBlogging.dblogger.debug("Doing {0} based processing".format(timebase))
            ## from the input file see what the timebase is and grab all files that go into process
            DBlogging.dblogger.debug("Finding input files for {0}".format(daterange))

            files = []
            for val, opt in input_product_id:
                tmp = self.dbu.getFiles_product_utc_file_date(val, daterange)
                if tmp:  # != []
                    files.extend(tmp)
            DBlogging.dblogger.debug("buildChildren files: ".format(str(files)))
            files = self.dbu.file_id_Clean(files)

        else:
            DBlogging.dblogger.debug("Doing {0} based processing".format(timebase))
            raise(NotImplementedError('Not implemented yet: {0} based processing'.format(timebase)))
            raise(ValueError('Bad timebase for product: {0}'.format(process_id)))
        return files, input_product_id

    def _requiredFilesPresent(self, files, input_product_id, process_id):
        #==============================================================================
        # do we have the required files to do the build?
        #==============================================================================
        # get the products of the input files
        ## need to go through the input_product_id and make sure we have a file for each required product
        if not files:
            return False
        for prod, opt in input_product_id:
            if not opt:
                if not prod in zip(*files)[2]: # the product ID
                    DBlogging.dblogger.info("Required products not found, continuing.  Process:{0}, product{1}".format(process_id, prod))
                    return False
        return True

    def buildChildren(self, process_id, file_id):
        """
        go through and all all the runMe's to the runme_list variable
        """
        DBlogging.dblogger.debug("Entered buildChildren: process_id={0}".format(process_id))

        daterange = self.dbu.getFileDates(file_id[0])

        # whole function is in this loop
        for utc_file_date in daterange:

            files, input_product_id = self._getRequiredProducts(process_id, file_id[0], utc_file_date, daterange)

            #==============================================================================
            # do we have the required files to do the build?
            #==============================================================================
            if not self._requiredFilesPresent(files, input_product_id, process_id):
                return None

            input_files = zip(*files)[0] # this is the file_id
            DBlogging.dblogger.debug("Input files found, {0}".format(input_files))

            runme = runMe.runMe(self.dbu, utc_file_date, process_id, input_files, )
            self.runme_list.append(runme)


    def onRun(self):
        """
        Processes can be defined as output timebase "RUN" which means to run
        them each time to processing chain is run
        """
        proc = self.dbu.getAllProcesses(timebase='RUN')
        # need to call a "runner" with these processes
        ######
        ##
        # not sure how to deal with having to specify a filename and handle that in the DB
        # things made here will also have to have inspectors
        raise(NotImplementedError('Not yet implemented'))

    def _reprocessBy(self, id_in, code=False, prod=False, inst=False, level=None, startDate=None, endDate=None, incVersion=2):
        """
        given a code_id (or name) add all files that this code touched to processqueue
            so that next -p run they will be reprocessed
        If one adds a new code run this on the code that this is replacing
        Force moves the file back to incoming and then removes it from the db
        incVersion sets which of the version numbers to increment {0}.{1}.{2}
        ** this ends up being a little more aggressive as the input files are put
           on the processqueue so all products associated with them are remade
           ** If we want to change this then several steps need to occur:
               1) need to have a way to tell buildchildren or _runner to only use
                   certain codes
        """
        # 1) get all the files made by this code
        # 2) get all the parents of the 1) files
        # 3) add all these back to the processqueue (use set as duplicates breaks things)
        if code:
            code_id = self.dbu.getCodeID(id_in) # allows name or id
            files = self.dbu.getFilesByCode(code_id)
        elif prod:
            prod_id = self.dbu.getProductID(id_in)
            files = self.dbu.getFilesByProduct(prod_id)
        elif inst:
            inst_id = self.dbu.getInstrumentID(id_in)
            prods = self.dbu.getProductsByInstrument(inst_id)
            if level is not None: # cull the list by level
                prods2 = []
                for prod in prods:
                    ptb = self.dbu.getProductTraceback(prod)
                    if ptb['product'].level == level:
                        prods2.append(ptb['product'].product_id)
                prods = prods2
            for prod in prods: # add them all to be reprocessed
                self.reprocessByProduct(prod, startDate=startDate, endDate=endDate, incVersion=incVersion)
        else:
            raise(ValueError('No reprocess by specified'))
        # files before this date are removed from the list
        if startDate is not None:
            files = [val for val in files if val.utc_file_date >= startDate]
        # files after this date are removed from the list
        if endDate is not None:
            files = [val for val in files if val.utc_file_date <= endDate]
        f_ids = [val.file_id for val in files]
        parents = [self.dbu.getFileParents(val, id_only=True) for val in f_ids]
        filesToReprocess = set(Utils.flatten(parents))
        self.dbu.Processqueue.push(filesToReprocess, incVersion)
        return len(filesToReprocess)

    # TODO can functools.partial help here?
    def reprocessByCode(self, id_in, startDate=None, endDate=None, incVersion=2):
        return(self._reprocessBy(id_in, code=True, prod=False, startDate=startDate, endDate=endDate, incVersion=incVersion))

    def reprocessByProduct(self, id_in, startDate=None, endDate=None, incVersion=2):
        return(self._reprocessBy(id_in, code=False, prod=True, startDate=startDate, endDate=endDate, incVersion=incVersion))

    def reprocessByInstrument(self, id_in, level=None, startDate=None, endDate=None, incVersion=2):
        return(self._reprocessBy(id_in, code=False, prod=False, inst=True, startDate=startDate, endDate=endDate, incVersion=incVersion))





