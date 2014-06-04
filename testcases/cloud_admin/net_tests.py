#!/usr/bin/python
# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author:
__author__ =  'matt.clark@eucalyptus.com'
'''
Test case class to test points of network security groups
See individual test descriptions for test objectives.
test1:
    Definition:
        Create test instances within each zone within security group1. This security group is authorized for
        ssh access from 0.0.0.0/0.
        This test attempts the following:
            -To run an instance in each zone and confirm it reaches 'running' state.
            -Confirm the instance is ping-able from the cc within a given timeout
            -Establish and verify an ssh session directly from the local machine running this test.
            -Place ssh key on instance for later use
            -Add instance to global 'group1_instances'

test2:
    Definition:
        This test attempts to create an instance in each within security group2 which should not
        be authorized for any remote access (outside of the CC).
        The test attempts the following:
            -To run an instance in each zone and confirm it reaches 'running' state.
            -Confirm the instance is ping-able from the cc within a given timeout
            -Establish and verify an ssh session using the cc as a proxy.
            -Place ssh key on instance for later use
            -Add instance to global 'group2_instances'

test3:
    Definition:
        This test attempts to set up security group rules between group1 and group2 to authorize group2 access
        from group1. If use_cidr is True security groups will be setup using cidr notication ip/mask for each instance in
        group1, otherwise the entire source group 1 will authorized.
        the group will be
        Test attempts to:
            -Authorize security groups for inter group private ip access.
            -Iterate through each zone and attempt to ssh from an instance in group1 to an instance in group2 over their
                private ips.

test4:
    Definition:
        Test attempts to verify that the local machine cannot ssh to the instances within group2 which is not authorized
        for ssh access from this source.

test5 (Multi-zone/cluster env):
    Definition:
        This test attempts to check connectivity for instances in the same security group, but in different zones.
        Note: This test requires the CC have tunnelling enabled, or the CCs in each zone be on same
        layer 2 network segment.
        Test attempts to:
            -Iterate through each zone and attempt to ssh from an instance in group1 to an instance in a separate zone
             but same security group1 over their private ips.

test 6 (Multi-zone/cluster env):
    Definition:
        This test attempts to set up security group rules between group1 and group2 to authorize group2 access
        from group1 across different zones.
        If no_cidr is True security groups will be setup using cidr notication ip/mask for each instance in
        group1, otherwise the entire source group 1 will authorized.
        the group will be
        Note: This test requires the CC have tunnelling enabled, or the CCs in each zone be on same
        layer 2 network segment.
        Test attempts to:
            -Authorize security groups for inter group private ip access.
            -Iterate through each zone and attempt to ssh from an instance in group1 to an instance in group2 over their
             private ips.


'''

#todo: Make use of CC optional so test can be run with only creds and non-admin user.
# CC only provides additional point of debug so can be removed from test for non-euca testing
#todo: Allow test to run with an admin and non-admin account, so debug can be provided through admin and test can
# be run under non-admin if desired.


from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import SkipTestException
from eutester.euinstance import EuInstance
from eutester.sshconnection import SshConnection
import time
import os
import sys
import copy


class Net_Tests(EutesterTestCase):

    def __init__(self,  tester=None, **kwargs):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--no_cidr",
                                 action='store_false',
                                 help="Boolean to authorize sec group with cidr notation or by group ",
                                 default=True)
        self.parser.add_argument("--freeze_on_fail",
                                 action='store_true',
                                 help="Boolean flag to avoid cleaning test resources upon failure, default: True ",
                                 default=False)
        '''
        self.parser.add_argument('--user',
                                 default='Admin',
                                 help='User to run this test as')
        self.parser.add_argument("--account",
                                 help="Account to run this as",
                                 default=None)
        '''
        self.tester = tester
        self.get_args()
        # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        self.show_args()
        ### Create the Eucaops object, by default this will be Eucalyptus/Admin and have ssh access to components
        if not tester and not self.args.config:
            print "Need eutester config file to execute this test. As well as system ssh credentials (key, password, etc)"
            self.parser.print_help()
            sys.exit(1)
        # Setup basic eutester object
        if not self.tester:
            try:
                self.debug('Creating Eucaops tester object from args provided...')
                self.tester = self.do_with_args(Eucaops)
            except Exception, e:
                raise Exception('Couldnt create Eucaops tester object, make sure credpath, '
                                'or config_file and password was provided, err:' + str(e))
                #replace default eutester debugger with eutestcase's for more verbosity...
            self.tester.debug = lambda msg: self.debug(msg, traceback=2, linebyline=False)
        assert isinstance(self.tester, Eucaops)
        self.cc_last_checked = time.time()

        ### Create local zone list to run tests in
        if self.args.zone:
            self.zones = [str(self.args.zone)]
        else:
            self.zones = self.tester.get_zones()
        if not self.zones:
            raise Exception('No zones found to run this test?')
        self.debug('Running test against zones:' + ",".join(self.zones))

        ### Add and authorize securtiy groups
        self.debug("Creating group1..")
        self.group1 = self.tester.add_group(str(self.name) + "_group1_" + str(time.time()))
        self.debug("Authorize ssh for group1 from '0.0.0.0/0'")
        self.tester.authorize_group(self.group1, port=22, protocol='tcp', cidr_ip='0.0.0.0/0')
        #self.tester.authorize_group(self.group1, protocol='icmp',port='-1')

        self.debug("Creating group2, will authorize later from rules within test methods..")
        self.group2 = self.tester.add_group(str(self.name) + "_group2_" + str(time.time()))
        self.group1_instances = []
        self.group2_instances = []



        ### Generate a keypair for the instances
        try:
            keys = self.tester.get_all_current_local_keys()
            if keys:
                self.keypair = keys[0]
            else:
                self.keypair = self.tester.add_keypair(str(self.name) + "_key_" + str(time.time()))
        except Exception, ke:
            raise Exception("Failed to find/create a keypair, error:" + str(ke))

        ### Get an image to work with
        if self.args.emi:
            self.image = self.tester.get_emi(emi=str(self.args.emi))
        else:
            self.image = self.tester.get_emi(root_device_type="instance-store")
        if not self.image:
            raise Exception('couldnt find instance store image')




    ######################################################
    #   Test Utility Methods
    ######################################################

    def authorize_group_for_instance_list(self, group, instances):
        for instance in instances:
            assert isinstance(instance, EuInstance)
            self.tester.authorize_group(group, cidr_ip=instance.private_ip_address + "/32")

    def clean_method(self):
        if self.args.freeze_on_fail:
            self.status('freeze_on_fail arg set, not cleaning test resources')
        else:
            self.tester.cleanup_artifacts()

    def get_proxy_machine(self, instance):
        if self.tester.config["network"].lower() == "edge":
            proxy_machine = self.get_active_nc_for_instance(instance)
        else:
            proxy_machine = self.get_active_cc_for_instance(instance)
        self.debug("Instance is running on: " + proxy_machine.hostname)
        return proxy_machine

    def create_ssh_connection_to_instance(self, instance, retry=10):
        proxy_machine = self.get_proxy_machine(instance)
        ssh = None
        attempts = 0
        elapsed = 0
        next_retry_time = 10
        start = time.time()
        proxy_keypath=proxy_machine.machine.ssh.keypath or None
        while not ssh and attempts < retry:
            attempts += 1
            elapsed = int(time.time()-start)
            self.debug('Attempting to ssh to instances private ip:' + str(instance.private_ip_address) +
                       'through the cc ip:' + str(proxy_machine.hostname) + ', attempts:' +str(attempts) + "/" + str(retry) +
                       ", elapsed:" + str(elapsed))
            try:
                ssh = SshConnection(host=instance.private_ip_address,
                                keypath=instance.keypath,
                                proxy=proxy_machine.hostname,
                                proxy_username=proxy_machine.machine.ssh.username,
                                proxy_password=proxy_machine.machine.ssh.password,
                                proxy_keypath=proxy_keypath)
            except Exception, ce:
                tb = self.tester.get_traceback()
                if attempts >= retry:
                    self.debug("\n" + tb,linebyline=False)
                self.debug('Failed to connect error:' + str(ce))
            if attempts < retry:
                    time.sleep(next_retry_time)

        if not ssh:
            raise Exception('Could not ssh to instances private ip:' + str(instance.private_ip_address) +
                            ' through the cc ip:' + str(proxy_machine.hostname) + ', attempts:' +str(attempts) + "/" + str(retry) +
                            ", elapsed:" + str(elapsed))

        return ssh

    def get_active_cc_for_instance(self,instance,refresh_active_cc=30):
        elapsed = time.time()-self.cc_last_checked
        self.cc_last_checked = time.time()
        if elapsed > refresh_active_cc:
            use_cached_list = False
        else:
            use_cached_list = True
        cc = self.tester.service_manager.get_all_cluster_controllers(partition=instance.placement,
                                                                     use_cached_list= use_cached_list,
                                                                     state='ENABLED')[0]
        return cc

    def get_active_nc_for_instance(self,instance):
        nc = self.tester.service_manager.get_all_node_controllers(instance_id=instance.id, use_cached_list=False).pop()
        return nc

    def ping_instance_private_ip_from_active_cc(self, instance):
        assert isinstance(instance, EuInstance)
        proxy_machine = self.get_proxy_machine(instance)
        try:
            proxy_machine.machine.ping_check(instance.private_ip_address)
            return True
        except:pass
        return False




    ################################################################
    #   Test Methods
    ################################################################


    def test1_create_instance_in_zones_for_security_group1(self, ping_timeout=180):
        '''
        Definition:
        Create test instances within each zone within security group1. This security group is authorized for
        ssh access from 0.0.0.0/0.
        This test attempts the following:
            -To run an instance in each zone and confirm it reaches 'running' state.
            -Confirm the instance is ping-able from the cc within a given timeout
            -Establish and verify an ssh session directly from the local machine running this test.
            -Place ssh key on instance for later use
            -Add instance to global 'group1_instances'
        '''
        for zone in self.zones:
            #Create an instance, monitor it's state but disable the auto network/connect checks till afterward
            instance = self.tester.run_image(image=self.image,
                                             keypair=self.keypair,
                                             group=self.group1,
                                             zone=zone,
                                             auto_connect=False,
                                             monitor_to_running=False)[0]
            self.group1_instances.append(instance)
        self.tester.monitor_euinstances_to_running(self.group1_instances)
        #Now run the network portion.
        for instance in self.group1_instances:
            self.status('Checking connectivity to:' + str(instance.id) + ":" + str(instance.private_ip_address)+
                        ", zone:" + str(instance.placement) )
            assert isinstance(instance, EuInstance)
            self.debug('Attempting to ping instances private ip from cc...')
            self.tester.wait_for_result( self.ping_instance_private_ip_from_active_cc,
                                         result=True,
                                         timeout=ping_timeout,
                                         instance=instance)
            self.debug('Attempting to ssh to instance from local test machine...')
            self.debug('Check some debug information re this data connection in this security group first...')
            self.tester.does_instance_sec_group_allow(instance=instance,
                                                      src_addr=None,
                                                      protocol='tcp',
                                                      port=22)
            instance.connect_to_instance(timeout=90)
            self.status('SSH connection to instance:' + str(instance.id) +
                        ' successful to public ip:' + str(instance.ip_address) +
                        ', zone:' + str(instance.placement))
            instance.sys('uname -a', code=0)
            instance.ssh.sftp_put(instance.keypath, os.path.basename(instance.keypath))
            instance.sys('chmod 0600 ' + os.path.basename(instance.keypath), code=0 )



    def test2_create_instance_in_zones_for_security_group2(self, ping_timeout=180):
        '''
        Definition:
        This test attempts to create an instance in each zone within security group2 which should not
        be authorized for any remote access (outside of the CC).
        The test attempts the following:
            -To run an instance in each zone and confirm it reaches 'running' state.
            -Confirm the instance is ping-able from the cc within a given timeout
            -Establish and verify an ssh session using the cc as a proxy.
            -Place ssh key on instance for later use
            -Add instance to global 'group2_instances'
        '''
        for zone in self.zones:
            instance = self.tester.run_image(image=self.image,
                                             keypair=self.keypair,
                                             group=self.group2,
                                             zone=zone,
                                             auto_connect=False,
                                             monitor_to_running=False)[0]
            self.group2_instances.append(instance)
        self.tester.monitor_euinstances_to_running(self.group2_instances)
        for instance in self.group2_instances:
            self.status('Checking connectivity to:' + str(instance.id) + ":" + str(instance.private_ip_address)+
                        ", zone:" + str(instance.placement) )
            assert isinstance(instance, EuInstance)
            self.tester.wait_for_result( self.ping_instance_private_ip_from_active_cc,
                                         result=True,
                                         timeout=ping_timeout,
                                         instance=instance)
            self.status('Make sure ssh is working through CC path before trying between instances...')
            instance.cc_ssh = self.create_ssh_connection_to_instance(instance)
            self.status('SSH connection to instance:' + str(instance.id) +
                        ' successful to private ip:' + str(instance.private_ip_address) +
                        ', zone:' + str(instance.placement))
            instance.cc_ssh.sys('uname -a', code=0)
            self.status('Uploading keypair to instance in group2...')
            instance.cc_ssh.sftp_put(instance.keypath, os.path.basename(instance.keypath))
            instance.cc_ssh.sys('chmod 0600 ' + os.path.basename(instance.keypath), code=0 )
            self.status('Done with create instance security group2:' + str(instance.id))


    def test3_test_ssh_between_instances_in_diff_sec_groups_same_zone(self, no_cidr=None):
        '''
        Definition:
        This test attempts to set up security group rules between group1 and group2 to authorize group2 access
        from group1. If no_cidr is True security groups will be setup using cidr notation ip/mask for each instance in
        group1, otherwise the entire source group 1 will be authorized.

        Test attempts to:
            -Authorize security groups for inter group private ip access.
            -Iterate through each zone and attempt to ssh from an instance in group1 to an instance in group2 over their
                private ips.
        '''

        if no_cidr is None:
            no_cidr = self.args.no_cidr
        if no_cidr:
            self.authorize_group_for_instance_list(self.group2, self.group1_instances)
        else:
            self.tester.authorize_group(self.group2, cidr_ip=None, port=None, src_security_group_name=self.group1.name )

        for zone in self.zones:
            instance1 = None
            instance2 = None
            for instance in self.group1_instances:
                if instance.placement == zone:
                    assert isinstance(instance, EuInstance)
                    instance1 = instance
                    break
            if not instance1:
                raise Exception('Could not find instance in group1 for zone:' + str(zone))

            for instance in self.group2_instances:
                if instance.placement == zone:
                    assert isinstance(instance, EuInstance)
                    instance2 = instance
                    break
            if not instance2:
                raise Exception('Could not find instance in group2 for zone:' + str(zone))
        self.debug('Attempting to run ssh command "uname -a" between instances across security groups:\n'
                   + str(instance1.id) + '/sec grps(' + str(instance1.security_groups)+") --> "
                   + str(instance2.id) + '/sec grps(' + str(instance2.security_groups)+")\n"
                   + "Current test run in zone: " + str(zone), linebyline=False )
        self.debug('Check some debug information re this data connection in this security group first...')
        self.tester.does_instance_sec_group_allow(instance=instance2,
                                                  src_addr=instance1.private_ip_address,
                                                  protocol='tcp',
                                                  port=22)
        self.debug('Now Running the ssh command...')
        instance1.sys("ssh -o StrictHostKeyChecking=no -i "
                      + str(os.path.basename(instance1.keypath))
                      + " root@" + str(instance2.private_ip_address)
                      + " 'uname -a'", code=0)
        self.debug('Ssh between instances passed')

    def test4_attempt_unauthorized_ssh_from_test_machine_to_group2(self):
        '''
        Description:
        Test attempts to verify that the local machine cannot ssh to the instances within group2 which is not authorized
        for ssh access from this source.
        '''
        for instance in self.group2_instances:
            assert isinstance(instance, EuInstance)
            #Provide some debug information re this data connection in this security group
            self.tester.does_instance_sec_group_allow(instance=instance, src_addr=None, protocol='tcp',port=22)
            try:
                instance.reset_ssh_connection(timeout=5)
                raise Exception('Was able to connect to instance: ' + str(instance.id) + ' in security group:'
                                + str(self.group2.name))
            except:
                self.debug('Success: Was not able to ssh from the local machine to instance in unauthorized sec group')

    def test5_test_ssh_between_instances_in_same_sec_groups_different_zone(self):
        '''
        Definition:
        This test attempts to check connectivity for instances in the same security group, but in different zones.
        Note: This test requires the CC have tunnelling enabled, or the CCs in each zone be on same
        layer 2 network segment.

        Test attempts to:
            -Iterate through each zone and attempt to ssh from an instance in group1 to an instance in a separate zone
             but same security group1 over their private ips.
        '''
        zones = []
        if len(self.zones) < 2:
            raise SkipTestException('Skipping test5, only a single zone found or provided')

        class TestZone():
            def __init__(self, zone):
                self.zone = zone
                self.test_instance_group1 = None
                self.test_instance_group2 = None

        for zone in self.zones:
            zones.append(TestZone(zone))
            #Grab a single instance from each zone within security group1
        for zone in zones:
            instance = None
            for instance in self.group1_instances:
                if instance.placement == zone.zone:
                    assert isinstance(instance, EuInstance)
                    zone.test_instance_group1 = instance
                    break
                instance = None
            if not zone.test_instance_group1:
                raise Exception('Could not find an instance in group1 for zone:' + str(zone.zone))

        self.debug('Iterating through zones, attempting ssh between zones within same security group...')
        for zone in zones:
            instance1 = zone.test_instance_group1
            for zone2 in zones:
                if zone.zone != zone2.zone:
                    instance2 = zone2.test_instance_group1
                    if not instance1 or not instance2:
                        raise Exception('Security group: ' + str(self.group1.name) + ", missing instances in a Zone:"
                                        + str(zone.zone) + " = instance:" + str(instance1) +
                                        ", Zone:" + str(zone2.zone) + " = instance:" + str(instance2))
                    self.debug('Attempting to run ssh command "uname -a" between instances across zones and security groups:\n'
                               + str(instance1.id) + '/sec grps(' + str(instance1.security_groups)+") --> "
                               + str(instance2.id) + '/sec grps(' + str(instance2.security_groups)+")\n"
                               + "Current test run in zones: " + str(instance1.placement) + "-->" + str(instance2.placement),
                               linebyline=False )
                    self.debug('Check some debug information re this data connection in this security group first...')
                    self.tester.does_instance_sec_group_allow(instance=instance2,
                                                              src_addr=instance1.private_ip_address,
                                                              protocol='tcp',
                                                              port=22)
                    self.debug('Now Running the ssh command...')
                    instance1.sys("ssh -o StrictHostKeyChecking=no -i "
                                  + str(os.path.basename(instance1.keypath))
                                  + " root@" + str(instance2.private_ip_address)
                                  + " ' uname -a'", code=0)
                    self.debug('Ssh between instances passed')




    def test6_test_ssh_between_instances_in_diff_sec_groups_different_zone(self):
        '''
        Definition:
        This test attempts to set up security group rules between group1 and group2 to authorize group2 access
        from group1 across different zones.
        If no_cidr is True security groups will be setup using cidr notication ip/mask for each instance in
        group1, otherwise the entire source group 1 will authorized.
        the group will be
        Note: This test requires the CC have tunnelling enabled, or the CCs in each zone be on same
        layer 2 network segment.

        Test attempts to:
            -Authorize security groups for inter group private ip access.
            -Iterate through each zone and attempt to ssh from an instance in group1 to an instance in group2 over their
                private ips.
        '''
        zones = []
        if len(self.zones) < 2:
            raise SkipTestException('Skipping test5, only a single zone found or provided')
        self.status('Authorizing group2:' + str(self.group2.name) + ' for access from group1:' + str(self.group1.name))
        self.tester.authorize_group(self.group2, cidr_ip=None, port=None, src_security_group_name=self.group1.name)

        class TestZone():
            def __init__(self, zone):
                self.zone = zone
                self.test_instance_group1 = None
                self.test_instance_group2 = None

        for zone in self.zones:
            zones.append(TestZone(zone))


        self.debug('Grabbing  a single instance from each zone and from each test security group to use in this test...')
        for zone in zones:
            instance = None
            for instance in self.group1_instances:
                if instance.placement == zone.zone:
                    assert isinstance(instance, EuInstance)
                    zone.test_instance_group1 = instance
                    break
                instance = None
            if not zone.test_instance_group1:
                raise Exception('Could not find an instance in group1 for zone:' + str(zone.zone))
            instance = None
            for instance in self.group2_instances:
                if instance.placement == zone.zone:
                    assert isinstance(instance, EuInstance)
                    zone.test_instance_group2 = instance
                    break
            if not zone.test_instance_group2:
                raise Exception('Could not find instance in group2 for zone:' + str(zone.zone))
            instance = None

        self.status('Checking connectivity for instances in each zone, in separate but authorized security groups...')
        for zone in zones:
            instance1 = zone.test_instance_group1
            if not instance1:
                raise Exception('Missing instance in Security group: ' + str(self.group1.name) + ', Zone:' +
                                str(zone) + " = instance:" + str(instance1) )
            for zone2 in zones:
                if zone.zone != zone2.zone:
                    instance2 = zone2.test_instance_group2
                    if not instance2:
                        raise Exception('Missing instance in Security group: ' + str(self.group2.name) + ', Zone:' +
                                        str(zone2.zone) + " = instance:" + str(instance2) )
                    self.debug('Attempting to run ssh command "uname -a" between instances across zones and security groups:\n'
                               + str(instance1.id) + '/sec grps(' + str(instance1.security_groups)+") --> "
                               + str(instance2.id) + '/sec grps(' + str(instance2.security_groups)+")\n"
                               + "Current test run in zones: " + str(instance1.placement) + "-->" + str(instance2.placement),
                               linebyline=False )
                    self.debug('Check some debug information re this data connection in this security group first...')
                    self.tester.does_instance_sec_group_allow(instance=instance2,
                                                              src_addr=instance1.private_ip_address,
                                                              protocol='tcp',
                                                              port=22)
                    self.debug('Now Running the ssh command...')
                    instance1.sys("ssh -o StrictHostKeyChecking=no -i "
                                  + str(os.path.basename(instance1.keypath))
                                  + " root@" + str(instance2.private_ip_address)
                                  + " ' uname -a'", code=0)
                    self.debug('Ssh between instances passed')






if __name__ == "__main__":
    testcase = Net_Tests()

    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list

    if testcase.args.tests:
        list = testcase.args.tests
    else:
        list =['test1_create_instance_in_zones_for_security_group1',
               'test2_create_instance_in_zones_for_security_group2',
               'test3_test_ssh_between_instances_in_diff_sec_groups_same_zone',
               'test4_attempt_unauthorized_ssh_from_test_machine_to_group2',
               'test5_test_ssh_between_instances_in_same_sec_groups_different_zone',
               'test6_test_ssh_between_instances_in_diff_sec_groups_different_zone']
        ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,eof=False,clean_on_exit=True)
    exit(result)



