# filelike/wrappers/compress.py
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

    filelike.wrappers.compress:  wrapper classes handling compressed files
    
This module provides the filelike wrappers 'BZip2' and 'UnBZip2' for dealing
with files compressed in bz2 format.  It also provides some base classes for
each building other compression wrappers.

""" 

import filelike
from filelike.wrappers import FileWrapper
from filelike.wrappers.translate import Translate
from filelike.wrappers.translate import ReadStreamTranslate
from filelike.wrappers.translate import WriteStreamTranslate
from filelike.wrappers.buffered import Buffered

import unittest
from StringIO import StringIO

import bz2

class Decompress(FileWrapper):
    """Abstract base class for decompressing files.

    Instances of this class represent the decompressed version of a file - 
    all data read from the file is decompressed on demand, and all data
    written to the file is compressed.

    Subclases must provide compressor_factory() and decompressor_factory()
    methods.
    """

    def __init__(self,fileobj,mode=None):
        if mode is None:
            try:
                mode = fileobj.mode
            except AtributeError:
                mode = "r"
        myFileObj = None
        if "r" in mode:
            if "w" not in mode and "a" not in mode and "+" not in mode:
                # Nice and easy, just a streaming decompress on read
                myFileObj = ReadStreamTranslate(fileobj,mode=mode,
                                    func_factory=self.decompressor_factory)
        else:
            if "-" in mode:
                # Nice and easy, just a streaming compress on write
                myFileObj = WriteStreamTranslate(fileobj,mode=mode,
                                    func_factory=self.compressor_factory)
        if not myFileObj:
            # Rats, writing + seekabilty == inefficient.
            # Operate using a buffer file.
            ins = Translate(fileobj,mode="r",rfunc=self.decompressor_factory())
            out = Translate(fileobj,mode="w",wfunc=self.compressor_factory())
            def onclose():
                ins._fileobj = None
                fileobj.seek(0,0)
            myFileObj = Buffered(fileobj=None,mode=mode,instream=ins,
                                 outstream=out,onclose=onclose)
        super(Decompress,self).__init__(myFileObj,mode=mode)


class Compress(FileWrapper):
    """Abstract base class for compressing files.

    Instances of this class represent the compressed version of a file - 
    all data read from the file is compressed on demand, and all data
    written to the file is decompressed.

    Subclases must provide compressor_factory() and decompressor_factory()
    methods.
    """

    def __init__(self,fileobj,mode=None):
        if mode is None:
            try:
                mode = fileobj.mode
            except AtributeError:
                mode = "r"
        myFileObj = None
        if "r" in mode:
            if "w" not in mode and "a" not in mode and "+" not in mode:
                # Nice and easy, just a streaming compress on read
                myFileObj = ReadStreamTranslate(fileobj,mode=mode,
                                    func_factory=self.compressor_factory)
        else:
            if "-" in mode:
                # Nice and easy, just a streaming decompress on write
                myFileObj = WriteStreamTranslate(fileobj,mode=mode,
                                    func_factory=self.decompressor_factory)
        if not myFileObj:
            # Rats, writing + seekabilty == inefficient
            ins = Translate(fileobj,mode="r",rfunc=self.compressor_factory())
            out = Translate(fileobj,mode="w",wfunc=self.decompressor_factory())
            def onclose():
                ins._fileobj = None
                fileobj.seek(0,0)
            myFileObj = Buffered(mode=mode,instream=ins,outstream=out,onclose=onclose)
        super(Compress,self).__init__(myFileObj,mode=mode)


class BZip2Mixin(object):
    """Mixin for Compress/Decompress subclasses using Bzip2."""

    def __init__(self,*args,**kwds):
        if not hasattr(self,"compresslevel"):
            self.compresslevel = 9
        super(BZip2Mixin,self).__init__(*args,**kwds)

    def compressor_factory(self):
        c = bz2.BZ2Compressor(self.compresslevel)
        def compress(data):
            return c.compress(data)
        compress.flush = c.flush
        return compress

    def decompressor_factory(self):
        d = bz2.BZ2Decompressor()
        def decompress(data):
            if data == "":
                return ""
            return d.decompress(data)
        return decompress


class UnBZip2(BZip2Mixin,Decompress):
    """Class for reading and writing to a un-bziped file.
        
    This class behaves almost exactly like the bz2.BZ2File class from
    the standard library, except that it accepts an arbitrary file-like
    object.  All reads from the file are decompressed, all writes are
    compressed.
    """
    
    def __init__(self,fileobj,mode=None,compresslevel=9):
        self.compresslevel = compresslevel
        super(UnBZip2,self).__init__(fileobj,mode=mode)


class BZip2(BZip2Mixin,Compress):
    """Class for reading and writing a bziped file.
        
    This class is the dual of UnBZip2 - it compresses read data, and
    decompresses written data.  Thus BZip2(f) is the compressed version
    of f.
    """
    
    def __init__(self,fileobj,mode=None,compresslevel=9):
        self.compresslevel = compresslevel
        super(BZip2,self).__init__(fileobj,mode=mode)


##  Add handling of .bz2 files to filelike.open()
def _BZip2_decoder(fileobj):
    """Decoder function for handling .bz2 files with filelike.open"""
    if not fileobj.name.endswith(".bz2"):
        return None
    f = UnBZip2(fileobj)
    f.name = fileobj.name[:-4]
    return f
filelike.open.decoders.append(_BZip2_decoder)
    

class Test_BZip2(filelike.Test_ReadWriteSeek):
    """Tetcases for BZip2 wrapper class."""

    contents = bz2.compress("This is my compressed\n test data")

    def makeFile(self,contents,mode):
        return BZip2(StringIO(bz2.decompress(contents)),mode)

    #  We cant just write text into a BZip stream, so we have
    #  to adjust these tests

    def test_write_read(self):
        self.file.write(self.contents[0:5])
        c = self.file.read()
        self.assertEquals(c,self.contents[5:])

    def test_read_write_read(self):
        c = self.file.read(5)
        self.assertEquals(c,self.contents[:5])
        self.file.write(self.contents[5:10])
        c = self.file.read(5)
        self.assertEquals(c,self.contents[10:15])

    def test_read_write_seek(self):
        c = self.file.read(5)
        self.assertEquals(c,self.contents[:5])
        self.file.write(self.contents[5:10])
        self.file.seek(0)
        c = self.file.read(10)
        self.assertEquals(c,self.contents[:10])

    def test_read_empty_file(self):
        f = self.makeFile("","r")
        self.assertEquals(f.read(),bz2.compress(""))


class Test_UnBZip2(filelike.Test_ReadWriteSeek):
    """Tetcases for UnBZip2 wrapper class."""

    contents = "This is my uncompressed\n test data"

    def makeFile(self,contents,mode):
        return UnBZip2(StringIO(bz2.compress(contents)),mode)


def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_BZip2))
    suite.addTest(unittest.makeSuite(Test_UnBZip2))
    return suite

