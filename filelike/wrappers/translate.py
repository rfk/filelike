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
    read or written.  It could be used, for example, to read from a 
    gzipped source file or to encrypt a file as it's being written.
    
    The translating function must accept a string as its only argument,
    and return a transformed string representing the updated file contents.
    No guarantees are made about the amount of data fed into the function
    at a time (although another wrapper like FixedBlockSize could be
    used to do so).  If the transform needs to be flushed when reading/writing
    is finished, it should provide a flush() method that returns either None,
    or any data remaining to be read/written.
    
    The default use case assumes either reading+writing with a stateless
    translation function, or exclusive reading or writing.  So, a single
    function is used for translation on both reads and writes.  Separate
    reading and writing translation functions may be provided using keyword
    arguments 'rfunc' and 'wfunc' to the constructor.
    """
    
    def __init__(self,fileobj,func=None,mode=None,rfunc=None,wfunc=None,bytewise=False):
        """Translate file wrapper constructor.

        'fileobj' must be the file-like object whose contents are to be
        transformed, and 'func' the callable that will transform the
        contents.  'mode' should be one of "r" or "w" to indicate whether
        reading or writing is desired.  If omitted it is determined from
        'fileobj' where possible, otherwise it defaults to "r".
        
        If separate reading/writing translations are required, the
        keyword arguments 'rfunc' and 'wfunc' can be used in place of
        'func'.

        If the translation is guaranteed to generate a single byte of output
        for every byte of input, set the keyword argument 'bytewise' to True.
        This will increase the efficiency of some operations, in particular
        of seek() and tell().
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
        self.bytewise = bytewise
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
        # Flush func if necessary, when writing
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
        # We can only do relative seeks if it's a bytewise translation.
        if self.bytewise:
            self._fileobj.seek(offset,whence)
            self._pos = self._fileobj.tell()
            self._flush_rfunc()
            self._flush_wfunc()
            return None
        else:
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


class Test_TranslateNull(filelike.Test_ReadWriteSeek):
    """Testcases for the Translate class with null translation."""
    
    def makeFile(self,contents,mode):
        def noop(string):
            return string
        return Translate(StringIO(contents),noop,mode=mode)


class Test_TranslateRot13(filelike.Test_ReadWriteSeek):
    """Testcases for the Translate class with Rot13 translation."""
    
    def makeFile(self,contents,mode):
        def rot13(string):
            return string.encode("rot13")
        return Translate(StringIO(contents.encode("rot13")),rot13,bytewise=True,mode=mode)
    

def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_TranslateNull))
    suite.addTest(unittest.makeSuite(Test_TranslateRot13))
    return suite

