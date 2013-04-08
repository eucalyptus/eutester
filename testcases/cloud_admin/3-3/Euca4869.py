'''
Created on Mar 14, 2013
@author: mmunn
Unit test          : EUCA-4869 euca-deregister returns bogus error message when deregistering a malformed image ID
setUp              : Install Credentials,
test               : use euca-deregister on malformed imageid and check for new user friendly AWS compatible error.
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca4869(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.doAuth()

    def tearDown(self):
        self.tester.cleanup_artifacts() 
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath) 
                
    def runSysCmd(self, cmd):
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.out = self.tester.sys(self.source + cmd) 
         
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def testName(self):
        # Try and deregister a malforemd imageId (ie: emi, efi, eri followed by 8 chars)
        self.runSysCmd("euca-deregister emi-1234567")
        # Check for new error (Invalid id: "emi-1234567")
        self.new = str(self.out).count("Invalid id")
        # We should see the new error and not the old.
        if self.new > 0 :
            self.tester.debug("SUCCESS new error logged")
            pass
        else:
            self.fail("FAIL old error logged")
        
if __name__ == "__main__":
    unittest.main("Euca4869")
    