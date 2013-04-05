#!/usr/bin/python
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase

class GatherDebug(EutesterTestCase):
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
                   

    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config_file, password=self.args.password,download_creds=True)

    def clean_method(self):
        pass

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

    def cleanup(self):
        pass

    def DebugAll(self):
        self.debug_clc()
        self.debug_walrus()
        self.debug_cc()
        self.debug_sc()
        self.debug_sc()


if __name__ == "__main__":
    testcase = GatherDebug()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list  "VolumeTagging", "InstanceTagging", "SnapshotTagging", "ImageTagging"
    list = testcase.args.tests or ["DebugAll"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
   
