#!/usr/bin/python
from testcases.cloud_user.instances.instancetest import InstanceBasics
from testcases.cloud_user.s3.bucket_tests import BucketTestSuite
from eucaops import Eucaops

class GatherDebug(InstanceBasics, BucketTestSuite):
    basic_commands = ['df -B M',
                      'ps aux',
                      'free',
                      'uptime']
    network_commands = ['iptables -L',
                        'iptables -L -t nat',
                        'arp -a',
                        'ip addr show',
                        'ifconfig',
                        'brctl show',
                        'route',
                        'netstat -lnp']

    euca_commands = ['cat /etc/eucalyptus/eucalyptus.conf | grep -v \'#\' ',
                     'cat /etc/eucalyptus/eucalyptus-version',
                     'ps aux | grep euca']

    clc_commands = ['euca-describe-services -E -A',
                    'euca-describe-availability-zones verbose',
                    'euca-describe-instances verbose',
                    'euca-describe-volumes verbose',
                    'euca-describe-snapshots verbose',
                    'euca-describe-keypairs verbose',
                    'euca-describe-groups verbose']
    
    sc_commands = ['ls -l /dev/',
                   'losetup -a',
                   'service tgtd status'
                   'tgtadm --lld iscsi --mode target --op show',
                   'service iscsid status'
                   'iscsiadm -m session -P 3',
                   'pvdisplay',
                   'lvdisplay',
                   'vgdisplay',
                   'mpathconf',
                   'multipath -ll']
    
    nc_commands = ['service iscsid status',
                   'iscsiadm -m session -P 3',                   
                   'mpathconf',
                   'multipath -ll',
                   'virsh list',
                   'losetup -a',
                   'dmsetup status',
                   'll /var/lib/eucalyptus/instances/**/**/**']
                   

    def __init__(self, config_file="cloud.conf", password="foobar"):
        self.tester = Eucaops( config_file=config_file, password=password)
        self.servman = self.tester.service_manager

    def run_command_list(self,machine, list):
        for command in list:
            machine.sys(command)

    def debug_clc(self, **kwargs):
        clc_commands = self.basic_commands + self.network_commands + self.euca_commands + self.clc_commands
        for machine in self.tester.get_component_machines("clc"):
            for command in clc_commands:
                machine.sys("source " + self.tester.credpath + "/eucarc && " + command)

        for account in self.tester.get_all_accounts():
            account_name = next((value for key, value in account.iteritems() if 'account_name' in key), None)
            self.tester.debug( "## Account Name: " + account_name )
            for user in self.tester.get_users_from_account(delegate_account=account_name):
                user_name = next((value for key, value in user.iteritems() if 'user_name' in key), None)
                self.tester.debug( "### User Name: " + user_name )
                for policy in self.tester.get_user_policies(user_name, delegate_account=account_name):
                    self.tester.debug( "#### User " + user_name + " Policy ####" )
                    for key, value in policy.iteritems():
                        self.tester.debug( key + ": " + value )

            for group in self.tester.get_all_groups(account_name=account_name):
                group_name = next((value for key, value in group.iteritems() if 'group_name' in key), None)
                self.tester.debug( "### Group Name: " + group_name )
                for policy in self.tester.get_group_policies(group_name, delegate_account=account_name):
                    self.tester.debug( "#### Group " + group_name + " Policy ####" )
                    for key, value in policy.iteritems():
                        self.tester.debug( key + ": " + value )

    def debug_walrus(self, **kwargs):
        walrus_commands = self.basic_commands + self.network_commands + self.euca_commands
        for machine in self.tester.get_component_machines("ws"):
            self.run_command_list(machine,walrus_commands)

    def debug_cc(self, **kwargs):
        cc_commands = self.basic_commands + self.network_commands + self.euca_commands
        for machine in self.tester.get_component_machines("cc"):
            self.run_command_list(machine,cc_commands)

    def debug_sc(self, **kwargs):
        sc_commands = self.basic_commands + self.network_commands + self.euca_commands + self.sc_commands
        for machine in self.tester.get_component_machines("sc"):
            self.run_command_list(machine,sc_commands)

    def debug_nc(self, **kwargs):
        nc_commands = self.basic_commands + self.network_commands + self.euca_commands + self.nc_commands
        for machine in self.tester.get_component_machines("nc"):
            self.run_command_list(machine,nc_commands)

    def run_testcase(self, testcase_callback, **kwargs):
        poll_count = 20
        poll_interval = 20
        while poll_count > 0:
            try:
                testcase_callback(**kwargs)
                break
            except Exception, e:
                self.tester.debug("Attempt failed due to: " + str(e)  + "\nRetrying testcase in " + str(poll_interval) )
            self.tester.sleep(poll_interval)
            poll_count = poll_count - 1
        if poll_count is 0:
            self.fail("Could not run an instance after " + str(poll_count) +" tries with " + str(poll_interval) + "s sleep in between")

    def cleanup(self):
        pass

    def run_suite(self):
        self.testlist = []
        testlist = self.testlist
        testlist.append(self.create_testcase_from_method(self.debug_clc))
        testlist.append(self.create_testcase_from_method(self.debug_walrus))
        testlist.append(self.create_testcase_from_method(self.debug_cc))
        testlist.append(self.create_testcase_from_method(self.debug_sc))
        testlist.append(self.create_testcase_from_method(self.debug_sc))
        self.run_test_case_list(testlist)
        self.cleanup()

if __name__ == "__main__":
    parser = GatherDebug.get_parser()
    args = parser.parse_args()
    debugsuite = GatherDebug(config_file=args.config, password = args.password)
    debugsuite.run_suite()
   
