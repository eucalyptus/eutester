'''
Created on Oct 23, 2012
@author: mmunn
Unit test          : EUCA-3933 - euca-modify-image-attribute allows invalid userId without error.
setUp              : Install Credentials,
test               : Try and add --launch-permission bad userId and check for error
tearDown           : Removes Credentials

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca3933(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"
        self.fakeId = "OOO000000000"
        self.cmdMod =  " euca-modify-image-attribute --launch-permission "       
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.doAuth()

    def tearDown(self):
        self.tester.cleanup_artifacts() 
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath)  
    
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def testValidation(self):
        self.emi = self.tester.get_emi()
        # Try and add --launch-permission with a bad userId
        self.out = self.tester.sys(self.source + self.cmdMod + " -a " + self.fakeId + " " + self.emi.id)
        # Check output
        self.count = str(self.out).count("Not a valid userId")
        if self.count==1:
            self.tester.debug("SUCCESS --launch-permission validation error thrown")
            pass
        else:
            self.fail("FAIL no error with bad userID")
        pass
if __name__ == "__main__":
    unittest.main("Euca3933")