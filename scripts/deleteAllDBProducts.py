#!/usr/bin/env python2.6


from dbprocessing import DBUtils


if __name__ == "__main__":
    a = DBUtils.DBUtils('rbsp')
    a._openDB()
    a._createTableObjects()
    prod_ids = zip(*a.getProductNames())[4]

    for ff in f:
        a._purgeFileFromDB(ff[0])
    print 'deleted {0} files'.format(len(f))

