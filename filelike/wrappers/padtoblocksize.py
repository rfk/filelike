# filelike/wrappers/padtoblocksize.py
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

    filelike.wrappers.padtoblocksize:  pad a file to a given blocksize
    
This module provides the dual filelike wrappers 'PadToBlockSize' and 
'UnPadToBlockSize' to handle padding or a file to a specified blocksize.

""" 

import filelike
from filelike.wrappers import FileWrapper

import unittest
from StringIO import StringIO


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


def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_PadToBlockSize5))
    suite.addTest(unittest.makeSuite(Test_PadToBlockSize7))
    suite.addTest(unittest.makeSuite(Test_PadToBlockSize16))
    suite.addTest(unittest.makeSuite(Test_UnPadToBlockSize5))
    suite.addTest(unittest.makeSuite(Test_UnPadToBlockSize7))
    suite.addTest(unittest.makeSuite(Test_UnPadToBlockSize16))
    return suite

