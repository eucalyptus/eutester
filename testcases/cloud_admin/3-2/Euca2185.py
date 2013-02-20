'''
Created on Oct 10, 2012
@author: mmunn
Unit test          : EUCA-2185 DescribeInstances api call does not return ip addresses
setUp              : Install Credentials, set use_instance_dns
test               : Call euca-describe-instances with use_instance_dns=true and make 
                     sure the instance ip is not the same as the instance dns name
                     in the returned string
tearDown           : Removes Credentials, terminates instance, reset use_instance_dns

cloud.conf:( place in same directory as this test)
IP_ADDRESS   CENTOS  6.3     64      BZR     [CLC]
IP_ADDRESS   CENTOS  6.3     64      BZR     [WS]
IP_ADDRESS   CENTOS  6.3     64      BZR     [CC00 SC00]
IP_ADDRESS   CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca2185(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf"      
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.clc1 = self.tester.service_manager.get_enabled_clc()
        # Enable DNS
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.sbin = self.tester.eucapath + "/usr/sbin/"
        self.cmd = "euca-modify-property -p bootstrap.webservices.use_instance_dns="
        self.tester.sys(self.source + self.sbin + self.cmd + "true")
        self.doAuth()

    def tearDown(self):
        # Restore default dns  
        self.tester.sys(self.source + self.sbin + self.cmd + "false")  
        self.tester.cleanup_artifacts() 
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath)  
    
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def testName(self):

        self.emi = self.tester.get_emi()
        # Start instance
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group, is_reachable=False)
        # Make sure the instance is running       
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.dns = instance.public_dns_name
                self.instanceid = instance.id
                
        self.out = self.tester.sys(self.source + "euca-describe-instances " + self.instanceid)
        # Count the number of times the public dns is in the return string
        self.count = str(self.out).count(str(self.dns))
        # The public dns name should only be listed once with the fix not twice
        if self.count==1:
            pass
        else:
            self.fail(" euca-describe-instances instance ip=" + self.dns)
            
if __name__ == "__main__":
    unittest.main("Euca2185")
