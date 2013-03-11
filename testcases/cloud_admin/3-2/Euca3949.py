'''
Created on Mar 7, 2013
@author: mmunn
Unit test          : EUCA-3949 Log message org.hibernate.PersistentObjectException
setUp              : Install Credentials,
test               : start and terminate an instance and check for org.hibernate.PersistentObjectException
tearDown           : Removes Credentials,

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca3949(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf" 
        self.cond = 1     
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.doAuth()
        self.clc1 = self.tester.service_manager.get_enabled_clc()
        self.IP = self.tester.get_ec2_ip()

    def tearDown(self):
        self.tester.cleanup_artifacts() 
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath) 
         
    def runInstances(self, numMax):
        #Start instance
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group, min=1, max=numMax, is_reachable=False)
        # Make sure the instance is running       
        for instance in self.reservation.instances:
            if instance.state == "running":
                self.instance = instance
                
    def runSysCmd(self, cmd):
        self.source  = "source " + self.tester.credpath + "/eucarc && "
        self.out = self.tester.sys(self.source + cmd) 
         
    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)
        
    def check_for_error_msg(self, error):
        self.logFile = self.tester.eucapath + "/var/log/eucalyptus/cloud-output.log"
        if self.clc1.machine.found(" grep " + error + " " + self.logFile, error) :
            self.fail("FAILURE! PersistentObjectException error thrown.")
        else : self.tester.debug("SUCCESS! No confusing error logged!")

    def testName(self):
        self.emi = self.tester.get_emi()
        self.runInstances(1)
        self.tester.terminate_single_instance(self.instance)
        self.runSysCmd("euca-describe-instances")
        #check log file to see if PersistentObjectException error was thrown
        self.check_for_error_msg("PersistentObjectException")

        pass
        
if __name__ == "__main__":
    unittest.main("Euca3949")
    