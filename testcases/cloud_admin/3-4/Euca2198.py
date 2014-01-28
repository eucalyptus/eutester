'''
Created on 8/21/13
Author: mmunn

Unit test          : EUCA-2198 Walrus should not appear in DescribeRegionsResponses
setUp              : Install Credentials,
test               : run euca-describe-regions and make sure walrus is not listed.
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops


class Euca2198(unittest.TestCase):
    def setUp(self):
        self.conf = "cloud.conf"
        self.tester = Eucaops(config_file=self.conf, password="foobar")
        self.doAuth()
        self.OK = '\033[1m\033[37m\033[42m'
        self.ENDC = '\033[0m'


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
        self.runSysCmd('euca-describe-regions')
        if not str(self.out).count('Walrus'):
           print self.OK + str(self.out) + self.ENDC
        else : self.fail( 'Walrus listed in output')

if __name__ == "__main__":
    unittest.main()