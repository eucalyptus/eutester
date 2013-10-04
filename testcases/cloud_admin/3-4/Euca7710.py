'''
Created on = '10/1/13'
Author = 'mmunn'

Unit test          : EUCA-7710 missing input validation on CLC
setUp              : Install Credentials, starts instance
test               : run euca-bundle-instance, euca-attach-volume and euca-dettach-volume with bad input parameters
                     for bucket,prefix and device
tearDown           : Removes Credentials, terminates instance

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.3     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.3     64      BZR     [NC00]
'''
import unittest
import shutil
from eucaops import Eucaops

class Euca7710(unittest.TestCase):

    def setUp(self):
        self.OK = '\033[1m\033[37m\033[42m'
        self.ENDC = '\033[0m'
        self.conf = 'cloud.conf'
        self.tester  = Eucaops( config_file=self.conf, password='foobar' )
        self.source  = 'source ' + self.tester.credpath + '/eucarc && '
        self.clc1 = self.tester.service_manager.get_enabled_clc()
        self.doAuth()

    def doAuth(self):
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        self.tester.authorize_group(self.group)
        self.tester.authorize_group(self.group, port=3389, protocol='tcp')
        self.skey = self.tester.get_secret_key()
        self.akey = self.tester.get_access_key()

    def runInstances(self, numMax):
        #Start instance
        self.reservation = self.tester.run_instance(self.emi,type='m1.large', keypair=self.keypair.name, group=self.group, min=1, max=numMax, is_reachable=False)
        # Make sure the instance is running
        for instance in self.reservation.instances:
            if instance.state == 'running':
                self.instance = instance
                self.instanceid = instance.id

    def runCmdTest (self, cmd):
        self.out = self.clc1.machine.cmd(self.source + self.cmd)
        print self.OK + self.out['output'] + self.ENDC
        # make sure InvalidParameterValue error was thrown
        assert str(self.out).count('InvalidParameterValue') > 0

    def test(self):
        self.emi = self.tester.get_emi()
        self.runInstances(1)
        # Attempt to bundle the running instance with invalid parameters
        # regex used to validate bucket and prefix parameters = ( ^[a-zA-Z\d\.\-_]{3,255}$ )
        # two few chars
        self.badBucket = 'xx'
        # invalid char
        self.badPrefix = 'xx$'

        self.cmd = 'euca-bundle-instance ' + self.instanceid + ' -b ' + self.badBucket + ' -p goodPrefix -o ' + self.akey + ' -w ' + self.skey
        self.runCmdTest(self.cmd)
        self.cmd = 'euca-bundle-instance ' + self.instanceid + ' -b goodBucket -p ' + self.badPrefix + ' -o ' + self.akey + ' -w ' + self.skey
        self.runCmdTest(self.cmd)

        # Attempt  to attach and detach volume with invalid device name
        # regex used to device parameter = ( ^[a-zA-Z\d/]{3,10}$ )
        self.volume = 'vol-BOGUS1'
        # invalid char
        self.badDevice1 = 'sd$'
        # invalid name too long
        self.badDevice2 = 'sdistoolong'
        self.cmd = 'euca-attach-volume -i ' + self.instanceid + ' -d ' + self.badDevice1 + ' ' + self.volume
        self.runCmdTest(self.cmd)
        self.cmd = 'euca-attach-volume -i ' + self.instanceid + ' -d ' + self.badDevice1 + ' ' + self.volume
        self.runCmdTest(self.cmd)
        self.cmd = 'euca-detach-volume -i ' + self.instanceid + ' -d ' + self.badDevice1 + ' ' + self.volume
        self.runCmdTest(self.cmd)
        self.cmd = 'euca-detach-volume -i ' + self.instanceid + ' -d ' + self.badDevice1 + ' ' + self.volume
        self.runCmdTest(self.cmd)

    def tearDown(self):
        if self.reservation is not None:
            self.tester.terminate_instances(self.reservation)
        self.tester.delete_keypair(self.keypair)
        self.tester.local('rm ' + self.keypair.name + '.pem')
        shutil.rmtree(self.tester.credpath)

if __name__ == '__main__':
    unittest.main()