'''
Created on Mar 18, 2013
@author: mmunn
Unit test          : EUCA-4229  After hitting maximum snapshot limit the cloud still sees snapshots
setUp              : Install Credentials,
test               : Set the storagemaxtotalsnapshotsizeingb to 1GB, try and create a 2G snapshot (this throws an EntityTooLargeException)
                     and make sure the failes snapshot metadata does show up in euca-describe-snapshots output.
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
import eutester.euproperties
from eucaops import Eucaops
from eutester.euproperties import Euproperty_Manager

class Euca4229(unittest.TestCase):

    def setUp(self):
        self.conf = "cloud.conf" 
        self.cond = 0
        self.tester  = Eucaops( config_file=self.conf, password="foobar" )
        self.doAuth()
        self.sbin = self.tester.eucapath + "/usr/sbin/"
        self.source  = "source " + self.tester.credpath + "/eucarc && "

    def tearDown(self):
        self.tester.sys(self.source + self.sbin + "euca-modify-property -p walrus.storagemaxtotalsnapshotsizeingb=50")
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
                self.ip = instance.public_dns_name
                self.instanceid = instance.id

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)

    def testEuca4229(self):
        # Get availibility zone
        self.zone = self.tester.get_zones().pop()
        # Get number of already existing snapshots:
        self.num_snaps_before = str(self.tester.sys(self.source + "euca-describe-snapshots")).count("SNAPSHOT")
        # Set storagemaxtotalsnapshotsizeingb 
        self.tester.sys(self.source + self.sbin + "euca-modify-property -p walrus.storagemaxtotalsnapshotsizeingb=1")
        # create volume larger than storagemaxtotalsnapshotsizeingb = 1GB
        self.volume = self.tester.create_volume(self.zone, 2, timeout=100)
        # make sure the exception is thrown 
        try:
            self.snap = self.tester.create_snapshot(self.volume.id, description="snap-4229")
        except Exception as detail:
            self.cond = str(detail).count('maximum allowed object size')
        # Get the current number of snapshots
        self.num_snaps_after = str(self.tester.sys(self.source + "euca-describe-snapshots")).count("SNAPSHOT")
        # Check to see if the the error was thrown and make sure no new snapshot-matadata was created
        if self.cond >= 1 and self.num_snaps_after == self.num_snaps_before :
            self.tester.debug("SUCCESS no new snapshot-metadata")
            pass
        else:
            self.fail("FAIL new snapshot-metadata")
if __name__ == "__main__":
    unittest.main("Euca4229")
    