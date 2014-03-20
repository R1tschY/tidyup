#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#    tidyup - is a little python script that remove backup files and files
#             generated by makefiles or automake
#    Copyright (C) 2012 R1tschY <r1tschy@yahoo.de>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import sys, os
from fnmatch import fnmatch
from tempfile import mkdtemp
import shutil
import subprocess
import argparse

# from here: http://www.peterbe.com/plog/uniqifiers-benchmark
def unique(seq, idfun=None): 
  # order preserving
  if idfun is None:
     def idfun(x): return x
  seen = {}
  result = []
  for item in seq:
    marker = idfun(item)
    if marker in seen: continue
    seen[marker] = 1
    result.append(item)
    
  return result

def walk_path(path, func, post_func):
  contents = os.listdir(path)
  if not func(path, contents): return
  
  for filename in contents:
    cpath = os.path.join(path, filename)
    if os.path.isdir(cpath):
      walk_path(cpath, func, post_func)
      
  post_func(path, os.listdir(path))
      
def check_pattern(filename):
  global patterns
  for p in patterns:
    if fnmatch(filename, p):
      return True
      
def process_file(path, filename):
  global tmpdir
  global root_path
  global options
  
  file_path = os.path.join(path, filename)
  rel_path = os.path.relpath(path, root_path)
  dest_path = os.path.join(tmpdir, rel_path, filename)
  dest_dir = os.path.join(tmpdir, rel_path)
  display_path = os.path.normpath(os.path.join(rel_path, filename))
  
  if not os.path.isdir(dest_dir) and not options.dry_run: 
    os.makedirs(dest_dir)
  
  if options.no_backup:
    print(display_path + ' -> remove')
    if options.dry_run: return
    if os.path.isdir(file_path):
      shutil.rmtree(file_path)
    else:
      os.remove(file_path)
  else:
    if not os.path.isdir(dest_path):
      print(display_path + ' -> move to backup archive')
      if not options.dry_run:
        shutil.move(file_path, dest_path)      
    else:
      print(display_path + ' -> ignored, see TODO in README')
  
def process_path(path, files):
  global root_path
  global options

  if not options.ignore_makefiles and 'Makefile' in files:
    rel_path = os.path.relpath(path, root_path)
    os.chdir(path)
    
    # Check for automake
    if 'configure' in files:
      print(rel_path + ' -> make distclean')
      if options.dry_run: return
      
      null = open('/dev/null', 'r+')
      subprocess.call(['make', 'distclean'], stdout=null, stdin=null)
      null.close()
    # Check for Makefile
    else:
      print(rel_path + ' -> make clean')
      if options.dry_run: return
      null = open('/dev/null', 'r+')
      subprocess.call(['make', 'clean'], stdout=null, stdin=null)
      null.close()
      
    files = os.listdir(path)
    
  # Check for empty directory
  if not options.ignore_empty_folders and len(files) == 0:
    process_file(os.path.dirname(path), os.path.basename(path))
    return False
  
  # Check for Pattern
  for f in files:
    if check_pattern(f):
      process_file(path, f)

  return True
  
def post_process_path(path, files):
  global root_path
  global options
    
  # Check for empty directory
  if not options.ignore_empty_folders and len(files) == 0:
    process_file(os.path.dirname(path), os.path.basename(path))
    
    
    
  
parser = argparse.ArgumentParser(usage='%(prog)s [options] [PATH]')
parser.add_argument("path", metavar='PATH', nargs='?',
                    help='Path to search for files to remove',
                    default=os.getcwd())
parser.add_argument("-p", "--pattern",
                    help='slash separated list of search pattern for files to remove (You can use shell wildcards: e.x. *.bak/*~)',
                    metavar="<pattern>",
                    default='')
parser.add_argument("-n", "--dry-run",
                    action="store_true",
                    help='perform a trial run with no changes made',
                    default=False)                   
parser.add_argument("--no-config",
                    action="store_true",
                    help='Don\'t use .tidyup file to read search pattern',
                    default=False)
parser.add_argument("--no-backup",
                    action="store_true",
                    help='Don\'t create a backup archive',
                    default=False)
parser.add_argument("--ignore-makefiles",
                    action="store_true",
                    help='Don\'t use Makefiles to clean up',
                    default=False)
parser.add_argument("--ignore-empty-folders",
                    action="store_true",
                    help='Don\'t process empty folders',
                    default=False)                    
parser.add_argument("-b", "--backup", metavar='path', nargs='?',
                    help='Backup filename without file extention (default: tidyup.backup)',
                    default='tidyup.backup')

options = parser.parse_args()

if not os.path.isdir(options.path):
  print('path ' + options.path + ' does not exist')
  sys.exit() 
else:
  root_path = os.path.abspath(options.path)

patterns = []
if not options.no_config:
  # Load configfile
  configfile = os.path.join(root_path, '.tidyup')
  if os.path.isfile(configfile):
    for line in open(configfile, 'r'):
      l = line.strip()
      if len(l) > 0 and l[0] != '#':
        patterns.append(l)
        
if len(options.pattern) != 0:
  patterns.extend(options.pattern.split('/'))

patterns = unique(patterns)

if len(patterns) == 0:
  print("No patterns to use")
  sys.exit()

# Create path variables
tmpdir_root = mkdtemp(prefix='tidyup')
tmpdir = os.path.join(tmpdir_root, os.path.basename(root_path))
archive_name = os.path.realpath(options.backup)
archive_path = archive_name + '.tar.gz'

# Merge with old backup files
if os.path.isfile(archive_path) and not options.dry_run:
  shutil.unpack_archive(archive_path, tmpdir_root, 'gztar')
  
# Process files
walk_path(root_path, process_path, post_process_path)

if options.dry_run: sys.exit(0)

# Pack backup
if os.path.isdir(tmpdir) and not options.no_backup:
  print(os.path.normpath('pack archive to ' + archive_path))
  archive_path = shutil.make_archive(archive_name, 'gztar', tmpdir_root, os.path.basename(root_path))

# Remove tmpdir
shutil.rmtree(tmpdir_root)


