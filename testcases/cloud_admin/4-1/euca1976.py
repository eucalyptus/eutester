'''
Created on = '10/28/13"
Author = 'mmunn'

Unit test          : EUCA-1976 euca-describe-availability-zone allows invalid misspell of verbose
setUp              : Install Credentials,
test               : call euca-describe-availability-zones with non-existent zone parameter and check for error
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
import os
from eucaops import Eucaops


class Euca(unittest.TestCase):
    def setUp(self):
        self.conf = "../cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.doAuth()

    def tearDown(self):
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

    def runSysCmd(self, cmd):
        self.source = 'export EUCALYPTUS=' + self.tester.eucapath + " && source " + self.tester.credpath + "/eucarc && " + self.tester.eucapath + "/usr/bin/"
        self.out = self.tester.sys(self.source + cmd)

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def test(self):
        # using a non-existent zone should throw an InvalidParameterValue error
        self.runSysCmd("euca-describe-availability-zones bogus-zone")
        # Make sure InvalidParameterValue error thrown
        count = str(self.out).count('InvalidParameterValue')
        if count == 1 :
            self.tester.debug("SUCCESS")
            pass
        else:
            self.fail("FAILED : InvalidParameterValue error message not thrown")

if __name__ == "__main__":
    unittest.main()
