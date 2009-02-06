
from filelike.wrappers import Buffered
from filelike.tests import Test_ReadWriteSeek

import unittest
from StringIO import StringIO

class Test_Buffered(Test_ReadWriteSeek):
    """Testcases for the Buffered class."""
    
    def makeFile(self,contents,mode):
        s = StringIO(contents)
        if "a" in mode:
            s.seek(0,2)
        f = Buffered(s,mode)
        def getvalue():
            if f._check_mode("r"):
                f._read_rest()
            pos = f._buffer.tell()
            f._buffer.seek(0)
            val = f._buffer.read()
            f._buffer.seek(pos)
            return val
        f.getvalue = getvalue
        return f

    def test_buffer_w(self):
        """Test that Buffered writes its contents out correctly on close."""
        f = self.makeFile("","w")
        s = f._fileobj
        close = s.close
        def noop():
            pass
        s.close = noop
        f.write("testing")
        f.flush()
        self.assertEquals(f.getvalue(),"testing")
        self.assertEquals(s.getvalue(),"")
        f.close()
        self.assertEquals(s.getvalue(),"testing")

    def test_buffer_rw(self):
        """Test that Buffered writes its contents out correctly on close."""
        f = self.makeFile("testing","r+")
        s = f._fileobj
        close = s.close
        def noop():
            pass
        s.close = noop
        f.write("hello")
        f.flush()
        self.assertEquals(f.getvalue(),"hellong")
        self.assertEquals(s.getvalue(),"testing")
        f.close()
        self.assertEquals(s.getvalue(),"hellong")

    def test_buffer_a(self):
        """Test that Buffered writes its contents out correctly on close."""
        f = self.makeFile("hello","a")
        s = f._fileobj
        close = s.close
        def noop():
            pass
        s.close = noop
        f.write("testing")
        f.flush()
        self.assertEquals(f.getvalue(),"testing")
        self.assertEquals(s.getvalue(),"hello")
        f.close()
        self.assertEquals(s.getvalue(),"hellotesting")

    def test_buffer_ra(self):
        """Test that Buffered writes its contents out correctly on close."""
        f = self.makeFile("hello","a+")
        s = f._fileobj
        close = s.close
        def noop():
            pass
        s.close = noop
        f.write("testing")
        f.flush()
        self.assertEquals(f.getvalue(),"testing")
        self.assertEquals(s.getvalue(),"hello")
        f.close()
        self.assertEquals(s.getvalue(),"hellotesting")


