#!/usr/bin/env python2.6

from __future__ import print_function

import sys

from dbprocessing import DBUtils

if len(sys.argv) != 2:
    print("Usage: {0} database".format(sys.argv[0]))
    sys.exit(-1)

if __name__ == "__main__":
    a = DBUtils.DBUtils(sys.argv[1])
    n_items = a.Processqueue.len()
    a.Processqueue.flush()
    print('Flushed {0} items from queue'.format(n_items))

