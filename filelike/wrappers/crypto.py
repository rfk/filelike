# filelike/wrappers/crypto.py
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

    filelike.wrappers.crypto:  wrapper classes for cryptography
    
This module provides the filelike wrappers 'Encrypt' and 'Decrypt' for
dealing with encrypted files.

""" 

import filelike
from filelike.wrappers.translate import Translate, BytewiseTranslate
from filelike.wrappers.buffered import Buffered
from filelike.wrappers.fixedblocksize import FixedBlockSize

import unittest
from StringIO import StringIO

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
        self._cipher = cipher
        self.blocksize = cipher.block_size
        if cipher.mode == 1:
            # MODE_ECB is a bytewise translation
            self._bytewise = True
            myFileObj = BytewiseTranslate(fileobj,mode=mode,
                                                  rfunc=cipher.decrypt,
                                                  wfunc=cipher.encrypt)
        else:
            # Other modes are stateful translations.
            # To reset them, we simply reset the initialisation vector
            self._bytewise = False
            initialIV = cipher.IV
            def rfunc(data):
                return cipher.decrypt(data)
            def wfunc(data):
                return cipher.encrypt(data)
            def reset():
                cipher.IV = initialIV
            rfunc.reset = reset
            wfunc.reset = reset
            myFileObj = Translate(fileobj,mode=mode,rfunc=rfunc,wfunc=wfunc)
            #  To allow writes with seeks, we need to buffer.
            #  TODO: find a way around this.
            if mode is None:
                try:
                    mode = fileobj.mode
                except AttributeError:
                    mode = "r+"
            if self._check_mode("rw",mode):
                myFileObj = Buffered(myFileObj,mode=mode)
            elif self._check_mode("w",mode) and not self._check_mode("w-",mode):
                myFileObj = Buffered(myFileObj,mode=mode)
        super(Decrypt,self).__init__(myFileObj,self.blocksize,mode=mode)

    def _seek(self,offset,whence):
        # For stateful translations, don't bother with fancy seeks since
        # the underlying file will have to reset to start anyway.
        if not self._bytewise:
            if offset > 0 or whence > 0:
                raise NotImplementedError
        return super(Decrypt,self)._seek(offset,whence)


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
        self._cipher = cipher
        self.blocksize = cipher.block_size
        if cipher.mode == 1:
            # MODE_ECB is a bytewise translation
            self._bytewise = True
            myFileObj = BytewiseTranslate(fileobj,mode=mode,
                                                  rfunc=cipher.encrypt,
                                                  wfunc=cipher.decrypt)
        else:
            # Other modes are stateful translations.
            # To reset them, we simply reset the initialisation vector
            self._bytewise = False
            initialIV = cipher.IV
            def rfunc(data):
                return cipher.encrypt(data)
            def wfunc(data):
                return cipher.decrypt(data)
            def reset():
                cipher.IV = initialIV
            rfunc.reset = reset
            wfunc.reset = reset
            myFileObj = Translate(fileobj,mode=mode,rfunc=rfunc,wfunc=wfunc)
            #  To allow writes with seeks, we need to buffer.
            #  TODO: find a way around this.
            if mode is None:
                try:
                    mode = fileobj.mode
                except AttributeError:
                    mode = "r+"
            if self._check_mode("rw",mode):
                myFileObj = Buffered(myFileObj,mode=mode)
            elif self._check_mode("w",mode) and not self._check_mode("w-",mode):
                myFileObj = Buffered(myFileObj,mode=mode)
        super(Encrypt,self).__init__(myFileObj,self.blocksize,mode=mode)

    def _seek(self,offset,whence):
        # For stateful translations, don't bother with fancy seeks since
        # the underlying file will have to reset to start anyway.
        if not self._bytewise:
            if offset > 0 or whence > 0:
                raise NotImplementedError
        return super(Encrypt,self)._seek(offset,whence)


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
        self.cipher = DES.new('abcdefgh',DES.MODE_ECB)
        super(Test_Encrypt,self).setUp()


class Test_EncryptFB(filelike.Test_ReadWriteSeek):
    """Testcases for the Encrypt wrapper class, using a feedback cipher"""
    
    contents = "\xc9\xa3b\x18\xeb\xe8\xbe3\x84\x9a,\x025\x13\xb0\xb7It\x90@a\xb1\xc2\x13\x04_6c\x19\x0b\xf2\xcd\x0eD\xfb?\xf5\xbb\xad\xc8"
    plaintext = "Guido van Rossum is a space alien." + "\0"*6

    def makeFile(self,contents,mode):
        IV = self.cipher.IV
        if len(contents) % self.cipher.block_size != 0:
            raise ValueError("content must be multiple of blocksize.")
        f = Encrypt(StringIO(self.cipher.decrypt(contents)),self.cipher,mode=mode)
        self.cipher.IV = IV
        return f
        
    def setUp(self):
        from Crypto.Cipher import DES
        self.cipher = DES.new('abcdefgh',DES.MODE_CBC,"12345678")
        super(Test_EncryptFB,self).setUp()


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
        self.cipher = DES.new('abcdefgh',DES.MODE_ECB)
        super(Test_Decrypt,self).setUp()


class Test_DecryptFB(filelike.Test_ReadWriteSeek):
    """Testcases for the Decrypt wrapper class, using a feedback cipher"""
    
    ciphertext = "\xc9\xa3b\x18\xeb\xe8\xbe3\x84\x9a,\x025\x13\xb0\xb7It\x90@a\xb1\xc2\x13\x04_6c\x19\x0b\xf2\xcd\x0eD\xfb?\xf5\xbb\xad\xc8"
    contents = "Guido van Rossum is a space alien." + "\0"*6

    def makeFile(self,contents,mode):
        IV = self.cipher.IV
        if len(contents) % self.cipher.block_size != 0:
            raise ValueError("content must be multiple of blocksize.")
        f = Decrypt(StringIO(self.cipher.encrypt(contents)),self.cipher,mode=mode)
        self.cipher.IV = IV
        return f
        
    def setUp(self):
        from Crypto.Cipher import DES
        self.cipher = DES.new('abcdefgh',DES.MODE_CBC,"12345678")
        super(Test_DecryptFB,self).setUp()

def makefile():
    from Crypto.Cipher import DES
    cipher = DES.new('abcdefgh',DES.MODE_CBC,"12345678")
    return Decrypt(StringIO("\xc9\xa3b\x18\xeb\xe8\xbe3\x84\x9a,\x025\x13\xb0\xb7It\x90@a\xb1\xc2\x13\x04_6c\x19\x0b\xf2\xcd\x0eD\xfb?\xf5\xbb\xad\xc8"),cipher,mode="r+")
    
    

def testsuite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_Encrypt))
    suite.addTest(unittest.makeSuite(Test_EncryptFB))
    suite.addTest(unittest.makeSuite(Test_Decrypt))
    suite.addTest(unittest.makeSuite(Test_DecryptFB))
    return suite

