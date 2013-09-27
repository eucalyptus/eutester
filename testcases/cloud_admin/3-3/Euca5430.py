'''
Created on Jun 14, 2013
@author: mmunn
Unit test          : EUCA-5430 Bogus Error Message when creating security group that already exists
SetUp              : Install Credentials,
Test               : Try and create a security group with the same name twice and check the error
TearDown           : Removes Credentials

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca5430(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf" 
        self.cond = 1     
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
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

    def testName(self):
        #create the testGroup
        try:
            self.out = self.tester.create_group('Euca5430group')
        except Exception as detail:
            print str(detail)
        
        #try and create the testGroup again and check the error
        try:
            self.out = self.tester.create_group('Euca5430group')
        except Exception as detail:
            self.cond = str(detail).count('already exists')
        
        if self.cond >= 1:
            self.tester.debug("SUCCESS")
            pass
        else:
            self.fail("FAIL")
        
if __name__ == "__main__":
    unittest.main("Euca5430")
    