#!/usr/bin/env python2.6

"""
in a given directory make symlinks to all the newest versions of files into another directory
"""

import ConfigParser
import datetime
import itertools
import glob
import os
from optparse import OptionParser
import re
import traceback
import shutil
import sys
import warnings

from dateutil import parser as dup

from dbprocessing import inspector


################################################################
# 1) In the current directory get all the file ids from the directory
# 2) If those files are not current version remove them from set
# 3) Check that the files are in the wanted dates
# 4) Create sumlinks to the file in a specified dir (latest by default)
################################################################


def argsort(seq):
    #http://stackoverflow.com/questions/3382352/equivalent-of-numpy-argsort-in-basic-python/3382369#3382369
    #by ubuntu
    return sorted(range(len(seq)), key=seq.__getitem__)

def get_all_files(indir, outdir, glb='*'):
    """
    in indir get all the files that follow the glob glb
    - indir is a full path
    - glb is a file glob
    """
    files = sorted(glob.glob(os.path.join(indir, glb)))
    files_out = sorted(glob.glob(os.path.join(outdir, glb)))
    return files, files_out

def getBaseVersion(f):
    """
    given an input filename return a tuple of base an version
    """
    base = re.split(r'v\d\d?\.\d\d?\.\d\d?\.', f)[0]
    version = inspector.extract_Version(f)
    return base, version

def cull_to_newest(files, options=None):
    """
    given a list of files cull to only the newest ones

    match everything in front of v\d\d?\.\d\d?\.\d\d?\.
    """
    ans = []
    # make a set of all the file bases
    bases = []
    versions = []
    for f in files:
        tmp = getBaseVersion(f)
        if tmp[1] is not None:
            bases.append(tmp[0])
            versions.append(tmp[1])
        else:
            if options.verbose: print("Skipped file {0}".format(f))
    uniq_bases = list(set(bases))
    for ub in uniq_bases:
        if bases.count(ub) == 1: # there is only one
            ans.append(files[bases.index(ub)])
        else: # must be more than
            indices = [i for i, x in enumerate(bases) if x == ub]
            tmp = []
            for i in indices:
                tmp.append((bases[i], versions[i], files[i]))
            ans.append(max(tmp, key=lambda x: x[1])[2])
    return ans

def cull_to_dates(files, startdate, enddate, nodate=False, options=None):
    """
    loop over the files and drop the ones that are outside of the range we want to include
    - call this after cull_to_newest()  # maybe doesn't matter
    """
    ans = []
    if nodate:
        return files
    for f in files:
        date = inspector.extract_YYYYMMDD(f)
        if not date:
            date = inspector.extract_YYYYMM(f)
        else:
            date = date.date()
        if not date:
            if options.verbose: print('skipping {0} no date found'.format(f))
            continue
        if date >= startdate and date <= enddate:
            ans.append(f)
        elif options.verbose:
            print("File {0} culled by date".format(f))
    return ans

def toBool(value):
    if value in ['True', 'true', True, 1, 'Yes', 'yes']:
        return True
    else:
        return False

def make_symlinks(files, files_out, outdir, linkdirs, mode, options):
    """
    for all the files make symlinks into outdir
    """
    if not hasattr(files, '__iter__'):
        files = [files]
    if not hasattr(files_out, '__iter__'):
        files_out = [files_out]
    # if files_out then cull the files to get rid of the ones
    for f in files:
        if not os.path.isdir(outdir):
            os.makedirs(outdir, int(mode, 8))
        outf = os.path.join(outdir, os.path.basename(f))
        try:
            if os.path.isfile(f) and not os.path.isfile(outf):
                if options.verbose: print("linking1 {0}->{1}".format(f, outf))
                os.symlink(f, outf)
            elif toBool(linkdirs):
                if options.verbose: print("linking2 {0}->{1}".format(f, outf))
                os.symlink(f, outf)
        except:
            warnings.warn("File {0} not linked:\n\t{1}".format(f, traceback.format_exc()))

def delete_unneeded(files, files_out, options):
    """
    delete the link that are not needed
    """
    files_tmp = [os.path.basename(f) for f in files]
    for f in files_out:
        if os.path.basename(f) not in files_tmp:
            try:
                os.remove(f)
            except OSError:
                pass
            if options.verbose: print("removing unneeded link {0}".format(f))


def readconfig(config_filepath):
    expected_items = ['sourcedir', 'destdir', 'deltadays', 'startdate',
                      'enddate', 'filter', 'linkdirs', 'outmode', 'nodate']
    # Create a ConfigParser object, to read the config file
    cfg=ConfigParser.SafeConfigParser()
    cfg.read(config_filepath)
    sections = cfg.sections()
    # Read each parameter in turn
    ans = {}
    for section in sections:
        ans[section] = dict(cfg.items(section))
    # make sure that for each section the reqiured items are present
    for k in ans:
        for ei in expected_items:
            if ei not in ans[k]:
                raise(ValueError('Section [{0}] does not have required key "{1}"'.format(k, ei)))
    # check that we can parse the dates
    for k in ans:
        try:
            tmp = dup.parse(ans[k]['startdate'])
        except:
            raise(ValueError('Date "{0}" in [{1}][{2}] is not valid'.format(ans[k]['startdate'], k, 'startdate',)))
        try:
            tmp = dup.parse(ans[k]['enddate'])
        except:
            raise(ValueError('Date "{0}" in [{1}][{2}] is not valid'.format(ans[k]['enddate'], k, 'enddate')))
        try:
            tmp = int(ans[k]['deltadays'])
        except:
            raise(ValueError('Invalid "{0}" in [{1}][{2}]'.format(ans[k]['deltadays'], k, 'deltadays')))
        try:
            tmp = int(ans[k]['outmode'])
        except:
            raise(ValueError('Invalid "{0}" in [{1}][{2}]'.format(ans[k]['outmode'], k, 'outmode')))
    for k in ans:
        ans[k]['sourcedir'] = os.path.abspath(os.path.expanduser(os.path.expandvars(ans[k]['sourcedir'])))
        ans[k]['destdir']   = os.path.abspath(os.path.expanduser(os.path.expandvars(ans[k]['destdir'])))
                
    return ans


if __name__ == '__main__':
    usage = "usage: %prog config"
    parser = OptionParser(usage=usage)
    parser.add_option("", "--verbose",
                  dest="verbose", action='store_true',
                  help="Print out verbose information", default=False)
    parser.add_option("-l", "--list",
                  dest="list", action='store_true',
                  help="Instead of syncing list the sections of the conf file", default=False)
    parser.add_option("-f", "--filter",
                  dest="filter", 
                  help="Comma seperated list of strings that must be in the sync conf name (e.g. -f hope,rbspa)", default=None)

    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.error("incorrect number of arguments")

    conffile = os.path.abspath(os.path.expanduser((os.path.expandvars(args[0]))))
    if not os.path.isfile(conffile):
        parser.error("Config file not readable ({0})".format(conffile))
        
    config = readconfig(conffile)

    config2 = {}
    if options.filter is not None:
        filters = options.filter.split(',')
        if options.verbose:
            print("Filters: {0}".format(filters))
        for c in config:
            num = 0 
            for f in filters:
                print("Filter {0}".format(filters))
                if f in c:
                    num += 1
            if num == len(filters):
                config2[c] = config[c]
        config = config2
        
    if options.list:
        out = []
        for c in config:
            print(c)
        sys.exit(0)
    print config

    for sec in config:
        print('Processing [{0}]'.format(sec))
        filter = config[sec]['filter']
        for filt in filter.split(','):
            files = []
            files_out = []
            print filt
            files_t, files_out_t = get_all_files(config[sec]['sourcedir'], config[sec]['destdir'], filt)
            files.extend(files_t)
            files_out.extend(files_out_t)
            delete_unneeded(files, files_out, options)
            if files:
                files = cull_to_newest(files, options=options)
                startdate = dup.parse(config[sec]['startdate']).date()
                enddate   = dup.parse(config[sec]['enddate']).date()
                delta     = datetime.date.today() - datetime.timedelta(days = int(config[sec]['deltadays']))
                if delta < enddate:
                    enddate = delta
                if not toBool(config[sec]['nodate']):
                    files = cull_to_dates(files, startdate, enddate, options=options)
            else:
                print('   No files found for [{0}]'.format(sec))
                delete_unneeded(files, files_out, options)
            delete_unneeded(files, files_out, options)

            make_symlinks(files, files_out, config[sec]['destdir'], config[sec]['linkdirs'], config[sec]['outmode'], options)

