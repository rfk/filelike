
from filelike.wrappers import Buffered
from filelike.tests import Test_ReadWriteSeek

import unittest
from StringIO import StringIO

class Test_Buffered(Test_ReadWriteSeek):
    """Testcases for the Buffered class."""
    
    def makeFile(self,contents,mode):
        f1 = super(Test_Buffered,self).makeFile(contents,mode)
        f = Buffered(f1,mode)
        def getvalue():
            pos = f._buffer.tell()
            f._buffer.seek(0)
            val = f._buffer.read()
            f._buffer.seek(pos)
            return val
        f.getvalue = getvalue
        return f

