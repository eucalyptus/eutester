'''
Created on Dec 12, 2012
@author: mmunn
Unit test          : EUCA-2366 Unclear error message when attempting to create a volume larger than permitted.
                     The storage controller must be on a separate system to the cloud controller to reproduce this issue
setUp              : Install Credentials,
test               : try and create  a volume that is larger than the default max volume size and check for proper error.
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
machine00       CENTOS  6.3     64      BZR     [CC00 CLC WS]
machine01       CENTOS  6.3     64      BZR     [SC00]
machine02       CENTOS  6.3     64      BZR     [NC00
'''
import unittest
import shutil
from eucaops import Eucaops
from eutester.euproperties import EucaProperties

class Euca2366(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"       
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.cond = 1 
        self.doAuth()
        self.props = EucaProperties(self.tester)

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
        # Get availibility zone
        self.zone = self.tester.get_zones().pop()
        # Default Max volume size
        self.max_volume_size = int(self.props.get_property('storage.maxvolumesizeingb')[0])
        # Try and create volume larger than max_volume_size
        try:
            self.tester.create_volume(self.zone, self.max_volume_size + 1, timeout=10)
        except Exception as detail:
            print detail
            self.cond = str(detail).count('Max Volume Size Limit Exceeded')
       
        if self.cond >= 1:
            self.tester.debug("SUCCESS")
            pass
        else:
            self.fail("FAIL")
        
if __name__ == "__main__":
    unittest.main("Euca2366")
    