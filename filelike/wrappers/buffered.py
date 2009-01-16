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
and writes through a separate buffer file to allow for seeking etc.  It
can be used to transform a one-shot read/write stream into a proper
file-like object.

""" 

import filelike
from filelike.wrappers import FileWrapper

import unittest
from StringIO import StringIO

try:
    from tempfile import SpooledTemporaryFile as TempFile
except ImportError:
    from tempfile import NamedTemporaryFile as TempFile


class Buffered(FileWrapper):
    """Class implementing buffereing of input and output streams.
    
    This class uses a separate buffer file as an intermediary between
    an input stream and an output stream.  As data is read from the
    input stream it is duplicated to the buffere file, allowing it to
    be seeked through without re-reading fro the stream.  When the
    file is closed, the contents of the buffer are written to the output
    stream.
    """
    
    def __init__(self,fileobj=None,mode=None,instream=None,outstream=None,onclose=None):
        """Buffered file wrapper constructor.

        Unlike most file-like wrappers, the wrapped file is allowed to
        be None; in this case a fresh temporary file is be used.
        'instream' is the stream from which data will be read, while
        'outstream' is the stream to which data will be written.
        """
        if fileobj is None:
            fileobj = TempFile()
        super(Buffered,self).__init__(fileobj,mode)
        if hasattr(self,"mode"):
            if "r" in mode or "+" in mode:
                if instream is None:
                    raise ValueError("Must specify an instream for readable files.")
            if "w" in mode or "a" in mode or "+" in mode:
                if outstream is None:
                    raise ValueError("Must specify an outstream for writable files.")
        self._in_eof = False
        self._in_pos = 0
        self._instream = instream
        self._outstream = outstream
        self.onclose = onclose
        if "a" in self.mode:
            self.seek(0,2)
 
    def close(self):
        if self.closed:
            return
        if self.onclose:
            self.onclose()
        if self._outstream:
            self._fileobj.seek(0,0)
            for ln in self._fileobj:
                self._outstream.write(ln)
            self._outstream.close()
        if self._instream:
            self._instream.close()
        super(Buffered,self).close()

    def _read(self,sizehint=-1):
        #  First return any data available from the buffer
        data = self._fileobj.read(sizehint)
        if data != "":
            return data
        # Then look for more data in the input stream
        if self._in_eof:
            return None
        data = self._instream.read(sizehint)
        if sizehint < 0 or len(data) < sizehint:
            self._in_eof = True
        self._in_pos += len(data)
        self._fileobj.write(data)
        return data

    def _write(self,data,flushing=False):
        super(Buffered,self)._write(data,flushing)
        if self._instream and not self._in_eof:
            diff = self._fileobj.tell() - self._in_pos
            if diff > 0:
                junk = self._instream.read(diff)
                self._in_pos += len(junk)
                if len(junk) < diff:
                    self._in_eof = True
    
    def _seek(self,offset,whence):
        # Ensure we've read enough to simply do the see on the buffer
        if not self._in_eof:
            if whence == 0:
                if offset > self._in_pos:
                    self._read_rest()
            if whence == 1:
                if self._fileobj.tell() + offset > self._in_pos:
                    self._read_rest()
            if whence == 2:
                self._read_rest()
        # Then just do it on the buffer...
        self._fileobj.seek(offset,whence)
        
    def _read_rest(self):
        """Read the rest of the input stream."""
        pos = self._fileobj.tell()
        self._fileobj.seek(0,2)
        for ln in self._instream:
            self._in_pos += len(ln)
            self._fileobj.write(ln)
        self._in_eof = True 
        self._fileobj.seek(pos)


class Test_Buffered(filelike.Test_ReadWriteSeek):
    """Testcases for the Buffered class."""
    
    def makeFile(self,contents,mode):
        return Buffered(None,mode=mode,instream=StringIO(contents),outstream=StringIO())

    
def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_Buffered))
    return suite

