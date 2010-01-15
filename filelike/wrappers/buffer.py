# filelike/wrappers/buffer.py
#
# Copyright (C) 2009, Ryan Kelly
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

    filelike.wrappers.buffer:  buffering of streams to create a file
    
This module provides the filelike wrapper 'Buffer', which routes reads
and writes through a separate buffer file.  This allows the full file-like
interface to be provided, including seek() and tell(), while guaranteeing
that the underlying file is treated like a stream, with only read() and
write() being called.

The subclass 'FlushableBuffer' additionally assumes that the underlying
stream can be reset back to position zero, allowing flushes to be performed.

""" 

import filelike
from filelike.wrappers import FileWrapper

try:
    from tempfile import SpooledTemporaryFile as TemporaryFile
except ImportError:
    from tempfile import TemporaryFile


class Buffer(FileWrapper):
    """Class implementing buffereing of input and output streams.
    
    This class uses a separate buffer file to hold the contents of the
    underlying file while they are being manipulated.  As data is read
    it is duplicated into the buffer, and data is written from the buffer
    back to the file on close.
    """
    
    def __init__(self,fileobj,mode=None):
        """Buffered file wrapper constructor."""
        self._buffer = TemporaryFile()
        self._in_eof = False
        self._in_pos = 0
        super(Buffer,self).__init__(fileobj,mode)

    def _buffer_chunks(self):
        chunk = self._buffer.read(16*1024)
        if chunk == "":
            yield chunk
        else:
            while chunk != "":
                yield chunk
                chunk = self._buffer.read(16*1024)

    def _write_out_buffer(self):
        if self._check_mode("r"):
            self._read_rest()
            if "a" in self.mode:
                self._buffer.seek(self._in_pos)
                self._fileobj.seek(self._in_pos)
            else:
                self._fileobj.seek(0)
                self._buffer.seek(0)
        else:
            self._buffer.seek(0)
        for chunk in self._buffer_chunks():
            self._fileobj.write(chunk)
 
    def flush(self):
        # flush the buffer; we only write to the underlying file on close
        self._buffer.flush()

    def close(self):
        if self.closed:
            return
        if self._check_mode("w"):
            self._write_out_buffer()
        super(Buffer,self).close()

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
        if self._in_eof:
            return
        pos = self._buffer.tell()
        self._buffer.seek(0,2)
        data = self._fileobj.read(self._bufsize)
        while data:
            self._in_pos += len(data)
            self._buffer.write(data)
            data = self._fileobj.read(self._bufsize)
        self._in_eof = True 
        self._buffer.seek(pos)


class FlushableBuffer(Buffer):
    """Buffered file wrapper that supports flusing.

    This subclass of Buffer assumes that the underlying file object can
    be reset to position 0, allowing calls to flush() to write out to
    the underlying file.
    """

    _append_requires_overwite = True

    def __init__(self,fileobj,mode=None):
        super(FlushableBuffer,self).__init__(fileobj,mode)
        if "a" in self.mode and not self._check_mode("r"):
            self._start_pos = self._fileobj.tell()

    def flush(self):
        if self._check_mode("w-"):
            pos = self._buffer.tell()
            self._write_out_buffer()
            self._buffer.seek(pos)
        # Skip Buffer.flush, as it doesn't call parent class methods
        super(Buffer,self).flush()

    def close(self):
        if self.closed:
            return
        # Don't call Buffer.close, it will call _write_out_buffer, but
        # that's done by the implicit flush() in this case.
        super(Buffer,self).close()

    def _write_out_buffer(self):
        if self._check_mode("r"):
            self._read_rest()
            if "a" in self.mode:
                self._buffer.seek(self._in_pos)
                self._fileobj.seek(self._in_pos)
            else:
                self._fileobj.seek(0)
                self._buffer.seek(0)
        else:
            if "a" in self.mode:
                self._fileobj.seek(self._start_pos)
            else:
                self._fileobj.seek(0)
            self._buffer.seek(0)
        for chunk in self._buffer_chunks():
            self._fileobj.write(chunk)


