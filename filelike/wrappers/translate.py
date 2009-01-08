# filelike/wrappers/translate.py
#
# Copyright (C) 2006-2008, Ryan Kelly
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.
#
"""

    filelike.wrappers.translate:  pass file contents through translation func
    
This module provides the filelike wrapper 'Translate', which passes file
data through a translation function as it is read/written.

""" 

import filelike
from filelike.wrappers import FileWrapper

import unittest
from StringIO import StringIO


class Translate(FileWrapper):
    """Class implementing some translation on a file's contents.
    
    This class wraps a file-like object in another file-like object,
    applying a given function to translate the file's contents as it is
    read or written.
    
    The translating function must accept a string as its only argument,
    and return a transformed string representing the updated file contents.
    If the transform needs to be flushed when reading/writing is finished, it
    should provide a flush() method that returns either None, or any data
    remaining to be read/written.
    
    The default use case assumes either reading+writing with a stateless
    translation function, or exclusive reading or writing.  So, a single
    function is used for translation on both reads and writes.  Separate
    reading and writing translation functions may be provided using keyword
    arguments 'rfunc' and 'wfunc' to the constructor.

    Note that it must be possible to flush the translation function 
    multiple times, and at any time.  If you're using a function that
    expects to be flushed only at the end of the data stream, consider
    using one of 'ReadStreamTranslate' and 'WriteStreamTranslate' instead.

    If the translaton function operates on a byte-per-byte basis and
    does not buffer any data, consider using the 'BytewiseTranslate'
    class instead; the efficiency of several operations can be improved
    dramatically given such properties of the translation function.
    """
    
    def __init__(self,fileobj,func=None,mode=None,rfunc=None,wfunc=None):
        """Translate file wrapper constructor.

        'fileobj' must be the file-like object whose contents are to be
        transformed, and 'func' the callable that will transform the
        contents.  'mode' should be one of "r" or "w" to indicate whether
        reading or writing is desired.  If omitted it is determined from
        'fileobj' where possible, otherwise it defaults to "r".
        
        If separate reading/writing translations are required, the
        keyword arguments 'rfunc' and 'wfunc' can be used in place of
        'func'.
        """
        super(Translate,self).__init__(fileobj,mode)
        if func is not None:
            if rfunc is not None:
                raise ValueError("Cannot specify both <func> and <rfunc>")
            if wfunc is not None:
                raise ValueError("Cannot specify both <func> and <wfunc>")
            self._rfunc = func
            self._wfunc = func
        else:
            if hasattr(self,"mode"):
              if "r" in self.mode or "+" in self.mode:
                if rfunc is None:
                  raise ValueError("Must provide <rfunc> for readable files")
              if "w" in self.mode or "a" in self.mode:
                if wfunc is None:
                  raise ValueError("Must provide <wfunc> for writable files")
            self._rfunc = rfunc
            self._wfunc = wfunc
        self._pos = 0
            
    def _flush_rfunc(self):
        """Call flush on the reading translation function, if necessary."""
        if hasattr(self._rfunc,"flush"):
            return self._rfunc.flush()
        return None
   
    def _flush_wfunc(self):
        """Call flush on the writing translation function, if necessary."""
        if hasattr(self._wfunc,"flush"):
            return self._wfunc.flush()
        return None

    def flush(self):
        data = self._flush_wfunc()
        if data is not None:
            self._fileobj.write(data)
        super(Translate,self).flush()

    def _read(self,sizehint=-1):
        """Read approximately <sizehint> bytes from the file."""
        data = self._fileobj.read(sizehint)
        if data == "":
            tData = self._flush_rfunc()
            if not tData:
                return None
        else:
            tData = self._rfunc(data)
        self._pos += len(tData)
        return tData
    
    def _write(self,data,flushing=False):
        """Write the given data to the file."""
        self._pos += len(data)
        self._fileobj.write(self._wfunc(data))

    def _tell(self):
        return self._pos

    def _seek(self,offset,whence):
        if whence > 0:
            raise NotImplementedError
        # Really slow simulation of seek, using the sbuffer machinery.
        # Is there much else we can do in this case?
        self._fileobj.seek(0,0)
        self._pos = 0
        sbuf = ""
        while len(sbuf) < offset:
            sbuf = self._read(self._bufsize)
        self._fileobj.seek(0,0)
        self._pos = 0
        return sbuf[:offset]


class Test_Translate(filelike.Test_ReadWriteSeek):
    """Testcases for the Translate class, with null translation func."""
    
    def makeFile(self,contents,mode):
        def noop(string):
            return string
        return Translate(StringIO(contents),noop,mode=mode)

    
class BytewiseTranslate(FileWrapper):
    """Class implementing a bytewise translation on a file's contents.
    
    This class wraps a file-like object in another file-like object,
    applying a given function to translate the file's contents as it is
    read or written.  It could be used, for example, to encrypt a file
    as it's being written.
    
    The translating function must accept a string as its only argument,
    and return a transformed string representing the updated file contents.
    Since this is a bytewise translation, the returned string must be of
    the same length.  The translation function may not buffer any data.
    
    If a single function is provided it is used for both reads and writes.
    To use separate functions, provide the keyword arguments 'wfunc' and
    'rfunc'.
    """

    def __init__(self,fileobj,func=None,mode=None,rfunc=None,wfunc=None):
        """BytewiseTranslate file wrapper constructor.

        'fileobj' must be the file-like object whose contents are to be
        transformed, and 'func' the callable that will transform the
        contents.  'mode' should be one of "r" or "w" to indicate whether
        reading or writing is desired.  If omitted it is determined from
        'fileobj' where possible, otherwise it defaults to "r".
        
        If separate reading/writing translations are required, the
        keyword arguments 'rfunc' and 'wfunc' can be used in place of
        'func'.
        """
        super(BytewiseTranslate,self).__init__(fileobj,mode)
        if func is not None:
            if rfunc is not None:
                raise ValueError("Cannot specify both <func> and <rfunc>")
            if wfunc is not None:
                raise ValueError("Cannot specify both <func> and <wfunc>")
            self._rfunc = func
            self._wfunc = func
        else:
            if hasattr(self,"mode"):
              if "r" in self.mode or "+" in self.mode:
                if rfunc is None:
                  raise ValueError("Must provide <rfunc> for readable files")
              if "w" in self.mode or "a" in self.mode:
                if wfunc is None:
                  raise ValueError("Must provide <wfunc> for writable files")
            self._rfunc = rfunc
            self._wfunc = wfunc
            
    def _read(self,sizehint=-1):
        """Read approximately <sizehint> bytes from the file."""
        data = self._fileobj.read(sizehint)
        if data == "":
            return None
        return self._rfunc(data)
    
    def _write(self,data,flushing=False):
        """Write the given data to the file."""
        self._fileobj.write(self._wfunc(data))

    # Since this is a bytewise translation, the default seek() and tell()
    # will do what we want - simply move the underlying file object.


class Test_BytewiseTranslate(filelike.Test_ReadWriteSeek):
    """Testcases for the BytewiseTranslate class."""
    
    def makeFile(self,contents,mode):
        def rot13(string):
            return string.encode("rot13")
        return BytewiseTranslate(StringIO(contents.encode("rot13")),rot13,mode=mode)


class ReadStreamTranslate(FileWrapper):
    """Class implementing a streaming read translation on a file's contents.
    
    This class wraps a file-like object in another file-like object,
    applying a given function to translate the file's contents as it is
    read.  It could be used, for example, to decompress a file on the fly.
    
    This class is designed for working with streaming translation functions,
    which buffer data internally and must be flushed exactly once, at stream
    termination.  It supports (emulated) seeking but cannot be written to.

    The constructor expects the argument 'func_factory' which will be called
    to create the translation function.
    """

    def __init__(self,fileobj,func_factory,mode=None):
        self._func_factory = func_factory
        f = Translate(fileobj,rfunc=func_factory(),mode="r")
        super(ReadStreamTranslate,self).__init__(f,mode="r")

    def _seek(self,offset,whence):
        if whence > 0:
            raise NotImplementedError
        self._fileobj._rfunc = self._func_factory()
        self._fileobj.seek(0,0)
        while offset > 0:
            sz = min(offset,self._bufsize)
            self._fileobj.read(sz)
            offset -= sz
        return None


class Test_ReadStreamTranslate(filelike.Test_ReadWriteSeek):
    """Testcases for the ReadStreamTranslate class."""
    
    def makeFile(self,contents,mode):
        def rot13_factory():
            def rot13(string):
                return string.encode("rot13")
            return rot13
        return ReadStreamTranslate(StringIO(contents.encode("rot13")),rot13_factory,mode=mode)

    def test_write_read(self):
        pass
    def test_read_write_read(self):
        pass
    def test_read_write_seek(self):
        pass


def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_Translate))
    suite.addTest(unittest.makeSuite(Test_BytewiseTranslate))
    suite.addTest(unittest.makeSuite(Test_ReadStreamTranslate))
    return suite

