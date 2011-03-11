
from filelike.wrappers import BZip2, UnBZip2, GZip, UnGZip
from filelike import tests
from filelike.wrappers.tests.test_buffer import get_buffered_value, def_getvalue_maybe_buffered

import unittest
from StringIO import StringIO

import bz2
import gzip


class Test_BZip2(tests.Test_ReadWriteSeek):
    """Tetcases for BZip2 wrapper class."""

    contents = bz2.compress("This is my compressed\n test data")
    empty_contents = bz2.compress("")

    def makeFile(self,contents,mode):
        s = StringIO(bz2.decompress(contents))
        f = BZip2(s,mode)
        f.getvalue = def_getvalue_maybe_buffered(f,s,bz2.compress)
        return f

    #  We can't just write arbitrary text into a BZip stream, so we have
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

    def test_resulting_file(self):
        """Make sure BZip2 changes are pushed through to actual file."""
        import tempfile
        import os
        (fd,fn) = tempfile.mkstemp()
        os.close(fd)
        try:
            f = open(fn,"w")
            f.write("hello world!")
            f.close()
            f = BZip2(open(fn,"r+"))
            f.read(6)
            f.seek(-6,1)
            f.write(bz2.compress("hello Australia!"))
            f.close()
            self.assertEquals(open(fn).read(),"hello Australia!")
        finally:
            os.unlink(fn)


class Test_UnBZip2(tests.Test_ReadWrite):
    """Tetcases for UnBZip2 wrapper class."""

    contents = "This is my uncompressed\n test data"

    def makeFile(self,contents,mode):
        s = StringIO(bz2.compress(contents))
        f = UnBZip2(s,mode)
        f.getvalue = def_getvalue_maybe_buffered(f,s,bz2.decompress)
        return f

    def test_resulting_file(self):
        """Make sure UnBZip2 changes are pushed through to actual file."""
        import tempfile
        import os
        (fd,fn) = tempfile.mkstemp()
        os.close(fd)
        try:
            f = open(fn,"w")
            f.write(bz2.compress("hello world!"))
            f.close()
            f = UnBZip2(open(fn,"r+"))
            f.read(6)
            f.write("Ausralia!")
            f.seek(-6,1)
            f.write("tralia!")
            f.close()
            self.assertEquals(open(fn).read(),bz2.compress("hello Australia!"))
        finally:
          os.unlink(fn)


def gz_compress(data):
    s = StringIO()
    f = gzip.GzipFile(fileobj=s,mode="w")
    f.write(data)
    f.close()
    return s.getvalue()

def gz_decompress(data):
    s = StringIO()
    s.write(data)
    s.seek(0)
    f = gzip.GzipFile(fileobj=s)
    return f.read()


class Test_GZip(tests.Test_ReadWriteSeek):
    """Tetcases for GZip wrapper class."""

    contents = gz_compress("This is my compressed\n test data")
    empty_contents = gz_compress("")

    def makeFile(self,contents,mode):
        s = StringIO(gz_decompress(contents))
        f = GZip(s,mode)
        f.getvalue = def_getvalue_maybe_buffered(f,s,gz_compress)
        return f

    #  We can't just write arbitrary text into a BZip stream, so we have
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

    def test_resulting_file(self):
        """Make sure GZip changes are pushed through to actual file."""
        import tempfile
        import os
        (fd,fn) = tempfile.mkstemp()
        os.close(fd)
        try:
            f = open(fn,"w")
            f.write("hello world!")
            f.close()
            f = GZip(open(fn,"r+"))
            f.read(6)
            f.seek(-6,1)
            f.write(gz_compress("hello Australia!"))
            f.close()
            self.assertEquals(open(fn).read(),"hello Australia!")
        finally:
            os.unlink(fn)


class Test_UnGZip(tests.Test_ReadWrite):
    """Tetcases for UnGZip wrapper class."""

    contents = "This is my uncompressed\n test data"

    def makeFile(self,contents,mode):
        s = StringIO(gz_compress(contents))
        f = UnGZip(s,mode)
        f.getvalue = def_getvalue_maybe_buffered(f,s,gz_decompress)
        return f

    def test_resulting_file(self):
        """Make sure UnBZip2 changes are pushed through to actual file."""
        import tempfile
        import os
        (fd,fn) = tempfile.mkstemp()
        os.close(fd)
        try:
            f = open(fn,"w")
            f.write(gz_compress("hello world!"))
            f.close()
            f = UnGZip(open(fn,"r+"))
            f.read(6)
            f.write("Ausralia!")
            f.seek(-6,1)
            f.write("tralia!")
            f.close()
            self.assertEquals(open(fn).read(),gz_compress("hello Australia!"))
        finally:
          os.unlink(fn)

