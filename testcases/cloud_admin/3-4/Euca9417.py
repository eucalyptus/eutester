'''
Created on = '6/3/14"
Author = 'mmunn'

Unit test          : EUCA-9417 canonical ID replaced by NULL value after upgrade from 3.3.2 to 3.4.2
                     after an upgrade from 3.3 3.4 this checks to make sure the canonical ID is not null
setUp              : Install Credentials,
test               : Upgrade from 3.3 to 3.4 then run this test. ( this will always fail on 3.3 )
tearDown           : Cleanup artifacts

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
        self.doAuth()
        self.STARTC = '\033[1m\033[1m\033[42m'
        self.ENDC = '\033[0m'

    def tearDown(self):
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def test(self):
        canonicalID = str(self.tester.s3.get_canonical_user_id())
        count = len(canonicalID)
        print self.STARTC + "canonicalId = " + canonicalID + self.ENDC
        print self.STARTC + "canonicalId size = " + str(count) + self.ENDC
        # make sure it is valid 64 character canonicalID
        if count == 64 :
            self.tester.debug("SUCCESS")
            pass
        else:
            self.fail("FAIL")




if __name__ == "__main__":

    unittest.main()