# filelike/wrappers/unix.py
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

    filelike.wrappers.unix:  wrapper classes emulating unix commands
    
This module provides filelike wrapper classes inspired by standard unix
command-line programs.  Currently these include:

    * Head:    read/write only a the first N bytes or lines in a file

""" 

import filelike
from filelike.wrappers import FileWrapper

import unittest
from StringIO import StringIO


class Head(FileWrapper):
    """Wrapper acting like unix "head" command.
    
    This wrapper limits the amount of data returned from or written to the
    underlying file based on the number of bytes and/or lines.  This class
    currently does not support seeking or simultaneous read/write.
    
    NOTE: no guarantees are made about the amount of data read *from*
          the underlying file, only about the amount of data returned to
          the calling function.
    """
    
    def __init__(self,fileobj,mode=None,bytes=None,lines=None):
        """Head wrapper constructor.

        The arguments 'bytes' and 'lines' specify the maximum number
        of bytes and lines to be read or written.  Reading/writing
        will terminate when one of the given values has been exceeded.
        Any extraneous data is simply discarded.
        """
        super(Head,self).__init__(fileobj,mode)
        self._maxBytes = bytes
        self._maxLines = lines
        self._bytesR = 0
        self._linesR = 0
        self._bytesW = 0
        self._linesW = 0
        self._finishedR = False
        self._finishedW = False
    
    def _read(self,sizehint=-1):
        if self._finishedR:
            return None
        if sizehint <= 0 or sizehint > self._bufsize:
            sizehint = self._bufsize
        data = self._fileobj.read(sizehint)
        if data == "":
            self._finishedR = True
            return data
        nBytes = len(data)
        newBytes = self._bytesR + nBytes
        if self._maxBytes is not None and newBytes >= self._maxBytes:
            data = data[:self._maxBytes - self._bytesR]
            self._finishedR = True
        nLines = data.count("\n")
        newLines = self._linesR + nLines
        if self._maxLines is not None and newLines >= self._maxLines:
            limit = self._maxLines - self._linesR
            lines = data.split("\n")
            if len(lines) > limit:
                data = "\n".join(lines[:limit]) + "\n"
            else:
                data = "\n".join(lines[:limit])
            self._finishedR = True
        self._bytesR = newBytes
        self._linesR = newLines
        return data

    def _write(self,data,flushing=True):
        if self._finishedW:
            return None
        nBytes = len(data)
        nLines = data.count("\n")
        newBytes = self._bytesW + nBytes
        newLines = self._linesW + nLines
        if self._maxBytes is not None and newBytes >= self._maxBytes:
            data = data[:self._maxBytes - self._bytesW]
            self._finishedW = True
        elif self._maxLines is not None and newLines >= self._maxLines:
            limit = self._maxLines - self._linesW
            lines = data.split("\n")
            if len(lines) > limit:
                data = "\n".join(lines[:limit]) + "\n"
            else:
                data = "\n".join(lines[:limit])
            self._finishedW = True
        self._bytesW = newBytes
        self._linesW = newLines
        self._fileobj.write(data)
        return None


class Test_Head(unittest.TestCase):
    """Testcases for the Head wrapper class."""
    
    def setUp(self):
        self.intext = "Guido van Rossum\n is a space\n alien."
        self.infile = StringIO(self.intext)
        self.outfile = StringIO()

    def tearDown(self):
        pass

    def test_ReadHeadBytes(self):
        """Test reading bytes from head of a file."""
        hf = Head(self.infile,"r",bytes=10)
        txt = hf.read()
        self.assertEquals(len(txt),10)
        self.assertEquals(txt,self.intext[:10])
    
    def test_ReadHeadLongBytes(self):
        """Test reading entirety of head of file."""
        hf = Head(self.infile,"r",bytes=1000)
        txt = hf.read()
        self.assertEquals(txt,self.intext)
    
    def test_ReadHeadLines(self):
        """Test reading lines from head of file."""
        hf = Head(self.infile,"r",lines=2)
        txt = hf.read()
        self.assertEquals(txt.count("\n"),2)
        self.assertEquals(txt,"\n".join(self.intext.split("\n")[:2])+"\n")

    def test_ReadHeadLinesExact(self):
        """Test reading exact number of lines from head of file."""
        hf = Head(self.infile,"r",lines=3)
        txt = hf.read()
        self.assertEquals(txt.count("\n"),2)
        self.assertEquals(txt,self.intext)

    def test_ReadHeadLongLines(self):
        """Test reading all lines from head of file."""
        hf = Head(self.infile,"r",lines=200)
        txt = hf.read()
        self.assertEquals(txt,self.intext)
        
    def test_ReadBytesOverLines(self):
        """Test reading limited by bytes, not lines"""
        hf = Head(self.infile,"r",bytes=5,lines=2)
        txt = hf.read()
        self.assertEquals(len(txt),5)
        self.assertEquals(txt,self.intext[:5])
        
    def test_ReadLinesOverBytes(self):
        """Test reading limited by lines, not bytes"""
        hf = Head(self.infile,"r",bytes=500,lines=1)
        txt = hf.read()
        self.assertEquals(txt.count("\n"),1)
        self.assertEquals(txt,self.intext.split("\n")[0]+"\n")

    def test_WriteHeadBytes(self):
        """Test writing bytes to head of a file."""
        hf = Head(self.outfile,"w",bytes=10)
        hf.write(self.intext)
        self.assertEquals(len(self.outfile.getvalue()),10)
        self.assertEquals(self.outfile.getvalue(),self.intext[:10])
    
    def test_WriteHeadLongBytes(self):
        """Test writing entirety of head of file."""
        hf = Head(self.outfile,"w",bytes=1000)
        hf.write(self.intext)
        self.assertEquals(self.outfile.getvalue(),self.intext)
    
    def test_WriteHeadLines(self):
        """Test writing lines to head of file."""
        hf = Head(self.outfile,"w",lines=2)
        hf.write(self.intext)
        self.assertEquals(self.outfile.getvalue().count("\n"),2)
        self.assertEquals(self.outfile.getvalue(),"\n".join(self.intext.split("\n")[:2])+"\n")

    def test_WriteHeadLongLines(self):
        """Test writing all lines to head of file."""
        hf = Head(self.outfile,"w",lines=200)
        hf.write(self.intext)
        self.assertEquals(self.outfile.getvalue(),self.intext)
        
    def test_WriteBytesOverLines(self):
        """Test writing limited by bytes, not lines"""
        hf = Head(self.outfile,"w",bytes=5,lines=2)
        hf.write(self.intext)
        txt = self.outfile.getvalue()
        self.assertEquals(len(txt),5)
        self.assertEquals(txt,self.intext[:5])
        
    def test_writeLinesOverBytes(self):
        """Test writing limited by lines, not bytes"""
        hf = Head(self.outfile,"w",bytes=500,lines=1)
        hf.write(self.intext)
        txt = self.outfile.getvalue()
        self.assertEquals(txt.count("\n"),1)
        self.assertEquals(txt,self.intext.split("\n")[0]+"\n")


def testsuite():
    suite = unittest.TestSuite()
    from filelike.wrappers import unix
    suite.addTest(unittest.makeSuite(Test_Head))
    return suite

