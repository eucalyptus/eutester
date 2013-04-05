'''
Created on Mar 21, 2013
@author: mmunn
Unit test          : EUCA-4750 Cloud property being unset causes euca-describe-properties display to be broken
setUp              : Install Credentials,
test               : Set a property with a null value, run euca-describe-properties and make sure that propert is listed.
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca4750(unittest.TestCase):

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
        # Set modify the property with a null value
        self.runSysCmd("euca-modify-property -p www.httpproxyhost=")
        self.runSysCmd("euca-describe-properties")
        # Check euca-describe-properties output for property
        self.count = str(self.out).count("www.httpproxyhost")
        # reset property to original value
        self.runSysCmd("euca-modify-property -r www.httpproxyhost")
        if self.count == 1:
            self.tester.debug("SUCCESS property with null value modified correctly")
            pass
        else:
            self.fail("FAIL value null value not modified correctly")
        
if __name__ == "__main__":
    unittest.main("Euca4750")
    