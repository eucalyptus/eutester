'''
Created on 8/6/13
Author: mmunn

Unit test          : EUCA-6559 euca-deregister needs to be ran twice to de-register an image (doesn't match AWS behavior)
setUp              : Install Credentials,
test               : Register and deregister an Image check that no images in the deregistered state are output to user.
tearDown           : Removes Credentials, terminates instance
get_emi()
cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops


class Euca6559(unittest.TestCase):
    def setUp(self):
        self.conf = "cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.doAuth()

    def tearDown(self):
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

    def runSysCmd(self, cmd):
        self.source = "source " + self.tester.credpath + "/eucarc && "
        self.out = self.tester.sys(self.source + cmd)

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def testName(self):
        self.emi = self.tester.get_emi()
        self.new_emi = self.tester.register_manifest(self.emi.location)
        self.tester.deregister_image(self.new_emi);
        self.runSysCmd('euca-describe-images ' + self.new_emi.id);
        ### make sure that the images in the deregistered state are not output to user.
        if  str(self.out).count('deregistered') == 0 :
            self.tester.debug("SUCCESS")
            pass
        else:
            self.fail("FAIL")

if __name__ == "__main__":
    unittest.main()