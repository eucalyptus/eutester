'''
Created on Oct 18, 2012
@author: mmunn
Unit test          : EUCA-2244 Default launch permission for user image (account resource)
                     The fix for this issue changes the database so euca_conf --initialize
                     must have been run with the fix present for this test to pass.
setUp              : Install Credentials, sat variables
test               : Create and register an image and make sure the default visibility is Private not Public
tearDown           : Removes Credential, removes image

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
ip address CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops
from testcases.cloud_user.images.imageutils import ImageUtils


class Euca2244(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"
        self.bucket = "test-bucket"
        self.imgName = "bfebs-centos-vmwaretools-i386.img"
        self.imgUrl =  "http://mirror.qa.eucalyptus-systems.com/bfebs-image/vmware/"     
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.iu = ImageUtils(tester=self.tester, config_file=self.conf )
        self.doAuth()

    def tearDown(self):
        self.tester.sys(self.source + "euca-deregister " + self.emi)
        self.tester.sys(self.source + "euca-delete-bundle -b " + self.imgName + "test0")
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath)  
    
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def testName(self):
        self.emi = self.iu.create_emi_from_url( self.imgUrl + self.imgName)
        self.out = self.tester.sys(self.source + "euca-describe-images " + self.emi)
        self.count = str(self.out).count("private")
        if self.count==1:
            self.tester.debug("SUCCESS The default image availability is private")
            pass
        else:
            self.fail("FAIL The default image availability is public not private")
        
if __name__ == "__main__":
    unittest.main("Euca2244")