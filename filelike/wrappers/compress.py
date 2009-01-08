# filelike/wrappers/compress.py
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

    filelike.wrappers.compress:  wrapper classes handling compressed files
    
This module provides the filelike wrappers 'BZip2' and 'UnBZip2' for dealing
with files compressed in bz2 format.  It also provides some base classes for
each building other compression wrappers.

""" 

import filelike
from filelike.wrappers import FileWrapper
from filelike.wrappers.translate import Translate

import unittest
from StringIO import StringIO

import bz2


class Compress(Translate):
    """Abstract base class for compressing files.

    Instances of this class represent the compressed version of a file - 
    all data read from the file is compressed on demand, and all data
    written to the file is uncompressed.

    Subclasses need to provide the 'compress' and 'decompress' methods.
    """

    def __init__(self,fileobj,mode=None):
        super(Compress,self).__init__(fileobj,mode=mode,
                                       rfunc=self.compress,
                                       wfunc=self.decompress)


class Decompress(Translate):
    """Abstract base class for decompressing files.

    Instances of this class represent the decompressed version of a file - 
    all data read from the file is decompressed on demand, and all data
    written to the file is compressed.

    Subclasses need to provide the 'compress' and 'decompress' methods.
    """

    def __init__(self,fileobj,mode=None):
        super(Decompress,self).__init__(fileobj,mode=mode,
                                       rfunc=self.decompress,
                                       wfunc=self.compress)


class CompressMixin(object):

    def __init__(self,*args,**kwds):
        def compress(data):
            return self._compress(data)
        def c_flush():
            return self._flush_compress()
        compress.flush = c_flush
        self.compress = compress
        def decompress(data):
            return self._decompress(data)
        def d_flush():
            return self._flush_decompress()
        decompress.flush = c_flush
        self.decompress = decompress
        super(CompressMixin,self).__init__(*args,**kwds)

    def _compress(self,data):
        raise NotImplementedError

    def _flush_compress(self):
        return ""

    def _decompress(self,data):
        raise NotImplementedError

    def _flush_decompress(self):
        return ""


class BZip2Mixin(CompressMixin):
    """Mixin for Compress/UnCompress subclasses using Bzip2."""

    def __init__(self,*args,**kwds):
        try:
            cl = self.compresslevel
        except AttributeError:
            cl = None
        self._compressor = bz2.BZ2Compressor(cl)
        self._decompressor = bz2.BZ2Decompressor()
        super(BZip2Mixin,self).__init__(*args,**kwds)

    def _compress(self,data):
        return self._compressor.compress(data)

    def _flush_compress(self):
        return self._compressor.flush()

    def _decompress(self,data):
        return self._decompressor.decompress(data)


class BZip2(BZip2Mixin,Compress):
    """Class for reading and writing a bziped file.
        
    This class is the dual of UnBZip2 - it compresses read data, and
    decompresses written data.  Thus BZip2(f) is the compressed version
    of f.
    """
    
    def __init__(self,fileobj,mode=None,compresslevel=9):
        self.compresslevel = compresslevel
        super(BZip2,self).__init__(fileobj,mode=None)


class UnBZip2(BZip2Mixin,Decompress):
    """Class for reading and writing to a un-bziped file.
        
    This class behaves almost exactly like the bz2.BZ2File class from
    the standard library, except that it accepts an arbitrary file-like
    object.  All reads from the file are decompressed, all writes are
    compressed.
    """
    
    def __init__(self,fileobj,mode=None,compresslevel=9):
        self.compresslevel = compresslevel
        super(UnBZip2,self).__init__(fileobj,mode=None)
    

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


class Test_UnBZip2(filelike.Test_ReadWriteSeek):
    """Tetcases for UnBZip2 wrapper class."""

    contents = "This is my uncompressed\n test data"

    def makeFile(self,contents,mode):
        return BZip2(StringIO(bz2.compress(contents)),mode)


def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_BZip2))
    suite.addTest(unittest.makeSuite(Test_UnBZip2))
    return suite

