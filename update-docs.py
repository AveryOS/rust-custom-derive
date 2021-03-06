#!/usr/bin/env python2
# coding: utf-8

# Copyright ⓒ 2015, 2016 Daniel Keep.
#
# Licensed under the MIT license (see LICENSE or <http://opensource.org
# /licenses/MIT>) or the Apache License, Version 2.0 (see LICENSE of
# <http://www.apache.org/licenses/LICENSE-2.0>), at your option. All
# files in the project carrying such notice may not be copied, modified,
# or distributed except according to those terms.

import distutils.dir_util
import os
import shutil
import subprocess
import sys
import tempfile
import time

USE_ANSI = True if sys.platform != 'win32' else os.environ.get('FORCE_ANSI', '') != ''
TRACE_UPDATE_DOCS = os.environ.get('TRACE_UPDATE_DOCS', '') != ''
DOC_PKG_DIR = 'doc-pkg'

def sh(cmd):
    msg_trace('sh(%r)' % cmd)
    try:
        subprocess.check_call(cmd, shell=True)
    except:
        msg_trace('FAILED!')
        raise

def sh_eval(cmd, codec='utf-8'):
    msg_trace('sh_eval(%r)' % cmd)
    result = None
    try:
        result = subprocess.check_output(cmd, shell=True).decode(codec).strip()
    except:
        msg_trace('FAILED!')
        raise
    return result

def msg(*args):
    if USE_ANSI: sys.stdout.write('\x1b[1;34m')
    sys.stdout.write('> ')
    if USE_ANSI: sys.stdout.write('\x1b[1;32m')
    for arg in args:
        sys.stdout.write(str(arg))
    if USE_ANSI: sys.stdout.write('\x1b[0m')
    sys.stdout.write('\n')
    sys.stdout.flush()

def msg_trace(*args):
    if TRACE_UPDATE_DOCS:
        if USE_ANSI: sys.stderr.write('\x1b[1;31m')
        sys.stderr.write('$ ')
        if USE_ANSI: sys.stderr.write('\x1b[0m')
        for arg in args:
            sys.stderr.write(str(arg))
        sys.stderr.write('\n')
        sys.stderr.flush()

def copytree(src, dst):
    msg_trace('copytree(%r, %r)' % (src, dst))
    distutils.dir_util.copy_tree(src=src, dst=dst)

def really_rmtree(path):
    msg_trace('really_rmtree(%r)' % path)

    WAIT_TIME_SECS = 1.0
    MAX_TRIES = 10

    def on_error(func, path, exc_info):
        """
        Error handler for ``shutil.rmtree``.

        If the error is due to an access error (read only file)
        it attempts to add write permission and then retries.

        If the error is for another reason it re-raises the error.

        Usage: ``shutil.rmtree(path, onerror=on_error)``

        From <http://stackoverflow.com/a/2656405>_.
        """
        import stat
        if not os.access(path, os.W_OK):
            # Is the error an access error ?
            os.chmod(path, stat.S_IWUSR)
            func(path)
        else:
            raise

    for _ in range(MAX_TRIES):
        failed = True
        try:
            msg_trace('shutil.rmtree(%r)' % path)
            shutil.rmtree(path, onerror=on_error)
            failed = False
        except WindowsError:
            time.sleep(WAIT_TIME_SECS)
        if not failed: return

    msg('Warning: failed to remove directory %r' % path)

def gen_doc_bare(tmp1, tmp2):
    msg("Generating documentation from regular package...")
    sh('cargo doc')
    tmp1_target_doc = '%s/target/doc' % tmp1
    msg_trace('shutil.move(%r, %r)' % (tmp1_target_doc, tmp2))
    shutil.move(tmp1_target_doc, tmp2)

def gen_doc_pkg(tmp1, tmp2, doc_pkg):
    import json
    old_dir = os.getcwdu()
    try:
        msg("Generating documentation from doc package...")
        msg_trace('doc_pkg = %r' % doc_pkg)
        msg_trace('os.chdir(%r)' % doc_pkg)
        os.chdir(doc_pkg)
        manifest_str = sh_eval('cargo read-manifest --manifest-path "%s"'
            % os.path.join(doc_pkg, 'Cargo.toml'))
        manifest = json.loads(manifest_str)
        for dep in (d['name'] for d in manifest['dependencies']):
            sh('cargo doc --package %s' % dep)
        target_doc = os.path.join(doc_pkg, 'target/doc')
        msg_trace('shutil.move(%r, %r)' % (target_doc, tmp2))
        shutil.move(target_doc, tmp2)
    finally:
        msg_trace('os.chdir(%r)' % old_dir)
        os.chdir(old_dir)

def main():
    if sh_eval('git symbolic-ref --short HEAD') != u'master': return 0

    last_rev = sh_eval('git rev-parse HEAD')
    last_msg = sh_eval('git log -1 --pretty=%B')
    msg_trace('last_rev = %r' % last_rev)
    msg_trace('last_msg = %r' % last_msg)

    dir = os.getcwdu()
    msg_trace('dir = %r' % dir)

    tmp1 = tempfile.mkdtemp(prefix='gh-pages-post-commit-checkout-')
    tmp2 = tempfile.mkdtemp(prefix='gh-pages-post-commit-temp-')
    msg_trace('tmp1 = %r' % tmp1)
    msg_trace('tmp2 = %r' % tmp2)

    try:
        msg("Cloning into a temporary directory...")
        sh('git clone -qb gh-pages "%s" "%s"' % (dir, tmp1))
        msg_trace('os.chdir(%r)' % tmp1)
        os.chdir(tmp1)
        sh('git checkout -q master')

        if not os.path.exists(DOC_PKG_DIR):
            gen_doc_bare(tmp1, tmp2)
        else:
            gen_doc_pkg(tmp1, tmp2, os.path.abspath(DOC_PKG_DIR))

        msg('Updating gh-pages...')
        sh('git checkout -q gh-pages')
        sh('git clean -dfq')
        tmp2_doc = '%s/doc' % tmp2

        msg_trace('copytree(%r, %r)' % (tmp2_doc, './doc'))
        copytree(tmp2_doc, './doc')

        msg('Committing changes...')
        sh('git add .')
        sh('git commit -m "Update docs for %s" -m "%s"' % (last_rev[:7], last_msg))

        sh('git push -qu origin gh-pages')

    finally:
        msg('Cleaning up...')
        msg_trace('os.chdir(%r)' % dir)
        os.chdir(dir)
        msg_trace('shutil.rmtree(%r)' % tmp2)
        really_rmtree(tmp2)
        msg_trace('shutil.rmtree(%r)' % tmp1)
        really_rmtree(tmp1)

    msg('Done.  Use `git push origin gh-pages` to update live documentation.')


if __name__ == '__main__':
    sys.exit(main())
