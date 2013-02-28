#!/usr/bin/python
'''
Created on Jan 28, 2013
@author: mmunn
Unit test          : EUCA-4128 euca-describe-volumes (verbose) takes a long time to return with results
setUp              : Install Credentials,
test               : Starts 4 instances and creates 85 volumes. It then calls euca-describe-volumes 10
                     times and returns the average execution time.
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
import time
from eucaops import Eucaops

class Euca4128(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud2.conf"       
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.cond = 1 
        self.doAuth()

    def tearDown(self):
        #self.tester.cleanup_artifacts() 
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath) 
         
    def runInstances(self):
        #Start instance
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group, min=4, max=4, is_reachable=False)
        # Make sure the instance is running       
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.ip = instance.public_dns_name
                self.instanceid = instance.id
                
    def runSysCmd(self, cmd):
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.out = self.tester.sys(self.source + cmd) 
         
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def testName(self):
        #self.emi = self.tester.get_emi()
        #self.zone = self.tester.get_zones().pop()
        #self.runInstances()
        #self.tester.create_volumes(self.zone, count=85)
        self.total = 0
        i = 0
        while i < 10 :
            i += 1
            self.startTime = time.time()
            self.runSysCmd("euca-describe-volumes")
            self.time = time.time() - self.startTime
            self.total += self.time
            
        print self.total / 10
        
if __name__ == "__main__":
    unittest.main("Euca4128")
    