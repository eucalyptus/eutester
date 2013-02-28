#!/usr/bin/python
'''
Created on Oct 23, 2012
@author: mmunn
Unit test          : EUCA-3932 euca-describe-image-attribute does not list all permissions
                     add new --launch-permission and check euca-describe-image-attribute to
                     make sure the new --launch-permission is listed
setUp              : Install Credentials, set variables, create account
test               : add --launch-permission check  euca-describe-image-attribute output
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops
from testcases.cloud_user.images.imageutils import ImageUtils


class Euca3932(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"
        self.acctName = "test-account" 
        self.cmdMod =  " euca-modify-image-attribute --launch-permission "
        self.cmdDes =  " euca-describe-image-attribute --launch-permission "     
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.out = self.tester.create_account(self.acctName)
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.doAuth()

    def tearDown(self):
        self.tester.delete_account(self.acctName,recursive=True)
        self.tester.cleanup_artifacts() 
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath)  
    
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)
               
    def testLaunchPermission(self):
        self.emi = self.tester.get_emi()
        #Get new userId (AccountId)
        self.outAccts = self.tester.get_all_accounts(account_name=self.acctName)
        for u in self.outAccts:
            self.testAccountId = u.account_id            
        # Add --launch-permission
        self.tester.sys(self.source + self.cmdMod + " -a " + self.testAccountId + " " + self.emi.id)
        # Describe --launch-permissions
        self.outDes = self.tester.sys(self.source + self.cmdDes + self.emi.id)
        # Check --launch-permissions for added userId
        self.count = str(self.outDes).count(self.testAccountId)
        # Remove added --launch-permission
        self.tester.sys(self.source + self.cmdMod + " -r " + self.testAccountId + " " + self.emi.id)
        if self.count==1:
            self.tester.debug("SUCCESS The --launch-permission for " + self.testAccountId + " was added.")
            pass
        else:
            self.fail("FAIL The --launch-permission for " + self.testAccountId + " not added.")
if __name__ == "__main__":
    unittest.main("Euca3932")