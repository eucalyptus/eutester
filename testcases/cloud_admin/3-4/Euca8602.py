'''
Created on = '1/28/14"
Author = 'mmunn'

Unit test          : EUCA-8602 AWS and Euca differ in response to run-instances and describe-instances, when no keypair is specified for instance
setUp              : Install Credentials,
test               : run both euca-describe-instances --debug and euca-run-instances instanceId --debug and make sure
                     that the <keypair/> tag is not included in the response.
tearDown           : Removes Credentials, terminates instance

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

    def tearDown(self):
        self.tester.cleanup_artifacts()
        self.runSysCmd("euca-terminate-instances " + self.instanceid)
        shutil.rmtree(self.tester.credpath)

    def runSysCmd(self, cmd):
        self.source = "source " + self.tester.credpath + "/eucarc && "
        self.out = self.tester.sys(self.source + cmd)

    def test(self):
        self.emi = self.tester.get_emi()
        self.runSysCmd("euca-run-instances --debug " + self.emi.id )
        self.count1 = str(self.out).count('<keypair/>')
        self.runSysCmd("euca-describe-instances --debug ")
        self.count2 = str(self.out).count('<keypair/>')
        self.instanceid = str(self.tester.get_last_instance_id())

        # Make sure <keypair/> in not in either response
        assert self.count1 == 0 and self.count2 == 0

if __name__ == "__main__":
    unittest.main()