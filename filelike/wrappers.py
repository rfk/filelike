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
        super(Translate,self).__init__(fileobj,mode)
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
    
    No padding is added to the file is its length is not a multiple 
    of the blocksize.
    """
    
    def __init__(self,fileobj,blocksize,mode=None):
        super(FixedBlockSize,self).__init__(fileobj,mode)
        self.blocksize = blocksize
    
    def _round_up(self,num):
        """Round <num> up to a multiple of the block size."""
        if num % self.blocksize == 0:
            return num
        return ((num/self.blocksize)+1) * self.blocksize
    
    def _round_down(self,num):
        """Round <num> down to a multiple of the block size."""
        if num % self.blocksize == 0:
            return num
        return (num/self.blocksize) * self.blocksize

    def _read(self,sizehint=-1):
        """Read approximately <sizehint> bytes from the file."""
        if sizehint >= 0:
            sizehint = self._round_up(sizehint)
        data = self._fileobj.read(sizehint)
        if data == "":
            return None
        return data

    def _write(self,data,flushing=False):
        """Write the given string to the file.

        When flushing data to the file, it may need to be padded to the
        block size.  We attempt to read additional data from the
        underlying file to use for the padding.
        """
        size = self._round_down(len(data))
        self._fileobj.write(data[:size])
        if len(data) == size:
            return ""
        if not flushing:
            return data[size:]
        # Flushing, so we need to try to pad the data with existing contents.
        # If we can't find such contents, just write at non-blocksize.
        if self._check_mode("r"):
            nextBlock = self._fileobj.read(self.blocksize)
            self._fileobj.seek(-1*len(nextBlock),1)
        else:
            nextBlock = ""
        padstart = len(data) - size
        self._fileobj.write(data[size:] + nextBlock[padstart:])
        # Seek back to start of previous block, if the file is readable.
        if self._check_mode("r"):
            self.seek(padstart - self.blocksize,1)
        return ""

    # TODO: primative implementation of relative seek
    def _seek(self,offset,whence):
        """Absolute seek, repecting block boundaries.

        This method performs an absolute file seek to the block boundary
        closest to (but not exceeding) the specified offset.
        """
        if whence != 0:
            raise NotImplementedError
        boundary = self._round_down(offset)
        self._fileobj.seek(boundary,0)
        if boundary == offset:
            return ""
        else:
            data = self._fileobj.read(self.blocksize)
            diff = offset - boundary - len(data)
            if diff > 0:
                # Seeked past end of file.  Actually do this on fileobj, so
                # that it will raise an error if appropriate.
                self._fileobj.seek(diff,1)
                self._fileobj.seek(-1*diff,1)
            self._fileobj.seek(-1*len(data),1)
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
                self.assert_(size < 0 or size % self.blocksize == 0)
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

    This class does not necessarily align reads or writes along block
    boundaries - use the FixedBlockSize wrapper to achieve this.
    """

    def __init__(self,fileobj,blocksize,mode=None):
        super(PadToBlockSize,self).__init__(fileobj,mode)
        self.blocksize = blocksize
        self._pad_loc = None
        self._pad_read = ""
        self._pad_unread = ""
    
    def _round_up(self,num):
        """Round <num> up to a multiple of the block size."""
        if num % self.blocksize == 0:
            return num
        return ((num/self.blocksize)+1) * self.blocksize
    
    def _round_down(self,num):
        """Round <num> down to a multiple of the block size."""
        if num % self.blocksize == 0:
            return num
        return (num/self.blocksize) * self.blocksize
    
    def _padding(self,data):
        """Get the padding needed to make 'data' match the blocksize."""
        padding = "Z"
        size = self._round_up(len(data)+1)
        padding = padding + ("X"*(size-len(data)-1))
        return padding

    def _read(self,sizehint=-1):
        # If there is unread padding, return that
        if self._pad_unread:
            data = self._pad_unread
            self._pad_read = self._pad_read + data
            self._pad_unread = ""
            return data
        # If the padding has been read, return EOF
        if self._pad_read:
            return None
        # Always read at the blocksize, as it makes padding easier
        if sizehint > 0:
            sizehint = self._round_up(sizehint)
        data = self._fileobj.read(sizehint)
        if sizehint < 0 or len(data) < sizehint:
            self._pad_loc = self._fileobj.tell()
            self._pad_unread = self._padding(data)
        return data

    def _write(self,string,flushing=False):
        # Check whether this could contain the padding block, which
        # will need to be removed.
        zIdx = string.rfind("Z")
        maybePad = zIdx >= len(string) - self.blocksize - 1
        for c in string[zIdx+1:]:
            if c != "X":
                maybePad = False
                break
        # If it may contain the padding block, don't write those blocks
        # just yet.  Otherwise, write as much as possible.
        if maybePad:
            size = self._round_down(zIdx)
        else:
            size = self._round_down(len(string))
        self._fileobj.write(string[:size])
        leftover = string[size:]
        # If there's no leftover, well, that was easy :-)
        if not leftover:
            return None
        # If we're not flushing, we can delay writing the leftovers.
        if not flushing:
            return leftover
        # If we are flushing, we need to write the leftovers.
        # If we're in the middle of the file, write out a complete block
        # using the existing file contents.  Only works if readable...
        if self._check_mode("r"):
            lenNB = self._round_up(len(leftover))
            nextBlock = self._fileobj.read(lenNB)
            self._fileobj.seek(-1*len(nextBlock),1)
            if lenNB == len(nextBlock):
                padstart = len(leftover)
                self._fileobj.write(leftover + nextBlock[padstart:])
                self.seek(padstart - lenNB,1)
                return None
        # Otherwise, we must be at the end of the file.
        # Remove the padding data from the leftovers
        if maybePad:
            zIdx = leftover.rfind("Z")
            self._fileobj.write(leftover[:zIdx])
        return None

    def _seek(self,offset,whence):
        """Seek to approximately 'offset' bytes from start of while.

        This method implements absolute seeks and will not seek to
        positions beyond the end of the file.  If you try to seek past
        the file and its padding, you'll be placed at EOF.
        """
        if whence > 0:
            raise NotImplementedError
        # Slow simulation of seek by actually re-reading all the data.
        self._fileobj.seek(0,0)
        self._pad_unread = ""
        self._pad_read = ""
        data = self._fileobj.read(offset)
        boundary = self._round_down(len(data))
        # 1) We're within the file, so it's nice and easy
        if len(data) == offset:
            self._fileobj.seek(boundary-offset,1)
            return data[boundary:offset]
        # 2) We're past the underlying file.
        padding = self._padding(data)
        self._fileobj.seek(boundary-len(data),1)
        diff = offset - len(data)
        # If we're inside the padding, only return what's necessary.
        # Otherwise, we've seeked to the end of the whole thing.
        if diff <= len(padding):
            padding = padding[:diff]
        return data[boundary:] + padding

    def _tell(self):
        return self._fileobj.tell() + len(self._pad_read)


class UnPadToBlockSize(FileWrapper):
    """Class removing block-size padding from a file.
    
    This file wrapper can be used to reverse the effects of PadToBlockSize,
    removing extraneous padding data when reading, and adding it back in
    when writing.
    """
    
    def __init__(self,fileobj,blocksize,mode=None):
        super(UnPadToBlockSize,self).__init__(fileobj,mode)
        self.blocksize = blocksize
        self._pad_seen = ""

    def _round_up(self,num):
        """Round <num> up to a multiple of the block size."""
        if num % self.blocksize == 0:
            return num
        return ((num/self.blocksize)+1) * self.blocksize
    
    def _round_down(self,num):
        """Round <num> down to a multiple of the block size."""
        if num % self.blocksize == 0:
            return num
        return (num/self.blocksize) * self.blocksize
    
    def _padding(self,data):
        """Get the padding needed to make 'data' match the blocksize."""
        padding = "Z"
        size = self._round_up(len(data)+1)
        padding = padding + ("X"*(size-len(data)-1))
        return padding
    
    def _read(self,sizehint=-1):
        """Read approximately <sizehint> bytes from the file."""
        if sizehint >= 0:
            sizehint = self._round_up(sizehint)
        data = self._fileobj.read(sizehint)
        # If we might be near the end, read far enough ahead to find the pad
        zIdx = data.rfind("Z")
        if sizehint >= 0:
            if data == "X"*self.blocksize:
                newData = self._fileobj.read(self.blocksize)
                sizehint += self.blocksize
                data = data + newData
            if zIdx >= 0:
                while zIdx >= (len(data) - self.blocksize - 1):
                    newData = self._fileobj.read(self.blocksize)
                    sizehint += self.blocksize
                    data = data + newData
                    zIdx = data.rfind("Z")
                    if newData == "":
                        break
        # Return the data, stripping the pad if we're at the end
        if data == "":
            return None
        if sizehint < 0 or len(data) < sizehint:
            if zIdx < 0:
                assert len(data) <= self.blocksize
                return None
            else:
                self._pad_seen = data[zIdx:]
                return data[:zIdx]
        else:
            return data

    def _write(self,data,flushing=False):
        """Write the given string to the file."""
        size = self._round_down(len(data))
        self._fileobj.write(data[:size])
        leftover = data[size:]
        if not flushing:
            return leftover
        # Flushing, so we need to pad the data.  If the file is readable,
        # check to see if we're in the middle and pad using existing data.
        if self._check_mode("r"):
            lenNB = self._round_up(len(leftover))
            nextBlock = self._fileobj.read(lenNB)
            self._fileobj.seek(-1*len(nextBlock),1)
            if lenNB == len(nextBlock):
                padstart = len(leftover)
                self._fileobj.write(leftover + nextBlock[padstart:])
                self.seek(padstart - lenNB,1)
                return None
        # Otherwise, we must be at the end of the file.
        padding = self._padding(leftover)
        self._fileobj.write(leftover + padding)
        self._pad_seen = padding
        return None

    def _seek(self,offset,whence):
        if whence > 0:
            raise NotImplementedError
        self._fileobj.seek(0,0)
        self._pad_seen = ""
        data = self._fileobj.read(offset)
        eof = data.rfind("Z")
        if len(data) < offset:
            offset = eof
        elif eof > len(data) - self.blocksize - 1:
            extra = self._fileobj.read(self.blocksize+1)
            data = data + extra
            if len(extra) <= self.blocksize:
                eof = data.rfind("Z")
                if eof < offset:
                    offset = eof
        boundary = self._round_down(offset)
        self._fileobj.seek(boundary-len(data),1)
        return data[boundary:offset]

    def _tell(self):
        return self._fileobj.tell() - len(self._pad_seen)


_deprecate("PaddedToBlockSizeFile",UnPadToBlockSize)


class Test_PadToBlockSize5(filelike.Test_ReadWriteSeek):
    """Testcases for PadToBlockSize with blocksize=5."""

    contents = "this is some sample textZ"
    text_plain = ["Zhis is sample texty"]
    text_padded = ["Zhis is sample textyZXXXX"]
    blocksize = 5

    def makeFile(self,contents,mode):
        # Careful here - 'contents' should be the contents of the returned
        # file, and is therefore expected to contain the padding.  But for
        # easy testing we allow it to omit the padding and be used directly
        # in the underlying StringIO object.
        idx = contents.rfind("Z")
        if idx < 0:
            idx = len(contents)
        f = PadToBlockSize(StringIO(contents[:idx]),self.blocksize,mode=mode)
        return f

    def test_padding(self):
        for (plain,padded) in zip(self.text_plain,self.text_padded):
            f = self.makeFile(padded,"rw")
            self.assert_(len(padded) % self.blocksize == 0)
            self.assertEquals(f._fileobj.getvalue(),plain)

    def test_read_empty_file(self):
        # The empty file should still yield padding
        f = self.makeFile("","r")
        self.assertEquals(f.read(),"Z"+"X"*(f.blocksize-1))

    def test_write_zeds(self):
        f = self.makeFile("","w")
        txt = "test data Z with lots of Z's embedded in it Z"
        f.write("test data Z w")
        f.write("ith lots of Z's e")
        f.write("mbedded in it Z")
        f.write(f._padding(txt))
        f.flush()
        self.assertEquals(f._fileobj.getvalue(),txt)


class Test_PadToBlockSize7(Test_PadToBlockSize5):
    """Testcases for PadToBlockSize with blocksize=7."""

    contents = "this is som\n sample textZXXX"
    text_plain = ["Zhis is sample texty"]
    text_padded = ["Zhis is sample textyZ"]
    blocksize = 7


class Test_PadToBlockSize16(Test_PadToBlockSize5):
    """Testcases for PadToBlockSize with blocksize=16."""

    contents = "This is Zome Zample TeZTZXXXXXXX"
    text_plain = ["short"]
    text_padded = ["shortZXXXXXXXXXX"]
    blocksize = 16


class Test_UnPadToBlockSize5(filelike.Test_ReadWriteSeek):
    """Testcases for UnPadToBlockSize with blocksize=5."""

    contents = "this is some sample text"
    text_plain = ["Zhis is sample texty"]
    text_padded = ["Zhis is sample textyZXXXX"]
    blocksize = 5

    def makeFile(self,contents,mode):
        f = UnPadToBlockSize(StringIO(""),self.blocksize,mode=mode)
        f._fileobj = StringIO(contents + f._padding(contents))
        return f

    def test_padding(self):
        for (plain,padded) in zip(self.text_plain,self.text_padded):
            f = self.makeFile(plain,"rw")
            self.assertEquals(f._fileobj.getvalue(),padded)

    def test_write_zeds(self):
        f = self.makeFile("","w")
        txt = "test data Z with lots of Z's embedded in it Z"
        f.write("test data Z w")
        f.write("ith lots of Z's e")
        f.write("mbedded in it Z")
        f.flush()
        self.assertEquals(f._fileobj.getvalue(),txt + f._padding(txt))

    def test_read_zeds(self):
        f = self.makeFile("","r")
        txt = "test data Z with lots of Z's embedded in it Z"
        f._fileobj = StringIO(txt + f._padding(txt))
        self.assertEquals(f.read(),txt)


class Test_UnPadToBlockSize7(Test_UnPadToBlockSize5):
    """Testcases for UnPadToBlockSize with blocksize=7."""

    contents = "this is som\n sample text"
    text_plain = ["Zhis is sample texty"]
    text_padded = ["Zhis is sample textyZ"]
    blocksize = 7


class Test_UnPadToBlockSize16(Test_UnPadToBlockSize5):
    """Testcases for UnPadToBlockSize with blocksize=16."""

    contents = "This is Zome Zample TeZTZ"
    text_plain = ["short"]
    text_padded = ["shortZXXXXXXXXXX"]
    blocksize = 16


#############


class Decrypt(FixedBlockSize):
    """Class for reading and writing to an encrypted file.
    
    This class accesses an encrypted file using a ciphering object
    compliant with PEP272: "API for Block Encryption Algorithms".
    All reads from the file are automatically decrypted, while writes
    to the file and automatically encrypted.  Thus, Decrypt(fobj)
    can be seen as the decrypted version of the file-like object fobj.
    
    Because this class is implemented on top of FixedBlockSize, it
    assumes that the file size is a multiple of the block size.  If this
    is not appropriate, wrap it with UnPadToBlockSize.
    
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
        self.setCipher(cipher)
        myFileObj = Translate(fileobj,mode=mode,bytewise=True,
                                      rfunc=self._rfunc,
                                      wfunc=self._wfunc)
        super(Decrypt,self).__init__(myFileObj,self.blocksize,mode=mode)
        
    def setCipher(self,cipher):
        """Change the cipher after object initialization."""
        self._cipher = cipher
        self.blocksize = cipher.block_size

    def _rfunc(self,data):
        return self._cipher.decrypt(data)

    def _wfunc(self,data):
        return self._cipher.encrypt(data)


_deprecate("DecryptFile",Decrypt)


class Encrypt(FixedBlockSize):
    """Class for reading and writing to an decrypted file.
    
    This class accesses a decrypted file using a ciphering object
    compliant with PEP272: "API for Block Encryption Algorithms".
    All reads from the file are automatically encrypted, while writes
    to the file are automatically decrypted.  Thus, Encrypt(fobj)
    can be seen as the encrypted version of the file-like object fobj.

    Because this class is implemented on top of FixedBlockSize, it
    assumes that the file size is a multiple of the block size.  If this
    is not appropriate, wrap the underlying file object with PadToBlockSize.
    You will need to write the padding data yourself.
    
    There is a dual class, Decrypt, where all reads are decrypted
    and all writes are encrypted.  This would be used, for example, to
    decrypt the contents of an existing file using a series of read()
    operations.
    """

    def __init__(self,fileobj,cipher,mode=None):
        """Encrypt Constructor.

        'fileobj' is the file object with decrypted contents, and 'cipher'
        is the cipher object to be used.  Other arguments are passed through
        to FileWrapper.__init__
        """
        self.setCipher(cipher)
        myFileObj = Translate(fileobj,mode=mode,bytewise=True,
                                      rfunc=self._rfunc,
                                      wfunc=self._wfunc)
        super(Encrypt,self).__init__(myFileObj,self.blocksize,mode=mode)

    def setCipher(self,cipher):
        """Change the cipher after object initialization."""
        self._cipher = cipher
        self.blocksize = cipher.block_size

    def _rfunc(self,data):
        return self._cipher.encrypt(data)

    def _wfunc(self,data):
        return self._cipher.decrypt(data)


_deprecate("EncryptFile",Encrypt)


class Test_Encrypt(filelike.Test_ReadWriteSeek):
    """Testcases for the Encrypt wrapper class"""
    
    contents = "\x11,\xe3Nq\x8cDY\xdfT\xe2pA\xfa\xad\xc9s\x88\xf3,\xc0j\xd8\xa8\xca\xe7\xe2I\xd15w\x1d\xfe\x92\xd7\xca\xc9\xb5r\xec"
    plaintext = "Guido van Rossum is a space alien." + "\0"*6

    def makeFile(self,contents,mode):
        if len(contents) % self.cipher.block_size != 0:
            raise ValueError("content must be multiple of blocksize.")
        f = Encrypt(StringIO(self.cipher.decrypt(contents)),self.cipher,mode=mode)
        return f
        
    def setUp(self):
        from Crypto.Cipher import DES
        # Example inspired by the PyCrypto manual
        self.cipher = DES.new('abcdefgh',DES.MODE_ECB)
        super(Test_Encrypt,self).setUp()


class Test_Decrypt(filelike.Test_ReadWriteSeek):
    """Testcases for the Decrypt wrapper class"""
    
    ciphertext = "\x11,\xe3Nq\x8cDY\xdfT\xe2pA\xfa\xad\xc9s\x88\xf3,\xc0j\xd8\xa8\xca\xe7\xe2I\xd15w\x1d\xfe\x92\xd7\xca\xc9\xb5r\xec"
    contents = "Guido van Rossum is a space alien." + "\0"*6

    def makeFile(self,contents,mode):
        if len(contents) % self.cipher.block_size != 0:
            raise ValueError("content must be multiple of blocksize.")
        f = Decrypt(StringIO(self.cipher.encrypt(contents)),self.cipher,mode=mode)
        return f
        
    def setUp(self):
        from Crypto.Cipher import DES
        # Example inspired by the PyCrypto manual
        self.cipher = DES.new('abcdefgh',DES.MODE_ECB)
        super(Test_Decrypt,self).setUp()



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
    suite.addTest(unittest.makeSuite(Test_FixedBlockSize7))
    suite.addTest(unittest.makeSuite(Test_FixedBlockSize24))
    suite.addTest(unittest.makeSuite(Test_PadToBlockSize5))
    suite.addTest(unittest.makeSuite(Test_PadToBlockSize7))
    suite.addTest(unittest.makeSuite(Test_PadToBlockSize16))
    suite.addTest(unittest.makeSuite(Test_UnPadToBlockSize5))
    suite.addTest(unittest.makeSuite(Test_UnPadToBlockSize7))
    suite.addTest(unittest.makeSuite(Test_UnPadToBlockSize16))
    suite.addTest(unittest.makeSuite(Test_Encrypt))
    suite.addTest(unittest.makeSuite(Test_Decrypt))
#    suite.addTest(unittest.makeSuite(Test_Head))
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

