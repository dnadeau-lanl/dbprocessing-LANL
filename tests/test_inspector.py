#!/usr/bin/env python2.6

import os
import shutil
import stat
import tempfile
import unittest

from dbprocessing import DBUtils
from dbprocessing import Diskfile
from dbprocessing import inspector

__version__ = '2.0.3'


class InspectorClass(unittest.TestCase):
    """Tests of the inspector class"""

    def setUp(self):
        super(InspectorClass, self).setUp()
        sqpath = os.path.join(os.path.dirname(__file__), 'RBSP_MAGEIS.sqlite')
        self.sqlworking = sqpath.replace('RBSP_MAGEIS.sqlite', 'working.sqlite')
        shutil.copy(sqpath, self.sqlworking)
        os.chmod(self.sqlworking, stat.S_IRUSR | stat.S_IWUSR)
        self.dbu = DBUtils.DBUtils(self.sqlworking)
        self.filename = tempfile.NamedTemporaryFile(delete=False)
        self.filename.close()
        self.filename = self.filename.name

        class inspC(inspector.inspector):
            code_name = 'test_inspector.py'

            def inspect(self, kwargs):
                """overwrite the abstract method"""
                return Diskfile.Diskfile(self.filename, self.dbu)

        self.inspC = inspC

    def tearDown(self):
        super(InspectorClass, self).tearDown()
        self.dbu._closeDB()
        del self.dbu
        os.remove(self.sqlworking)
        os.remove(self.filename)

    def test_insp_1(self):
        """inspector test"""
        a = self.inspC(self.filename, self.dbu, 2)
        self.assertEqual(0.0, a.diskfile.params['data_level'])


if __name__ == "__main__":
    unittest.main()
