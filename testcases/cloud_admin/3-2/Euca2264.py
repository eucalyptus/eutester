'''
Created on Oct 29, 2012
@author: mmunn
Unit test          : EUCA-2264 Binding error when registering image with multiple device mappings.
                     euca-run-instances and euca-register have the same code path 
                     This test only checks for this binding error:
                     412 Precondition Failed: Failed to bind the following fields:                   
setUp              : Install Credentials,
test               : run instance with multiple block device mappings and check for 412 Precondition Failed:error
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca2264(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"   
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.doAuth()

    def tearDown(self):
        self.runSysCmd("euca-terminate-instances " + self.instanceid)
        self.tester.cleanup_artifacts() 
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath)  
    
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)
        
    def runSysCmd(self, cmd):
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        # Save command output in self.out
        self.out = self.tester.sys(self.source + cmd)
         

    def testName(self):
        self.emi = self.tester.get_emi()
        # start instances with multiple block devices
        self.runSysCmd("euca-run-instances " + self.emi.id + " -b /dev/sda2=:20 -b /dev/sda3=:20")
        # Search for error message
        self.count = str(self.out).count("412 Precondition Failed:")
        # Get instance id
        self.index = str(self.out).find("i-")
        self.instanceid = str(self.out)[self.index:self.index + 10]
        # if error not found pass else fail
        if self.count == 0 :
            self.index = str(self.out).find("i-")
            self.instanceid = str(self.out)[self.index:self.index + 10]
            self.time = 0
            #Wait for instance to start
            while(self.count != 1 and self.time < 60):
                self.tester.sleep(5)
                self.time = self.time + 5
                self.runSysCmd("euca-describe-instances " + self.instanceid)
                self.count = str(self.out).count('running') 
                self.tester.debug("Elapsed time " + str(self.time) + " seconds.")        
            self.tester.debug("SUCCESS")
            pass
        else:
            self.fail("FAIL 412 Precondition Failed:")
    
if __name__ == "__main__":
    unittest.main("Euca2264")