'''
Created on Jan 31, 2013
@author: mmunn
Unit test          : EUCA-3456 euca-describe-nodes does not return consistent results
setUp              : Install Credentials, 
test               : run 24 instances on 6 nodes then call euca_conf --list-nodes and count the number of nodes listed.
tearDown           : Removes Credentials, does not terminate instances

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC01] [NC02] [NC03] [NC04] [NC05] [NC06] 
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca3456(unittest.TestCase):

    def setUp(self):
        #This bug is intermittent.
        #To reproduce this consistently I used 6 nodes 24 instances and 50 iterations
        #These can be adjusted, the more nodes and instances the quicker you will see the problem.
        #runInstances is run twice for a total of (2 * numIntances ) this done
        #to avoid out of resources error.
        self.numNodes = 6
        self.numIntances = 12
        self.numIterations = 1
        self.conf = "cloud.conf"       
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.doAuth()

    def tearDown(self):
        #self.tester.cleanup_artifacts() 
        self.tester.delete_keypair(self.keypair)
        self.tester.local("rm " + self.keypair.name + ".pem") 
        shutil.rmtree(self.tester.credpath) 
         
    def runInstances(self, numMax):
        #Start instance
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, group=self.group, min=0, max=numMax, is_reachable=False, timeout=480)
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

    def testDescribeNodes(self):
        self.emi = self.tester.get_emi()
        self.runInstances(self.numIntances)
        #self.runInstances(self.numIntances)
        i = 0
        while i < self.numIterations :
            i += 1
            self.tester.debug("Running iteration " + str(i))
            self.runSysCmd("/opt/eucalyptus/usr/sbin/euca_conf --list-nodes")
            #count the returned nodes
            count = str(self.out).count("NODE")
            if count != self.numNodes :
                self.tester.debug("FAILURE only " + str(count) + " nodes listed.")
                self.fail("FAIL Incorrect number of nodes listed!")
            else :             
                self.tester.debug("SUCCESS " + str(count) + " nodes listed.")
                pass
            
if __name__ == "__main__":
    unittest.main("Euca3456")
    