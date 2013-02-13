'''
Created on Dec 6, 2012
@author: mmunn
Unit test          : EUCA-1057 second euca-deregister does not deregister the image completely.
                     Test to make sure correct error is thrown on second deregister of non-terminated instance
setUp              : Install Credentials, set vars
test               : create emi, start instance, deregister twice check output for error
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
import sys
import traceback
from eucaops import Eucaops
from testcases.cloud_user.images.imageutils import ImageUtils

class Euca1057(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.iu = ImageUtils(tester=self.tester, config_file=self.conf )
        self.imgName = "bfebs-centos-vmwaretools-i386.img"
        self.imgUrl =  "http://mirror.qa.eucalyptus-systems.com/bfebs-image/vmware/"
        self.errorMsg = "all associated instances must be in the terminated state."
        self.count = 0
        self.doAuth()

    def tearDown(self):
        if self.reservation is not None:
            self.tester.terminate_instances(self.reservation)
        self.out = self.runSysCmd("euca-deregister " + self.emi)
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
        self.emi = self.iu.create_emi_from_url( self.imgUrl + self.imgName)
        self.reservation = self.tester.run_instance(image=self.emi,is_reachable=False)

        self.runSysCmd("euca-deregister " + self.emi)
        self.count = + str(self.out).count(self.errorMsg)
        if self.count==1:
            self.tester.debug("SUCCESS proper error thrown ")
            pass
        else:
            self.fail("FAIL incorrect error thrown ")
        
if __name__ == "__main__":
    unittest.main("Euca1057")
    