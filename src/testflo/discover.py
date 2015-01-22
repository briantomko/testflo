
import os
import sys
import traceback
import inspect
import unittest

from fnmatch import fnmatch
from os.path import basename, dirname, isdir

from testflo.fileutil import find_files, get_module
from testflo.runner import get_testcase

def dryrun(input_iter):
    """Iterator added to the pipeline when user only wants
    a dry run, listing all of the discovered tests but not
    actually running them.
    """
    for spec in input_iter:
        print spec
        yield spec

class TestDiscoverer(object):

    def __init__(self, module_pattern='test*.py',
                       func_pattern='test*',
                       dir_exclude=None):
        self.module_pattern = module_pattern
        self.func_pattern = func_pattern
        self.dir_exclude = dir_exclude

    def get_iter(self, input_iter):
        """Returns an iterator over 'specific' testspec
        strings based on the starting list of
        directories/modules/testspecs.
        """
        seen = set()
        for test in input_iter:
            if isdir(test):
                itr = self._dir_iter
            else:
                itr = self._testspec_iter

            for result in itr(test):
                if result not in seen:
                    seen.add(result)
                    yield result

    def _dir_iter(self, dname):
        """Iterate over all tests in modules found in the given
        directory and its subdirectories.
        """
        for f in find_files(dname,
                            match=self.module_pattern,
                            direxclude=self.dir_exclude):
            if not basename(f).startswith('__init__.'):
                for result in self._module_iter(f):
                    yield result

    def _module_iter(self, filename):
        """Iterate over all testspecs in a module."""

        try:
            fname, mod = get_module(filename)
        except:
            sys.stderr.write(traceback.format_exc())
        else:
            if basename(fname).startswith('__init__.'):
                for result in self._dir_iter(dirname(fname)):
                    yield result
            else:
                for name, obj in inspect.getmembers(mod):
                    if inspect.isclass(obj):
                        if issubclass(obj, unittest.TestCase):
                            for result in self._testcase_iter(filename, obj):
                                yield result

                    elif inspect.isfunction(obj):
                        if fnmatch(name, self.func_pattern):
                            yield ':'.join((filename, obj.__name__))

    def _testcase_iter(self, fname, testcase):
        """Iterate over all testspecs found in a TestCase class."""

        methods = []
        for name, method in inspect.getmembers(testcase, inspect.ismethod):
            if fnmatch(name, self.func_pattern):
                methods.append(''.join((fname, ':', testcase.__name__,
                                               '.', method.__name__)))
        for m in sorted(methods):
            yield m

    def _testspec_iter(self, testspec):
        """Iterate over expanded testspec strings found in the
        module/testcase/method specified in testspec.  The format of
        testspec is one of the following:
            <module>
            <module>:<testcase>
            <module>:<testcase>.<method>
            <module>:<function>

        where <module> is either the python module path or the actual
        file system path to the .py file.
        """

        module, _, rest = testspec.partition(':')
        if rest:
            tcasename, _, method = rest.partition('.')
            if method:
                yield testspec
            else:  # could be a test function or a TestCase
                fname, mod = get_module(module)
                try:
                    tcase = get_testcase(fname, mod, tcasename)
                except (AttributeError, TypeError):
                    yield testspec
                else:
                    for spec in self._testcase_iter(fname, tcase):
                        yield spec
        else:
            for spec in self._module_iter(module):
                yield spec