'''
Created on Mar 14, 2013
@author: mmunn
Unit test          : EUCA-4868 euca-deregister returns malformed error message
setUp              : Install Credentials,
test               : use euca-deregister on non-existant image and check for new user friendly AWS compatible error.
tearDown           : Removes Credentials,

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca4868(unittest.TestCase):

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
        # Try and deregister an non-existant image
        self.runSysCmd("euca-deregister emi-12345678")
        # Check for new error (The image id '[emi-12345678]' does not exist)
        self.new = str(self.out).count("The image id '[emi-12345678]' does not exist")
        # We should see the new error and not the old.
        if self.new > 0 :
            self.tester.debug("SUCCESS new error logged")
            pass
        else:
            self.fail("FAIL old error logged")
        
if __name__ == "__main__":
    unittest.main("Euca4868")
    