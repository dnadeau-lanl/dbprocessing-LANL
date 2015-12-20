#!/usr/bin/env python2.6

import datetime
import os
import unittest

from dbprocessing import Utils
from dbprocessing import Version


class UtilsTests(unittest.TestCase):
    """Tests for DBfile class"""

    def setUp(self):
        super(UtilsTests, self).setUp()

    def tearDown(self):
        super(UtilsTests, self).tearDown()

    def test_dirSubs(self):
        """dirSubs substitutions should work"""
        path = '{Y}{m}{d}'
        filename = 'test_filename'
        utc_file_date = datetime.date(2012, 4, 12)
        utc_start_time = datetime.datetime(2012, 4, 12, 1, 2, 3)
        version = '1.2.3'
        version2 = Version.Version(3, 2, 1)
        self.assertEqual('20120412', Utils.dirSubs(path, filename, utc_file_date, utc_start_time, version))
        path = '{DATE}'
        self.assertEqual('20120412', Utils.dirSubs(path, filename, utc_file_date, utc_start_time, version))
        path = '{Y}{b}{d}'
        self.assertEqual('2012Apr12', Utils.dirSubs(path, filename, utc_file_date, utc_start_time, version))
        path = '{Y}{j}'
        self.assertEqual('2012103', Utils.dirSubs(path, filename, utc_file_date, utc_start_time, version))
        path = '{VERSION}'
        self.assertEqual('1.2.3', Utils.dirSubs(path, filename, utc_file_date, utc_start_time, version))
        self.assertEqual('3.2.1', Utils.dirSubs(path, filename, utc_file_date, utc_start_time, version2))

    def test_chunker(self):
        """chunker()"""
        self.assertEqual(list(Utils.chunker(range(10), 3)), [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]])
        self.assertEqual(list(Utils.chunker(range(10), 4)), [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]])
        self.assertEqual(list(Utils.chunker(range(10), 4)), [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]])
        self.assertEqual(list(Utils.chunker(range(10), 10)), [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]])
        self.assertEqual(list(Utils.chunker(range(10), 20)), [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]])

    def test_unique(self):
        """unique"""
        self.assertEqual(Utils.unique(range(5)), list(range(5)))
        self.assertEqual(Utils.unique([1, 1, 2, 2, 3]), [1, 2, 3])
        self.assertEqual(Utils.unique([1, 1, 3, 2, 2, 3]), [1, 3, 2])

    def test_expandDates(self):
        """expandDates"""
        d1 = datetime.datetime(2013, 1, 1)
        d2 = datetime.datetime(2013, 1, 2)
        d3 = datetime.datetime(2013, 1, 3)

        self.assertEqual(list(Utils.expandDates(d1, d1)), [d1])
        self.assertEqual(list(Utils.expandDates(d1, d2)), [d1, d2])
        self.assertEqual(list(Utils.expandDates(d1, d3)), [d1, d2, d3])

    def test_parseDate(self):
        """parseDate"""
        self.assertEqual(datetime.datetime(2013, 1, 1), Utils.parseDate('2013-01-01'))
        self.assertRaises(ValueError, Utils.parseDate, '2013-13-01')

    def test_parseVersion(self):
        """parseVersion"""
        self.assertEqual(Version.Version(1, 2, 3), Utils.parseVersion('1.2.3'))
        self.assertRaises(TypeError, Utils.parseVersion, '1.2')

    def test_flatten(self):
        """flatten"""
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8, 9], list(Utils.flatten([[1, 2], [3, 4, 5], [6, 7], [8], [9]])))

    def test_toBool(self):
        """toBool"""
        invals = ['True', 'true', True, 1, 'Yes', 'yes']
        for v in invals:
            self.assertTrue(Utils.toBool(v))
        invals = ['sdg', 'false', False, 'sagdfa']
        for v in invals:
            self.assertFalse(Utils.toBool(v))

    def test_toNone(self):
        """toNone"""
        invals = ['', 'None', 'none', 'NONE']
        for v in invals:
            self.assertTrue(Utils.toNone(v) is None)
        invals = ['sdg', 'false', False, 'sagdfa']
        for v in invals:
            self.assertFalse(Utils.toNone(v) is None)

    def test_daterange_to_dates(self):
        """daterange_to_dates"""
        daterange = [datetime.datetime(2000, 1, 4), datetime.datetime(2000, 1, 6)]
        expected = [datetime.datetime(2000, 1, 4), datetime.datetime(2000, 1, 5), datetime.datetime(2000, 1, 6)]
        self.assertEqual(expected, Utils.daterange_to_dates(daterange))
        daterange = [datetime.datetime(2000, 1, 4), datetime.datetime(2000, 1, 5, 23)]
        expected = [datetime.datetime(2000, 1, 4), datetime.datetime(2000, 1, 5)]
        self.assertEqual(expected, Utils.daterange_to_dates(daterange))

    def test_strargs_to_args_1(self):
        """strargs_to_args tests"""
        self.assertTrue(Utils.strargs_to_args(None) is None)

    def test_strargs_to_args_2(self):
        """strargs_to_args tests"""
        tst = Utils.strargs_to_args('arg1=1 arg2=2')
        self.assertEqual({ 'arg2': '2', 'arg1': '1' }, tst)

    def test_strargs_to_args_3(self):
        """strargs_to_args tests"""
        tst = Utils.strargs_to_args(['arg1=1', 'arg2=2'])
        self.assertEqual({ 'arg2': '2', 'arg1': '1' }, tst)

    def test_strargs_to_args_4(self):
        """strargs_to_args tests"""
        tst = Utils.strargs_to_args(['arg1=1'])
        self.assertEqual({ 'arg1': '1' }, tst)

    def test_processRunning(self):
        """processRunning should work"""
        pid = os.getpid()
        self.assertTrue(Utils.processRunning(pid))
        # TODO is there a smarter way to do this that can never be running?
        self.assertFalse(Utils.processRunning(655434))

    def test_extract_YYYYMMDD(self):
        """extract_YYYYMMDD works"""
        self.assertEqual(datetime.datetime(2013, 2, 14, 0, 0),
                         Utils.extract_YYYYMMDD('rbspa_pre_ect-hope-L1_20130214_v1.0.0.cdf'))
        self.assertEqual(None, Utils.extract_YYYYMMDD('rbspa_pre_ect-hope-L1_20130231_v1.0.0.cdf'))
        self.assertEqual(None, Utils.extract_YYYYMMDD('rbspa_pre_ect-hope-L1_19520201_v1.0.0.cdf'))
        self.assertEqual(None, Utils.extract_YYYYMMDD('rbspa_pre_ect-hope-L1_20510201_v1.0.0.cdf'))

    def test_valid_YYYYMMDD(self):
        """valid_YYYYMMDD works"""
        self.assertTrue(Utils.valid_YYYYMMDD('20121212'))
        self.assertTrue(Utils.valid_YYYYMMDD('20120229'))
        self.assertFalse(Utils.valid_YYYYMMDD('20120230'))

    def test_extract_YYYYMM(self):
        """extract_YYYYMMDD works"""
        self.assertEqual(datetime.date(2013, 2, 1),
                         Utils.extract_YYYYMM('rbspa_pre_ect-hope-L1_201302_v1.0.0.cdf'))
        self.assertEqual(datetime.date(2013, 2, 1),
                         Utils.extract_YYYYMM('rbspa_pre_ect-hope-L1_20130214_v1.0.0.cdf'))
        self.assertEqual(None, Utils.extract_YYYYMM('rbspa_pre_ect-hope-L1_205102_v1.0.0.cdf'))
        self.assertEqual(None, Utils.extract_YYYYMM('rbspa_pre_ect-hope-L1_205_v1.0.0.cdf'))


if __name__ == "__main__":
    unittest.main()
