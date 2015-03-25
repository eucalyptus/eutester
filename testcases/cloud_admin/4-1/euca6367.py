'''
Created on = '10/28/13"
Author = 'mmunn'

Unit test          : EUCA-6367 plea for a nice error message for euca-migrate-instances
setUp              : Install Credentials,
test               : Start and attemt tp migrate an instance to the same node, check for correct error.
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
        self.source_nc = ""

    def tearDown(self):
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem")
        shutil.rmtree(self.tester.credpath)

    def runInstances(self, numMax):
        self.emi = self.tester.get_emi()
        # Start instance
        self.reservation = self.tester.run_instance(self.emi, keypair=self.keypair.name, group=self.group, min=1,max=numMax,is_reachable=False)
        # Make sure the instance is running
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.ip = instance.public_dns_name
                self.instanceid = instance.id

    def runSysCmd(self, cmd):
        self.source = 'export EUCALYPTUS=' + self.tester.eucapath + " && source " + self.tester.credpath + "/eucarc && " + self.tester.eucapath + "/usr/sbin/"
        self.out = self.tester.sys(self.source + cmd)

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def test(self):
        # Start an instance
        self.runInstances(1)
        # Find the node that the new instance is running on
        self.tester.service_manager.populate_nodes()
        self.source_nc = self.tester.service_manager.get_all_node_controllers(instance_id=self.instanceid)[0]
        print self.STARTC + "InstanceID=" + self.instanceid + " Node IP=" + str(self.source_nc.hostname) + self.ENDC
        # Try and migrate our instance to the same node and it should fail
        self.runSysCmd('euca-migrate-instances -i ' + str(self.instanceid) + ' --dest ' +  str(self.source_nc.hostname))
        #Check for the correct error message
        count = str(self.out).count("source and destination cannot be the same")
        if count == 1 :
            self.tester.debug("SUCCESS")
            pass
        else:
            self.fail("FAILED : Correct error message not thrown")

if __name__ == "__main__":
    unittest.main()
