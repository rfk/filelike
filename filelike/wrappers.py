# filelike/wrappers.py
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

    filelike.wrappers:  wrapper classes modifying file-like objects
    
This module builds on the basic functionality of the filelike module to
provide a collection of useful classes.  These include:
    
    * Translate:  pass file contents through an arbitrary translation
                  function (e.g. compression, encryption, ...)
                  
    * Decrypt:    on-the-fly reading and writing to an encrypted file
                  (using PEP272 cipher API)

    * Cat:  concatenate several files into a single file-like object

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
        FileLikeBase.__init__(self)
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
        FileLikeBase.close(self)
        if hasattr(self._fileobj,"close"):
            self._fileobj.close()

    def flush(self):
        """Flush the write buffers of the file."""
        FileLikeBase.flush(self)
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


class Test_FileWrapper(filelike.Test_ReadWriteSeek):
    """Testcases for FileWrapper base class."""
    
    def makeFile(self,contents,mode):
        return FileWrapper(StringIO(contents),mode)


##############


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
        FileWrapper.__init__(self,fileobj,mode)
        if func is not None:
            if rfunc is not None:
                raise ValueError("Cannot specify both <func> and <rfunc>")
            if wfunc is not None:
                raise ValueError("Cannot specify both <func> and <wfunc>")
            self._rfunc = func
            self._wfunc = func
        else:
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
        FileWrapper.flush(self)

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


_deprecate("TransFile",Translate)


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
    

#############


class FixedBlockSize(FileWrapper):
    """Class reading/writing to files at a fixed block size.
    
    This file wrapper can be used to read or write to a file-like
    object at a specific block size.  All reads request strings
    whose length is a multiple of the block size, and all writes
    pass on strings of a similar nature.  This could be useful, for
    example, to write data to a cipher function without manually 
    chunking text to match the cipher's block size.
    
    If the total data written to the file when it is closed is not
    a multiple of the blocksize, it will be padded to the appropriate
    size with null bytes.
    """
    
    def __init__(self,fileobj,blocksize,mode=None):
        FileWrapper.__init__(self,fileobj,mode)
        self.blocksize = blocksize
    
    def _round_up(self,num):
        """Round <num> up to a multiple of the block size."""
        return ((num/self.blocksize)+1) * self.blocksize
    
    def _round_down(self,num):
        """Round <num> down to a multiple of the block size."""
        return (num/self.blocksize) * self.blocksize

    def _read(self,sizehint=-1):
        """Read approximately <sizehint> bytes from the file."""
        if sizehint <= 0:
            sizehint = self._bufsize
        size = self._round_up(sizehint)
        data = self._fileobj.read(size)
        if data == "":
            return None
        return data

    def _write(self,data,flushing=False):
        """Write the given string to the file.

        When flushing data to the file, it may need to be padded to the
        block size.  First we attempt to read additional data from the
        underlying file to use for the padding, but if this fails then
        we pad with null bytes.
        """
        size = self._round_down(len(data))
        self._fileobj.write(data[:size])
        if not flushing:
            return data[size:]
        # Flushing, so we need to pad the data.
        # Try to find existing contents, use null bytes otherwise
        try:
            nextBlock = self._fileobj.read(self.blocksize)
        except IOError:
            nextBlock = "\0" * self.blocksize
        else:
            lenNB = len(nextBlock)
            if lenNB < self.blocksize:
                nextBlock = nextBlock + "\0"*(self.blocksize-lenNB)
        padstart = len(data) - size
        self._fileobj.write(data[size:] + nextBlock[padstart:])
        return ""

    def _seek(self,offset,whence):
        """Absolute seek, repecting block boundaries.

        This method performs an absolute file seek to the block boundary
        closest to (but not exceeding) the specified offset.
        """
        if whence != 0:
            raise NotImplementedError
        boundary = self._round_down(offset)
        print "SEEK:", offset, boundary
        self._fileobj.seek(boundary,0)
        if boundary == offset:
            return ""
        else:
            data = self._fileobj.read(self.blocksize)
            diff = offset - boundary - len(data)
            if diff > 0:
                # Seeked past end of file.  Actually do this on fileobj, so
                # that it will raise an error if appropriate.  If it doesn't
                # then we'll pad with null bytes.
                self._fileobj.seek(diff,1)
                self._fileobj.seek(-1*diff,1)
                data = data + "\0"*diff
            else:
                self._fileobj.seek(-1*self.blocksize,1)
            print "SBUF:", data[:(offset-boundary)]
            return data[:(offset-boundary)]
 

_deprecate("FixedBlockSizeFile",FixedBlockSize)


class Test_FixedBlockSize5(filelike.Test_ReadWriteSeek):
    """Testcases for the FixedBlockSize class, with blocksize 5."""

    blocksize = 5
    
    def makeFile(self,contents,mode):
        f = StringIO(contents)
        f.seek(0)
        class BSFile:
            """Simulate reads/writes, asserting correct blocksize."""
            def read(s,size=-1):
                self.assert_(size > 0)
                self.assert_(size % self.blocksize == 0)
                return f.read(size)
            def write(s,data):
                self.assert_(len(data)%self.blocksize == 0)
                f.write(data)
            def seek(s,offset,whence):
                f.seek(offset,whence)
            def tell(s):
                return f.tell()
            def flush(self):
                f.flush()
        return FixedBlockSize(BSFile(),self.blocksize)


class Test_FixedBlockSize7(Test_FixedBlockSize5):
    """Testcases for the FixedBlockSize class, with blocksize 7."""
    blocksize = 7


class Test_FixedBlockSize24(Test_FixedBlockSize5):
    """Testcases for the FixedBlockSize class, with blocksize 24."""
    blocksize = 24


#############


class PadToBlockSize(FileWrapper):
    """Class padding files to a fixed block size.
    
    This file wrapper can be used to pad a file to a specific block size.
    The file data is followed by a 'Z', then as many 'X' bytes as needed
    to meet the block size.  This is automatically added when reading,
    and stripped when writing.  The dual of this class is UnPadToBlockSize.

    No guarantee is made that reads or writes are requested at the
    blocksize - use FixedBlockSize to achieve this.
    """

    def __init__(self,fileobj,blocksize,mode=None):
        FileWrapper.__init__(self,fileobj,mode)
        self.blocksize = blocksize
        self._padread = False
    
    def _round_up(self,num):
        """Round <num> up to a multiple of the block size."""
        nm = ((num/self.blocksize)+1) * self.blocksize
        if nm == num + self.blocksize:
            return num
        return nm
    
    def _round_down(self,num):
        """Round <num> down to a multiple of the block size."""
        return (num/self.blocksize) * self.blocksize
    
    def _pad_to_size(self,data):
        """Pad data to make it an appropriate size."""
        data = data + "Z"
        size = self._round_up(len(data))
        if len(data) < size:
            data = data + ("X"*(size-len(data)))
        return data

    def _read(self,sizehint=-1):
        if self._padread:
            return None
        data = self._fileobj.read(sizehint)
        if sizehint <= 0 or len(data) < sizehint:
            data = self._pad_to_size(data)
            self._padread = True
        if data == "":
          return None
        return data

    def _write(self,string,flushing=False):
        idx = string.rfind("Z")
        if idx < 0 or idx < (len(string) - self.blocksize):
            if flushing:
                raise ValueError("PadToBlockSize: no padding found in file.")
            self._fileobj.write(string)
            return None
        s2 = string[:idx]
        self._fileobj.write(s2)
        if flushing:
            return None
        return string[idx:]
        

class UnPadToBlockSize(FileWrapper):
    """Class removing block-size padding from a file.
    
    This file wrapper can be used to reverse the effects of PadToBlockSize,
    removing extraneous padding data when reading, and adding it back in
    when writing.
    """
    
    def __init__(self,fileobj,blocksize,mode=None):
        FileWrapper.__init__(self,fileobj,mode)
        self.blocksize = blocksize
        self._padwritten = False
        self._padread = False
    
    def _round_up(self,num):
        """Round <num> up to a multiple of the block size."""
        nm = ((num/self.blocksize)+1) * self.blocksize
        if nm == num + self.blocksize:
            return num
        return nm
    
    def _round_down(self,num):
        """Round <num> down to a multiple of the block size."""
        return (num/self.blocksize) * self.blocksize
    
    def _pad_to_size(self,data):
        """Pad data to make it an appropriate size."""
        data = data + "Z"
        size = self._round_up(len(data))
        if len(data) < size:
            data = data + ("X"*(size-len(data)))
        return data
    
    def _read(self,sizehint=-1):
        """Read approximately <sizehint> bytes from the file."""
        if self._padread:
            return None
        data = self._fileobj.read(sizehint)
        # If we might be near the end, read far enough ahead to find the pad
        idx = data.rfind("Z")
        while idx >= 0 and idx >= (len(data) - self.blocksize):
            newData = self._fileobj.read(self.blocksize)
            data = data + newData
            idx = data.rfind("Z")
            if newData == "":
                break
        if data == "":
            raise ValueError("UnPadToBlockSize: no padding found in file.")
        if idx < 0 or idx < (len(data) - self.blocksize):
            return data
        data = data[:idx]
        self._padread = True
        if data == "":
            data = None
        return data

    def _write(self,data,flushing=False):
        """Write the given string to the file."""
        # Writing at the block size means we dont have to count bytes written.
        # Pad the data if the buffers are being flushed.
        if flushing:
            if self._padwritten:
                size = 0
                data = ""
            else:
                data = self._pad_to_size(data)
                size = len(data)
                self._padwritten = True
        else:
            size = self._round_down(len(data))
        self._fileobj.write(data[:size])
        return data[size:]

    def flush(self):
        FileWrapper.flush(self)
        if not self._padwritten:
          if self._check_mode('w'):
            self._write("",flushing=True)


_deprecate("PaddedToBlockSizeFile",UnPadToBlockSize)


class Test_PadToBlockSize(unittest.TestCase):
    """Testcases for the [Un]PadToBlockSize class."""
    
    def setUp(self):
        self.textin = "Zhis is sample text"
        self.textout5 = "Zhis is sample textZ"
        self.textout7 = "Zhis is sample textZX"
        self.outfile = StringIO()
    
    def tearDown(self):
        del self.outfile

    def test_write5(self):
        """Test writing at blocksize=5"""
        bsf = UnPadToBlockSize(self.outfile,5,mode="w")
        bsf.write(self.textin)
        bsf.flush()
        self.assertEquals(self.outfile.getvalue(),self.textout5)
        self.outfile = StringIO()
        bsf = PadToBlockSize(self.outfile,5,mode="w")
        bsf.write(self.textout5)
        bsf.flush()
        self.assertEquals(self.outfile.getvalue(),self.textin)

    def test_write7(self):
        """Test writing at blocksize=7"""
        bsf = UnPadToBlockSize(self.outfile,7,mode="w")
        bsf.write(self.textin)
        bsf.flush()
        self.assertEquals(self.outfile.getvalue(),self.textout7)
        self.outfile = StringIO()
        bsf = PadToBlockSize(self.outfile,7,mode="w")
        bsf.write(self.textout7)
        bsf.flush()
        self.assertEquals(self.outfile.getvalue(),self.textin)

    def test_writeLen(self):
        """Test writing at blocksize=len"""
        bsf = UnPadToBlockSize(self.outfile,len(self.textin),mode="w")
        bsf.write(self.textin)
        bsf.flush()
        self.assertEquals(self.outfile.getvalue(),self.textin+"Z"+"X"*(len(self.textin)-1))
        self.outfile = StringIO()
        bsf = PadToBlockSize(self.outfile,len(self.textin),mode="w")
        bsf.write(self.textin+"Z"+"X"*(len(self.textin)-1))
        bsf.flush()
        self.assertEquals(self.outfile.getvalue(),self.textin)
    
    def test_read5(self):
        """Test reading at blocksize=5"""
        inf = StringIO(self.textout5)
        bsf = UnPadToBlockSize(inf,5,mode="r")
        txt = bsf.read()
        self.assertEquals(txt,self.textin)

        inf = StringIO(self.textout5)
        bsf = UnPadToBlockSize(inf,5,mode="r")
        self.assertEquals(bsf.read(1),self.textin[0])
        self.assertEquals(bsf.read(1),self.textin[1])

        inf = StringIO(self.textin)
        bsf = PadToBlockSize(inf,5,mode="r")
        txt = bsf.read()
        self.assertEquals(txt,self.textout5)

        inf = StringIO(self.textin)
        bsf = PadToBlockSize(inf,5,mode="r")
        self.assertEquals(bsf.read(1),self.textout5[0])
        self.assertEquals(bsf.read(1),self.textout5[1])

    def test_read7(self):
        """Test reading at blocksize=7"""
        inf = StringIO(self.textout7)
        bsf = UnPadToBlockSize(inf,7,mode="r")
        txt = bsf.read()
        self.assertEquals(txt,self.textin)

        inf = StringIO(self.textout7)
        bsf = UnPadToBlockSize(inf,7,mode="r")
        self.assertEquals(bsf.read(1),self.textin[0])
        self.assertEquals(bsf.read(1),self.textin[1])

        inf = StringIO(self.textin)
        bsf = PadToBlockSize(inf,7,mode="r")
        txt = bsf.read()
        self.assertEquals(txt,self.textout7)

        inf = StringIO(self.textin)
        bsf = PadToBlockSize(inf,7,mode="r")
        self.assertEquals(bsf.read(1),self.textout7[0])
        self.assertEquals(bsf.read(1),self.textout7[1])
        
        
    def test_readLen(self):
        """Test reading at blocksize=len"""
        inf = StringIO(self.textin+"Z"+"X"*(len(self.textin)-1))
        bsf = UnPadToBlockSize(inf,len(self.textin),mode="r")
        txt = bsf.read()
        self.assertEquals(txt,self.textin)

        inf = StringIO(self.textin)
        bsf = PadToBlockSize(inf,len(self.textin),mode="r")
        txt = bsf.read()
        self.assertEquals(txt,self.textin+"Z"+"X"*(len(self.textin)-1))


    def test_EmptyFile(self):
        """Test PadToBlockSize with empty files."""
        inf = StringIO("")
        pad = PadToBlockSize(inf,8,mode="r")
        self.assertEquals("".join(pad),"ZXXXXXXX")
        inf = StringIO("ZXXXXXXX")
        unpad = UnPadToBlockSize(inf,8,mode="r")
        self.assertEquals("".join(unpad),"")


#############


class Decrypt(FileWrapper):
    """Class for reading and writing to an encrypted file.
    
    This class accesses an encrypted file using a ciphering object
    compliant with PEP272: "API for Block Encryption Algorithms".
    All reads from the file are automatically decrypted, while writes
    to the file and automatically encrypted.  Thus, Decrypt(fobj)
    can be seen as the decrypted version of the file-like object fobj.
    
    Because this class is implemented on top of FixedBlockSize,
    the plaintext may be padded with null characters to reach a multiple
    of the block size.  If this is not desired, wrap it in PadToBlockSize.
    
    There is a dual class, Encrypt, where all reads are encrypted
    and all writes are decrypted.  This would be used, for example, to
    encrypt the contents of an existing file using a series of read()
    operations.
    """

    def __init__(self,fileobj,cipher,mode=None):
        """Decrypt Constructor.

        'fileobj' is the file object with encrypted contents, and 'cipher'
        is the cipher object to be used.  Other arguments are passed through
        to FileWrapper.__init__
        """
        self._cipher = cipher
        myFileObj = Translate(fileobj,mode=mode,
                                      rfunc=cipher.decrypt,
                                      wfunc=cipher.encrypt)
        myFileObj = FixedBlockSize(myFileObj,cipher.block_size)
        FileWrapper.__init__(self,myFileObj)
        
    def setCipher(self,cipher):
        """Change the cipher after object initialization."""
        self._cipher = cipher
        self._rfunc = cipher.decrypt
        self._wfunc = cipher.encrypt

_deprecate("DecryptFile",Decrypt)

class Encrypt(FileWrapper):
    """Class for reading and writing to an decrypted file.
    
    This class accesses a decrypted file using a ciphering object
    compliant with PEP272: "API for Block Encryption Algorithms".
    All reads from the file are automatically encrypted, while writes
    to the file are automatically decrypted.  Thus, Encrypt(fobj)
    can be seen as the encrypted version of the file-like object fobj.

    Because this class is implemented on top of FixedBlockSize,
    the plaintext may be padded with null characters to reach a multiple
    of the block size.  If this is not desired, wrap it in PadToBlockSize.
    
    There is a dual class, Decrypt, where all reads are decrypted
    and all writes are encrypted.  This would be used, for example, to
    decrypt the contents of an existing file using a series of read()
    operations.
    """

    def __init__(self,fileobj,cipher,mode=None):
        """Encrypt Constructor.
        <fileobj> is the file object with decrypted contents, and <cipher>
        is the cipher object to be used.  Other arguments are passed through
        to FileWrapper.__init__
        """
        self.__cipher = cipher
        myFileObj = Translate(fileobj,mode=mode,
                                      rfunc=self.__encrypt,
                                      wfunc=cipher.decrypt)
        myFileObj = FixedBlockSize(myFileObj,cipher.block_size)
        FileWrapper.__init__(self,myFileObj)

    def setCipher(self,cipher):
        """Change the cipher after object initialization."""
        self.__cipher = cipher
        self._wfunc = cipher.decrypt
    
    def __encrypt(self,data):
        """Encrypt the given data.
        This function pads any data given that is not a multiple of
        the cipher's blocksize.  Such a case would indicate that it
        is the last data to be read.
        """
        if len(data) % self.__cipher.block_size != 0:
            data = self._fileobj._pad_to_size(data)
        return self.__cipher.encrypt(data)

_deprecate("EncryptFile",Encrypt)


class Test_CryptFiles(unittest.TestCase):
    """Testcases for the (En/De)Crypt classes."""
    
    def setUp(self):
        from Crypto.Cipher import DES
        # Example inspired by the PyCrypto manual
        self.cipher = DES.new('abcdefgh',DES.MODE_ECB)
        self.plaintextin = "Guido van Rossum is a space alien."
        self.plaintextout = "Guido van Rossum is a space alien." + "\0"*6
        self.ciphertext = "\x11,\xe3Nq\x8cDY\xdfT\xe2pA\xfa\xad\xc9s\x88\xf3,\xc0j\xd8\xa8\xca\xe7\xe2I\xd15w\x1d\xfe\x92\xd7\xca\xc9\xb5r\xec"
        self.plainfile = StringIO(self.plaintextin)
        self.cryptfile = StringIO(self.ciphertext)
        self.outfile = StringIO()

    def tearDown(self):
        pass

    def test_ReadDecrypt(self):
        """Test reading from an encrypted file."""
        df = Decrypt(self.cryptfile,self.cipher,"r")
        self.assert_(df.read() == self.plaintextout)

    def test_Read1Decrypt(self):
        """Test reading one byte from an encrypted file."""
        df = Decrypt(self.cryptfile,self.cipher,"r")
        self.assertEquals(df.read(1),self.plaintextout[0])
        self.assertEquals(df.read(1),self.plaintextout[1])

    def test_ReadEncrypt(self):
        """Test reading from a decrypted file."""
        ef = Encrypt(self.plainfile,self.cipher,"r")
        self.assert_(ef.read() == self.ciphertext)

    def test_Read1Encrypt(self):
        """Test reading one bytes from a decrypted file."""
        ef = Encrypt(self.plainfile,self.cipher,"r")
        self.assertEquals(ef.read(1),self.ciphertext[0])
        self.assertEquals(ef.read(1),self.ciphertext[1])
    
    def test_WriteDecrypt(self):
        """Test writing to an encrypted file."""
        df = Decrypt(self.outfile,self.cipher,"w")
        df.write(self.plaintextin)
        df.flush()
        self.assert_(self.outfile.getvalue() == self.ciphertext)
        
    def test_WriteEncrypt(self):
        """Test writing to a decrypted file."""
        ef = Encrypt(self.outfile,self.cipher,"w")
        ef.write(self.ciphertext)
        self.assert_(self.outfile.getvalue() == self.plaintextout)


class Head(FileWrapper):
    """Wrapper acting like unix "head" command.
    
    This wrapper limits the amount of data returned from or written to the
    underlying file based on the number of bytes and/or lines.
    
    NOTE: no guarantees are made about the amount of data read *from*
          the underlying file, only about the amount of data returned to
          the calling function.
    """
    
    def __init__(self,fileobj,mode=None,bytes=None,lines=None):
        """Head wrapper constructor.
        The arguments <bytes> and <lines> specify the maximum number
        of bytes and lines to be read or written.  Reading/writing
        will terminate when one of the given values has been exceeded.
        Any extraneous data is simply discarded.
        """
        FileWrapper.__init__(self,fileobj,mode)
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

    def _write(self,data):
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


class Cat(FileWrapper):
    """Class concatenating several file-like objects.
    
    This is similar in functionality to the unix `cat` command.
    Data is read from each file in turn, until all have been
    exhausted.
    
    Since this doesnt make sense when writing to a file, the access
    mode is assumed to be "r" and cannot be set or modified. Each
    file is closed at the time of closing the wrapper.
    """
    
    def __init__(self,*files):
        """Cat wrapper constructor.
        This function accepts any number of file-like objects as its
        only arguments.  Data will be read from them in the order they
        are provided.
        """
        FileWrapper.__init__(self,None,"r")
        self._files = files
        self._curFile = 0
    
    def close(self):
        FileWrapper.close(self)
        for f in self._files:
            if hasattr(f,"close"):
                f.close()
    
    def _read(self,sizehint=-1):
        if len(self._files) <= self._curFile:
            return None
        data = self._files[self._curFile].read(sizehint)
        if not len(data):
            self._curFile += 1
            data = self._read(sizehint)
        return data
    
    def _write(self,data):
        raise IOError("Cat wrapper cannot be written to.")


class Test_Cat(unittest.TestCase):
    """Testcases for the filelike.Cat wrapper."""
    
    def setUp(self):
        self.intext1 = "Guido van Rossum\n is a space\n alien."
        self.intext2 = "But that's ok with me!"
        self.intext3 = "What do you think?"
        self.infile1 = StringIO(self.intext1)
        self.infile2 = StringIO(self.intext2)
        self.infile3 = StringIO(self.intext3)

    def tearDown(self):
        pass

    def test_basic(self):
        """Test basic concatenation of files."""
        fs = Cat(self.infile1,self.infile2,self.infile3)
        txt = "".join(fs.readlines())
        txtC = "".join([self.intext1,self.intext2,self.intext3])
        self.assertEquals(txt,txtC)


class Compress(Translate):
    """Compress a file using an arbitrary compression routine.

    All reads from the file are processed using self._compress, while
    all writes are passed through self._decompress.  Thus Compress(fobj)
    can be seen as the compressed version of fobj.

    Subclasses must implement _compress and _decompress.
    """

    def __init__(self,fileobj,mode=None):
        Translate.__init__(self,fileobj,mode=mode,
                           rfunc=self._compress,
                           wfunc=self._decompress)

class UnCompress(Translate):
    """Decompress a file using an arbitrary compression routine.

    All reads from the file are processed using self._decompress, while
    all writes are passed through self._compress.  Thus UnCompress(fobj)
    can be seen as the decompressed version of fobj.

    Subclasses must implement _compress and _decompress.
    """

    def __init__(self,fileobj,mode=None):
        Translate.__init__(self,fileobj,mode=mode,
                           rfunc=self._decompress,
                           wfunc=self._compress)


## Conditionally provide bz2 compression support
try:
    import bz2
    class BZ2Wrapper:
        """Mixin for wrapping files with BZ2 [de]compression.

        This class sets up _compress and _decompress as appropriate for
        BZ2 handling.  It should be mixed-in with one of CompressFile or
        DecompressFile, with BZ2Wrapper.__init__ called first.
        """

        def __init__(self,compresslevel=9):
            """BZ2Wrapper Constructor.

            <fileobj> is the file object with compressed contents.  <mode>
            is the file access mode. <compresslevel> an integer between 1
            and 9 giving the compression level.
            
            This does not support simultaneous reading and writing of a BZ2
            wrapped file, so mode must be either 'r' or 'w'.
            """
            # Create self._compress to handle compression
            compressor = bz2.BZ2Compressor(compresslevel)
            toFlush = {'c': False}
            def cfunc(data):
                toFlush['c'] = True
                return compressor.compress(data)
            def cflush():
                if not toFlush['c']:
                  return None
                data = compressor.flush()
                del cfunc.flush
                return data
            cfunc.flush = cflush
            self._compress = cfunc
            # Create self._decompress to handle decompression
            decompressor = bz2.BZ2Decompressor()
            def dfunc(data):
                return decompressor.decompress(data)
            self._decompress = dfunc


    class BZip2(BZ2Wrapper,Compress):
        """Class for reading and writing a bziped file.
        
        This class is the dual of UnBZip2 - it compresses read data, and
        decompresses written data.  Thus BZip2(f) is the compressed version
        of f.
        """
    
        def __init__(self,fileobj,mode=None,compresslevel=9):
            """BZip2 Constructor.

            <fileobj> is the file object with compressed contents.  <mode>
            is the file access mode. <compresslevel> an integer between 1
            and 9 giving the compression level.
            """
            BZ2Wrapper.__init__(self,compresslevel)
            Compress.__init__(self,fileobj,mode)

    class UnBZip2(BZ2Wrapper,UnCompress):
        """Class for reading and writing to a un-bziped file.
        
        This class behaves almost exactly like the bz2.BZ2File class from
        the standard library, except that it accepts an arbitrary file-like
        object and it does not support seek() or tell().  All reads from
        the file are decompressed, all writes are compressed.
        """
    
        def __init__(self,fileobj,mode=None,compresslevel=9):
            """UnBZip2 Constructor.

            <fileobj> is the file object with compressed contents.  <mode>
            is the file access mode. <compresslevel> an integer between 1
            and 9 giving the compression level.
            """
            BZ2Wrapper.__init__(self,compresslevel)
            UnCompress.__init__(self,fileobj,mode)
    
    _deprecate("BZ2File",UnBZip2)

    ##  Add handling of .bz2 files to filelike.open()
    def _BZip2_decoder(fileobj):
        """Decoder function for handling .bz2 files with filelike.open"""
        if not fileobj.name.endswith(".bz2"):
            return None
        if "a" in fileobj.mode:
            raise IOError("Cannot open .bz2 files in append mode")
        f = UnBZip2(fileobj)
        f.name = fileobj.name[:-4]
        return f
    filelike.open.decoders.append(_BZip2_decoder)
    
except ImportError:
    pass


## Conditionally provide gzip compression support
# TODO: understand zlib, implement own version similar to bz2 support
try:
    import gzip
    Gzip = gzip.GzipFile
except ImportError:
    pass


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
        f = filelike.open("http://www.rfk.id.au/scratch/test.txt.bz2")
        self.assertEquals(f.read(),"content goes here if you please.\n")


class Test_Compression(unittest.TestCase):
    """Testcases for the various compression wrappers."""
    
    def setUp(self):
        self.raw1 = "hello world I am raw text"
        self.bz1 = bz2.compress(self.raw1)

    def tearDown(self):
        pass

    def _test_rw(self,cls,dataIn,dataOut):
        """Basic read/write testing."""
        f = cls(StringIO(dataOut),'r')
        c = "".join(f)
        self.assertEquals(c,dataIn)
        f = cls(StringIO(),'w')
        f.write(dataIn)
        f.flush()
        self.assertEquals(f._fileobj.getvalue(),dataOut)

    def _test_readone(self,cls,dataIn,dataOut):
        f = cls(StringIO(dataOut),'r')
        c = f.read(1)
        self.assertEquals(c,dataIn[0])
        c = f.read(1)
        self.assertEquals(c,dataIn[1])

    def test_BZip2(self):
        """Test operation of BZip2."""
        self._test_rw(BZip2,self.bz1,self.raw1)
        self._test_readone(BZip2,self.bz1,self.raw1)

    def test_UnBZip2(self):
        """Test operation of UnBZip2."""
        self._test_rw(UnBZip2,self.raw1,self.bz1)
        self._test_readone(UnBZip2,self.raw1,self.bz1)



def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_FileWrapper))
    suite.addTest(unittest.makeSuite(Test_TranslateNull))
    suite.addTest(unittest.makeSuite(Test_TranslateRot13))
    suite.addTest(unittest.makeSuite(Test_FixedBlockSize5))
#    suite.addTest(unittest.makeSuite(Test_FixedBlockSize7))
#    suite.addTest(unittest.makeSuite(Test_FixedBlockSize24))
#    suite.addTest(unittest.makeSuite(Test_CryptFiles))
#    suite.addTest(unittest.makeSuite(Test_Head))
#    suite.addTest(unittest.makeSuite(Test_PadToBlockSize))
#    suite.addTest(unittest.makeSuite(Test_Cat))
#    suite.addTest(unittest.makeSuite(Test_OpenerDecoders))
#    try:
#      if bz2:
#        suite.addTest(unittest.makeSuite(Test_Compression))
#    except NameError:
#      pass
    return suite


# Run regression tests when called from comand-line
if __name__ == "__main__":
    UnitTest.TextTestRunner().run(testsuite())

