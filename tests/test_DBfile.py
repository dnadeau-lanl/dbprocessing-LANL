#!/usr/bin/env python2.6

import datetime
import os
import tempfile
import unittest

from dbprocessing import DBfile
from dbprocessing import Diskfile

filename = 'test_file.txt'


class dummyDBU(object):

    def __init__(self):
        self.mission = filename

    def addFileToDB(self):
        pass

    def addFile(self, filename, data_level, **kwargs):
        pass


class DBfileTests(unittest.TestCase):
    """Tests for DBfile class"""

    def setUp(self):
        super(DBfileTests, self).setUp()
        self.filename = tempfile.NamedTemporaryFile(delete=False)
        self.filename.close()
        self.filename = self.filename.name

        with open(self.filename, 'w') as fp:
            fp.write('I am some test data\n')
        self.dbu = dummyDBU()
        self.diskfile = Diskfile.Diskfile(self.filename, self.dbu)
        self.diskfile.params['utc_file_date'] = datetime.date(2012, 4, 12)
        self.diskfile.params['interface_version'] = 1
        self.diskfile.params['quality_version'] = 2
        self.diskfile.params['revision_version'] = 3

    def tearDown(self):
        super(DBfileTests, self).tearDown()
        os.remove(self.filename)

    def test_DBfile_1(self):
        DBfile.DBfile(self.diskfile, self.dbu)

    def test_DBfile_2(self):
        self.assertRaises(DBfile.DBfileError, DBfile.DBfile, None, self.dbu)

    def test_DBfile_3(self):
        f = DBfile.DBfile(self.diskfile, self.dbu)
        f.addFileToDB()



if __name__ == "__main__":
    unittest.main()
