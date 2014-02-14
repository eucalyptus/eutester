'''
Created on = '11/15/13"
Author = 'mmunn'

Unit test          : EUCA-6427 DNS TCP handler logs maximum size error
setUp              : get clc
test               : use "nc" to open a TCP connection to the DNS service and send message that exceeds 1024 bytes
                     and check for unwanted error..
tearDown           : cleanup artifacts

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops


class EucaTest(unittest.TestCase):
    def setUp(self):
        self.conf = "cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.clc1 = self.tester.service_manager.get_enabled_clc()

    def tearDown(self):
        self.tester.cleanup_artifacts()
        shutil.rmtree(self.tester.credpath)

    def check_for_error_msg(self, error):
        self.logFile = self.tester.eucapath + "/var/log/eucalyptus/cloud-error.log"
        if self.clc1.machine.found(" grep " + error + " " + self.logFile, error) :
            self.fail("FAILURE! Maximum message size exceeded. error thrown.")
        else : self.tester.debug("SUCCESS! No error logged!")

    def test(self):
      # send message that excceeds 1024 bytes (admin_cred.zip could be any file that exceeds 1024 bytes)
      self.tester.sys("nc " + str(self.tester.clc.hostname) + " 53 <  admin_cred.zip" )
      # Check make sure error is not there.
      self.check_for_error_msg("Maximum message size exceeded. Ignoring request.")

if __name__ == "__main__":
    unittest.main()