'''
Created on Dec 19, 2012
@author: mmunn
Unit test          : EUCA-4268 RebootInstances does not work on multiple instances
setUp              : Install Credentials,
test               : reboot two instances and ping them to make sure both were rebooted
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca4268(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"       
        self.tester = Eucaops( config_file=self.conf, password="foobar" )
        self.cond = 1 
        self.doAuth()

    def tearDown(self):
        self.tester.cleanup_artifacts() 
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath) 
         
    def runInstances(self):
        #Start instance
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group,min=2,max=2,is_reachable=False)
        # Make sure the instance is running       
        self.count = 0;
        for instance in self.reservation.instances:
            self.count += 1
            if instance.state == "running":
                if self.count == 1 :
                    self.ip_one = instance.public_dns_name
                    self.instanceid_one = instance.id
                else:
                    self.ip_two = instance.public_dns_name
                    self.instanceid_two = instance.id
                    
    def runSysCmd(self, cmd):
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.out = self.tester.sys(self.source + cmd) 
         
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)
        self.tester.authorize_group(self.group, port=-1, protocol="icmp")

    def testName(self):
        self.runInstances()
        self.tester.ping(self.ip_one, 1)
        self.tester.ping(self.ip_two, 1)
        #make sure instance is reachable
        self.cmd = 'euca-reboot-instances ' + self.instanceid_one + " " + self.instanceid_two
        self.runSysCmd(self.cmd)
        #wait for reboot
        self.tester.sleep(2)
        self.pingable1 = self.tester.ping(self.ip_one, 1)
        self.pingable2 = self.tester.ping(self.ip_two, 1)
        
        if self.pingable1 == False and self.pingable2 == False :
            self.tester.debug("SUCCESS both instances were rebooted")
            pass
        else:
            self.fail("FAIL both instances not rebooted")
        
if __name__ == "__main__":
    unittest.main("Euca4268")
    