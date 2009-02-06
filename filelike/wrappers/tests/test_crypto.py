
from filelike.wrappers import Decrypt, Encrypt
from filelike.tests import Test_ReadWriteSeek
import unittest
from StringIO import StringIO


class Test_Encrypt(Test_ReadWriteSeek):
    """Testcases for the Encrypt wrapper class"""
    
    contents = "\x11,\xe3Nq\x8cDY\xdfT\xe2pA\xfa\xad\xc9s\x88\xf3,\xc0j\xd8\xa8\xca\xe7\xe2I\xd15w\x1d\xfe\x92\xd7\xca\xc9\xb5r\xec"
    plaintext = "Guido van Rossum is a space alien." + "\0"*6

    def makeFile(self,contents,mode):
        if len(contents) % self.cipher.block_size != 0:
            raise ValueError("content must be multiple of blocksize.")
        s = StringIO(self.cipher.decrypt(contents))
        f = Encrypt(s,self.cipher,mode=mode)
        def getvalue():
            return self.cipher.encrypt(s.getvalue())
        f.getvalue = getvalue
        return f
        
    def setUp(self):
        from Crypto.Cipher import DES
        self.cipher = DES.new('abcdefgh',DES.MODE_ECB)
        super(Test_Encrypt,self).setUp()


class Test_EncryptFB(Test_ReadWriteSeek):
    """Testcases for the Encrypt wrapper class, using a feedback cipher"""
    
    contents = "\xc9\xa3b\x18\xeb\xe8\xbe3\x84\x9a,\x025\x13\xb0\xb7It\x90@a\xb1\xc2\x13\x04_6c\x19\x0b\xf2\xcd\x0eD\xfb?\xf5\xbb\xad\xc8"
    plaintext = "Guido van Rossum is a space alien." + "\0"*6

    def makeFile(self,contents,mode):
        IV = self.cipher.IV
        if len(contents) % self.cipher.block_size != 0:
            raise ValueError("content must be multiple of blocksize.")
        s = StringIO(self.cipher.decrypt(contents))
        self.cipher.IV = IV
        f = Encrypt(s,self.cipher,mode=mode)
        def getvalue():
            IV = self.cipher.IV
            self.cipher.IV = "12345678"
            val = self.cipher.encrypt(s.getvalue())
            self.cipher.IV = IV
            return val
        f.getvalue = getvalue
        return f
        
    def setUp(self):
        from Crypto.Cipher import DES
        self.cipher = DES.new('abcdefgh',DES.MODE_CBC,"12345678")
        super(Test_EncryptFB,self).setUp()


class Test_Decrypt(Test_ReadWriteSeek):
    """Testcases for the Decrypt wrapper class"""
    
    ciphertext = "\x11,\xe3Nq\x8cDY\xdfT\xe2pA\xfa\xad\xc9s\x88\xf3,\xc0j\xd8\xa8\xca\xe7\xe2I\xd15w\x1d\xfe\x92\xd7\xca\xc9\xb5r\xec"
    contents = "Guido van Rossum is a space alien." + "\0"*6

    def makeFile(self,contents,mode):
        if len(contents) % self.cipher.block_size != 0:
            raise ValueError("content must be multiple of blocksize.")
        s = StringIO(self.cipher.encrypt(contents))
        f = Decrypt(s,self.cipher,mode=mode)
        def getvalue():
            return self.cipher.decrypt(s.getvalue())
        f.getvalue = getvalue
        return f
        
    def setUp(self):
        from Crypto.Cipher import DES
        self.cipher = DES.new('abcdefgh',DES.MODE_ECB)
        super(Test_Decrypt,self).setUp()


class Test_DecryptFB(Test_ReadWriteSeek):
    """Testcases for the Decrypt wrapper class, using a feedback cipher"""
    
    ciphertext = "\xc9\xa3b\x18\xeb\xe8\xbe3\x84\x9a,\x025\x13\xb0\xb7It\x90@a\xb1\xc2\x13\x04_6c\x19\x0b\xf2\xcd\x0eD\xfb?\xf5\xbb\xad\xc8"
    contents = "Guido van Rossum is a space alien." + "\0"*6

    def makeFile(self,contents,mode):
        IV = self.cipher.IV
        if len(contents) % self.cipher.block_size != 0:
            raise ValueError("content must be multiple of blocksize.")
        s = StringIO(self.cipher.encrypt(contents))
        self.cipher.IV = IV
        f = Decrypt(s,self.cipher,mode=mode)
        def getvalue():
            IV = self.cipher.IV
            self.cipher.IV = "12345678"
            val = self.cipher.decrypt(s.getvalue())
            self.cipher.IV = IV
            return val
        f.getvalue = getvalue
        return f
        
    def setUp(self):
        from Crypto.Cipher import DES
        self.cipher = DES.new('abcdefgh',DES.MODE_CBC,"12345678")
        super(Test_DecryptFB,self).setUp()

