'''
Created on = '10/28/13"
Author = 'mmunn'

Unit test          :
setUp              : Install Credentials,
test               :
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
        self.STARTC = '\033[1m\033[1m\033[42m'
        self.ENDC = '\033[0m'

    def tearDown(self):
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

    def runInstances(self, numMax):
        self.emi = self.tester.get_emi()
        #Start instance
        self.reservation = self.tester.run_instance(self.emi, keypair=self.keypair.name, group=self.group, min=1, max=numMax,
                                                    is_reachable=False)
        # Make sure the instance is running
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.ip = instance.public_dns_name
                self.instanceid = instance.id

    def runSysCmd(self, cmd):
        self.source =  'export EUCALYPTUS=' + self.tester.eucapath + " && source " + self.tester.credpath + "/eucarc && "  + self.tester.eucapath + "/usr/sbin/"
        self.out = self.tester.sys(self.source + cmd)

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def test(self):
        self.runSysCmd('euca-describe-components')
        count = str(self.out).count("PRIMORDIAL")
        print self.STARTC + " The number of components listed in the PRIMORDIAL state = " + str(count) + self.ENDC
        #Fail if there are any components listed in the PRIMORDIAL state
        if count == 0 :
            self.tester.debug("SUCCESS")
            pass
        else:
            self.fail("FAILED : components listed in the PRIMORDIAL state")

if __name__ == "__main__":
    unittest.main()