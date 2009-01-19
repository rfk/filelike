# filelike/wrappers/translate.py
#
# Copyright (C) 2006-2009, Ryan Kelly
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

    filelike.wrappers.buffered:  buffering of streams to create a file
    
This module provides the filelike wrapper 'Buffered', which routes reads
and writes through a separate buffer file.  This allows the full file-like
interface to be provided, including seek() and tell(), while guaranteeing
that the underlying file is treated like a stream, with only read() and
write() being called.

""" 

import filelike
from filelike.wrappers import FileWrapper

import unittest
from StringIO import StringIO

try:
    from tempfile import SpooledTemporaryFile as TemporaryFile
except ImportError:
    from tempfile import TemporaryFile


class Buffered(FileWrapper):
    """Class implementing buffereing of input and output streams.
    
    This class uses a separate buffer file to hold the contents of the
    underlying file while they are being manipulated.  As data is read
    it is duplicated into the buffer, and data is written from the buffer
    back to the file on close.
    """
    
    def __init__(self,fileobj,mode=None):
        """Buffered file wrapper constructor."""
        super(Buffered,self).__init__(fileobj,mode)
        self._buffer = TemporaryFile()
        self._in_eof = False
        self._in_pos = 0
        if hasattr(self,"mode") and "a" in self.mode:
            self.seek(0,2)

    def flush(self):
        # a no-op, we only want to write to the file on close
        pass
 
    def close(self):
        if self.closed:
            return
        if self._check_mode("w"):
            if self._check_mode("r"):
                if not self._in_eof:
                    self._read_rest()
                self._fileobj.seek(0,0)
            self._buffer.seek(0,0)
            for ln in self._buffer:
                self._fileobj.write(ln)
        super(Buffered,self).close()

    def _read(self,sizehint=-1):
        #  First return any data available from the buffer
        data = self._buffer.read(sizehint)
        if data != "":
            return data
        # Then look for more data in the underlying file
        if self._in_eof:
            return None
        data = self._fileobj.read(sizehint)
        if sizehint < 0 or len(data) < sizehint:
            self._in_eof = True
        self._in_pos += len(data)
        self._buffer.write(data)
        return data

    def _write(self,data,flushing=False):
        self._buffer.write(data)
        if self._check_mode("r") and not self._in_eof:
            diff = self._buffer.tell() - self._in_pos
            if diff > 0:
                junk = self._fileobj.read(diff)
                self._in_pos += len(junk)
                if len(junk) < diff:
                    self._in_eof = True
    
    def _seek(self,offset,whence):
        # Ensure we've read enough to simply do the seek on the buffer
        if self._check_mode("r") and not self._in_eof:
            if whence == 0:
                if offset > self._in_pos:
                    self._read_rest()
            if whence == 1:
                if self._buffer.tell() + offset > self._in_pos:
                    self._read_rest()
            if whence == 2:
                self._read_rest()
        # Then just do it on the buffer...
        self._buffer.seek(offset,whence)

    def _tell(self):
        return self._buffer.tell()
        
    def _read_rest(self):
        """Read the rest of the input stream."""
        pos = self._buffer.tell()
        self._buffer.seek(0,2)
        data = self._fileobj.read(self._bufsize)
        while data:
            self._in_pos += len(data)
            self._buffer.write(data)
            data = self._fileobj.read(self._bufsize)
        self._in_eof = True 
        self._buffer.seek(pos)


class Test_Buffered(filelike.Test_ReadWriteSeek):
    """Testcases for the Buffered class."""
    
    def makeFile(self,contents,mode):
        return Buffered(StringIO(contents),mode)

    
def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_Buffered))
    return suite

