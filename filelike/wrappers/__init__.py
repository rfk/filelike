# filelike/wrappers/__init__.py
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

    filelike.wrappers:  wrapper classes modifying file-like objects
    
This module builds on the basic functionality of the filelike module to
provide a collection of useful classes.  These include:
    
    * Translate:  pass file contents through an arbitrary translation
                  function (e.g. compression, encryption, ...)
                  
    * Decrypt:    on-the-fly reading and writing to an encrypted file
                  (using PEP272 cipher API)

    * UnBZip2:    on-the-fly decompression of bzip'd files
                  (like the standard library's bz2 module, but accepts
                  any file-like object)
 
As an example of the type of thing this module is designed to achieve, here's
how to use the Decrypt wrapper to transparently access an encrypted file:
    
    # Create the decryption key
    from Crypto.Cipher import DES
    cipher = DES.new('abcdefgh',DES.MODE_ECB)
    # Open the encrypted file
    f = Decrypt(file("some_encrypted_file.bin","r"),cipher)
    
The object in 'f' now behaves as a file-like object, transparently decrypting
the file on-the-fly as it is read.

""" 

import filelike
from filelike import FileLikeBase

import os
import unittest
from StringIO import StringIO
import warnings
import tempfile


def _deprecate(oldName,newClass):
    """Mark an old class name as deprecated."""
    class Deprecated(newClass):
        def __init__(self,*args,**kwds):
            msg = oldName + " is deprecated, please use " + newClass.__name__
            warnings.warn(msg,category=DeprecationWarning)
            newClass.__init__(self,*args,**kwds)
    globals()[oldName] = Deprecated


class FileWrapper(FileLikeBase):
    """Base class for objects that wrap a file-like object.
    
    This class provides basic functionality for implementing file-like
    objects that wrap another file-like object to alter its functionality
    in some way.  It takes care of house-keeping duties such as flushing
    and closing the wrapped file.

    Access to the wrapped file is given by the private member _fileobj.
    By convention, the subclass's constructor should accept this as its
    first argument and pass it to its superclass's constructor in the
    same position.
    
    This class provides a basic implementation of _read() and _write()
    which just calls read() and write() on the wrapped object.  Subclasses
    will probably want to override these.
    """
    
    def __init__(self,fileobj,mode=None):
        """FileWrapper constructor.
        
        'fileobj' must be a file-like object, which is to be wrapped
        in another file-like object to provide additional functionality.
        
        If given, 'mode' must be the access mode string under which
        the wrapped file is to be accessed.  If not given or None, it
        is looked up on the wrapped file if possible.  Otherwise, it
        is not set on the object.
        """
        super(FileWrapper,self).__init__()
        self._fileobj = fileobj
        if mode is None:
            if hasattr(fileobj,"mode"):
                self.mode = fileobj.mode
        else:
            self.mode = mode
        # Copy useful attributes of the fileobj
        if hasattr(fileobj,"name"):
            self.name = fileobj.name
        
    def close(self):
        """Close the object for reading/writing."""
        super(FileWrapper,self).close()
        if hasattr(self._fileobj,"close"):
            self._fileobj.close()

    def flush(self):
        """Flush the write buffers of the file."""
        super(FileWrapper,self).flush()
        if hasattr(self._fileobj,"flush"):
            self._fileobj.flush()
    
    def _read(self,sizehint=-1):
        data = self._fileobj.read(sizehint)
        if data == "":
            return None
        return data

    def _write(self,string,flushing=False):
        return self._fileobj.write(string)

    def _seek(self,offset,whence):
        self._fileobj.seek(offset,whence)

    def _tell(self):
        return self._fileobj.tell()

##  Import the various classes from our sub-modules,
##  and mark old names as deprecated.

from filelike.wrappers.translate import Translate, BytewiseTranslate
_deprecate("TransFile",Translate)

from filelike.wrappers.fixedblocksize import FixedBlockSize
_deprecate("FixedBlockSizeFile",FixedBlockSize)

from filelike.wrappers.padtoblocksize import PadToBlockSize, UnPadToBlockSize
_deprecate("PaddedToBlockSizeFile",UnPadToBlockSize)

from filelike.wrappers.crypto import Encrypt, Decrypt
_deprecate("DecryptFile",Decrypt)
_deprecate("EncryptFile",Encrypt)

from filelike.wrappers.buffered import Buffered

from filelike.wrappers.compress import BZip2, UnBZip2
_deprecate("BZ2File",UnBZip2)

from filelike.wrappers.unix import Head

from filelike.wrappers.slice import Slice


##  test cases


class Test_FileWrapper(filelike.Test_ReadWriteSeek):
    """Testcases for FileWrapper base class."""
    
    def makeFile(self,contents,mode):
        return FileWrapper(StringIO(contents),mode)


class Test_OpenerDecoders(unittest.TestCase):
    """Testcases for the filelike.Opener decoder functions."""
    
    def setUp(self):
        import tempfile
        handle, self.tfilename = tempfile.mkstemp()
        self.tfile = os.fdopen(handle,"w+b")

    def tearDown(self):
        os.unlink(self.tfilename)

    def test_LocalFile(self):
        """Test opening a simple local file."""
        self.tfile.write("contents")
        self.tfile.flush()
        f = filelike.open(self.tfilename,"r")
        self.assertEquals(f.name,self.tfilename)
        self.assertEquals(f.read(),"contents")
    
    def test_RemoteBzFile(self):
        """Test opening a remote BZ2 file."""
        f = filelike.open("http://www.rfk.id.au/static/test.txt.bz2")
        self.assertEquals(f.read(),"contents goes here if you please.\n\n")


def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_FileWrapper))
    suite.addTest(unittest.makeSuite(Test_OpenerDecoders))
    from filelike.wrappers import translate
    suite.addTest(translate.testsuite())
    from filelike.wrappers import fixedblocksize
    suite.addTest(fixedblocksize.testsuite())
    from filelike.wrappers import padtoblocksize
    suite.addTest(padtoblocksize.testsuite())
    from filelike.wrappers import crypto
    suite.addTest(crypto.testsuite())
    from filelike.wrappers import buffered
    suite.addTest(buffered.testsuite())
    from filelike.wrappers import compress
    suite.addTest(compress.testsuite())
    from filelike.wrappers import unix
    suite.addTest(unix.testsuite())
    from filelike.wrappers import slice
    suite.addTest(slice.testsuite())
    return suite

