'''
Created on = '7/28/14'
Author = 'mmunn'

Unit test          : EUCA-9729 euscale-create-auto-scaling-group does not always honor ec2:quota-vminstancenumber
setUp              : Install Credentials,
test               : Create Account, upload Quota policy where ec2:quota-vminstancenumber":"3, try and launch 4
                     autoscaling instances, the quota should only allow 3 instsances to be started.
tearDown           : Cleanup artifacts

cloud.conf:( place in same directory as this test)
IP ADDRESS CENTOS  6.5     64      BZR     [CC00 CLC SC00 WS]
IP ADDRESS CENTOS  6.5     64      BZR     [NC00]
'''
import unittest
import os
from eucaops import Eucaops


class EucaTest(unittest.TestCase):
    def setUp(self):
        self.conf = 'cloud.conf'
        self.tester = Eucaops(config_file=self.conf, password='foobar')
        self.STARTC = '\033[1m\033[1m\033[42m'
        self.ENDC = '\033[0m'
        self.acct_name='testacct'
        self.acct_dir='/root/' + self.acct_name
        self.asg_instance_count = 'euscale-describe-auto-scaling-instances | grep -c INSTANCE'
        self.asg_name='testScaling'
        self.quota=3

    def tearDown(self):
        self.runTestCmd('euscale-delete-policy -g ' + self.asg_name + ' shutdown')
        self.runTestCmd('euscale-delete-auto-scaling-group ' + self.asg_name +' --force-delete')
        self.runTestCmd('euscale-delete-launch-config testLaunch')
        self.tester.delete_account(self.acct_name,recursive=True)
        self.runSysCmd('rm -rf testacct')

    def runSysCmd(self, cmd):
        self.source = 'source ' + self.tester.credpath + '/eucarc && '
        self.out = self.tester.sys(self.source + cmd)

    def runTestCmd(self, cmd):
        self.source = 'source ' +  self.acct_dir + '/eucarc && '
        self.out = self.tester.sys(self.source + cmd)

    def wait_for_asg_instances_to_stop(self):
        count = self.quota
        while (count > 0):
            self.tester.debug('Waiting for all instances to stop, still running = ' + str(count))
            self.tester.sleep(10)
            self.runTestCmd(self.asg_instance_count)
            count = int(self.out[0])

    def wait_for_asg_instances_to_start(self):
        count = 0
        while (count < self.quota):
            self.tester.debug('Waiting for Quota instances to start, count = ' + str(count))
            self.tester.sleep(10)
            self.runTestCmd(self.asg_instance_count)
            count = int(self.out[0])

    def test(self):
        self.emi = self.tester.get_emi()
        self.clc_ip = str(self.tester.clc.hostname)
        self.tester.create_account(self.acct_name)
        self.runSysCmd('mkdir ' + self.acct_dir)
        self.runSysCmd('/opt/eucalyptus/usr/sbin/euca_conf --cred-account ' + self.acct_name + ' --cred-user admin --get-credentials ' + self.acct_dir + '/' + self.acct_name + '.zip')
        os.system('scp test_policy.txt root@' + self.clc_ip + ':' + self.acct_name)
        self.runSysCmd('euare-accountuploadpolicy -a ' + self.acct_name + ' -p test-quota -f ' + self.acct_dir + '/test_policy.txt')
        self.runSysCmd('cd ' +  self.acct_dir + ' && unzip -o ' + self.acct_dir + '/' + self.acct_name + '.zip')
        self.runTestCmd('euca-create-keypair ' + self.acct_name + ' > ' + self.acct_dir + '/' + self.acct_name + '.private')
        self.runTestCmd(self.asg_instance_count)
        self.tester.debug(self.STARTC + 'Original Count = ' + str(self.out[0]) + self.ENDC)
        self.runTestCmd('euscale-create-launch-config testLaunch -t m1.small --key ' + self.acct_name + ' --group default --image ' + self.emi.id )
        self.runTestCmd('euscale-create-auto-scaling-group -l testLaunch -m 0 -M 4 --desired-capacity 4 -z PARTI00 '  + self.asg_name)
        # Wait for AS instances to launch
        self.wait_for_asg_instances_to_start()
        # Check number of AS Instances started.
        self.runTestCmd(self.asg_instance_count)
        assert int(self.out[0]) == self.quota
        self.tester.debug(self.STARTC + 'Success Quota = 3 number of ASG instances started = ' + str(self.out[0]) + self.ENDC)
        self.runTestCmd('euscale-put-scaling-policy shutdown -g ' + self.asg_name + ' -a -4 -t ChangeInCapacity ')
        self.runTestCmd('euscale-execute-policy shutdown -g ' + self.asg_name)
        self.wait_for_asg_instances_to_stop()

if __name__ == '__main__':
    unittest.main()