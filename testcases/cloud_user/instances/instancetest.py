#!/usr/bin/env python
#
#
# Description:  This script encompasses test cases/modules concerning instance specific behavior and
#               features for Eucalyptus.  The test cases/modules that are executed can be 
#               found in the script under the "tests" list.

import time
from concurrent.futures import ThreadPoolExecutor
import threading
from eucaops import Eucaops
from eutester import WaitForResultException
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase
from eucaops import EC2ops
import os
import re
import random


class InstanceBasics(EutesterTestCase):
    def __init__( self, name="InstanceBasics", credpath=None, region=None, config_file=None, password=None, emi=None, zone=None,
                  user_data=None, instance_user=None, **kwargs):
        """
        EC2 API tests focused on instance store instances

        :param credpath: Path to directory containing eucarc file
        :param region: EC2 Region to run testcase in
        :param config_file: Configuration file path
        :param password: SSH password for bare metal machines if config is passed and keys arent synced
        :param emi: Image id to use for test
        :param zone: Availability Zone to run test in
        :param user_data: User Data to pass to instance
        :param instance_user: User to login to instance as
        :param kwargs: Additional arguments
        """
        super(InstanceBasics, self).__init__(name=name)
        self.get_args()
        self.show_args()
        for kw in kwargs:
            print 'Setting kwarg:'+str(kw)+" to "+str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        self.show_args()
        if self.args.region:
            self.tester = EC2ops(credpath=self.args.redpath, region=self.args.region)
        else:
            self.tester = Eucaops(config_file=self.args.config_file,
                                  password=self.args.password,
                                  credpath=self.args.credpath)
        self.instance_timeout = 600

        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name)
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp")
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair("keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        if emi:
            self.image = self.tester.get_emi(emi=self.args.emi)
        else:
            self.image = self.tester.get_emi(root_device_type="instance-store", basic_image=True)
        self.address = None
        self.volume = None
        self.private_addressing = False
        if not self.args.zone:
            zones = self.tester.ec2.get_all_zones()
            self.zone = random.choice(zones).name
        else:
            self.zone = self.args.zone
        self.reservation = None
        self.reservation_lock = threading.Lock()
        self.run_instance_params = {'image': self.image,
                                    'user_data': self.args.user_data,
                                    'username': self.args.instance_user,
                                    'keypair': self.keypair.name,
                                    'group': self.group.name,
                                    'zone': self.zone,
                                    'return_reservation': True,
                                    'timeout': self.instance_timeout}
        self.managed_network = True

        ### If I have access to the underlying infrastructure I can look
        ### at the network mode and only run certain tests where it makes sense
        if hasattr(self.tester, "service_manager"):
            cc = self.tester.get_component_machines("cc")[0]
            network_mode = cc.sys("cat " + self.tester.eucapath + "/etc/eucalyptus/eucalyptus.conf | grep MODE")[0]
            if re.search("(SYSTEM|STATIC)", network_mode):
                self.managed_network = False

    def set_reservation(self, reservation):
        self.reservation_lock.acquire()
        self.reservation = reservation
        self.reservation_lock.release()

    def clean_method(self):
        self.tester.cleanup_artifacts()

    def BasicInstanceChecks(self):
        """
        This case was developed to run through a series of basic instance tests.
             The tests are as follows:
                   - execute run_instances command
                   - make sure that public DNS name and private IP aren't the same
                       (This is for Managed/Managed-NOVLAN networking modes)
                   - test to see if instance is ping-able
                   - test to make sure that instance is accessible via ssh
                       (ssh into instance and run basic ls command)
             If any of these tests fail, the test case will error out, logging the results.
        """
        reservation = self.tester.run_image(**self.run_instance_params)
        for instance in reservation.instances:
            self.assertTrue(self.tester.wait_for_reservation(reservation), 'Instance did not go to running')
            self.assertTrue(self.tester.ping(instance.ip_address), 'Could not ping instance')
            if self.image.virtualization_type == "paravirtual":
                paravirtual_ephemeral = "/dev/" + instance.rootfs_device + "2"
                self.assertFalse(instance.found("ls -1 " + paravirtual_ephemeral,  "No such file or directory"),
                                 "Did not find ephemeral storage at " + paravirtual_ephemeral)
            elif self.image.virtualization_type == "hvm":
                hvm_ephemeral = "/dev/" + instance.block_device_prefix + "b"
                self.assertFalse(instance.found("ls -1 " + hvm_ephemeral,  "No such file or directory"),
                                 "Did not find ephemeral storage at " + hvm_ephemeral)
            self.debug("Pinging instance public IP from inside instance")
            instance.sys('ping -c 1 ' + instance.ip_address, code=0)
            self.debug("Pinging instance private IP from inside instance")
            instance.sys('ping -c 1 ' + instance.private_ip_address, code=0)
        self.set_reservation(reservation)
        return reservation

    def ElasticIps(self):
        """
       This case was developed to test elastic IPs in Eucalyptus. This test case does
       not test instances that are launched using private-addressing option.
       The test case executes the following tests:
           - allocates an IP, associates the IP to the instance, then pings the instance.
           - disassociates the allocated IP, then pings the instance.
           - releases the allocated IP address
       If any of the tests fail, the test case will error out, logging the results.
        """
        if not self.reservation:
            reservation = self.tester.run_image(**self.run_instance_params)
        else:
            reservation = self.reservation

        for instance in reservation.instances:
            if instance.ip_address == instance.private_ip_address:
                self.tester.debug("WARNING: System or Static mode detected, skipping ElasticIps")
                return reservation
            domain = None
            if instance.vpc_id:
                domain = 'vpc' # Set domain to 'vpc' for use with instance in a VPC
            self.address = self.tester.allocate_address(domain=domain)
            self.assertTrue(self.address, 'Unable to allocate address')
            self.tester.associate_address(instance, self.address)
            instance.update()
            self.assertTrue(self.tester.ping(instance.ip_address), "Could not ping instance with new IP")
            self.tester.disassociate_address_from_instance(instance)
            self.tester.release_address(self.address)
            self.address = None
            assert isinstance(instance, EuInstance)
            self.tester.sleep(5)
            instance.update()
            self.assertTrue(self.tester.ping(instance.ip_address), "Could not ping after dissassociate")
        self.set_reservation(reservation)
        return reservation

    def MultipleInstances(self):
        """
        This case was developed to test the maximum number of m1.small vm types a configured
        cloud can run.  The test runs the maximum number of m1.small vm types allowed, then
        tests to see if all the instances reached a running state.  If there is a failure,
        the test case errors out; logging the results.
        """
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
            self.set_reservation(None)

        reservation = self.tester.run_image(min=2, max=2, **self.run_instance_params)
        self.assertTrue(self.tester.wait_for_reservation(reservation), 'Not all instances  went to running')
        self.set_reservation(reservation)
        return reservation

    def LargestInstance(self):
        """
        This case was developed to test the maximum number of c1.xlarge vm types a configured
        cloud can run.  The test runs the maximum number of c1.xlarge vm types allowed, then
        tests to see if all the instances reached a running state.  If there is a failure,
        the test case errors out; logging the results.
        """
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
            self.set_reservation(None)
        reservation = self.tester.run_image(type="c1.xlarge", **self.run_instance_params)
        self.assertTrue(self.tester.wait_for_reservation(reservation), 'Not all instances  went to running')
        self.set_reservation(reservation)
        return reservation

    def MetaData(self):
        """
        This case was developed to test the metadata service of an instance for consistency.
        The following meta-data attributes are tested:
           - public-keys/0/openssh-key
           - security-groups
           - instance-id
           - local-ipv4
           - public-ipv4
           - ami-id
           - ami-launch-index
           - reservation-id
           - placement/availability-zone
           - kernel-id
           - public-hostname
           - local-hostname
           - hostname
           - ramdisk-id
           - instance-type
           - any bad metadata that shouldn't be present.
        Missing nodes
         ['block-device-mapping/',  'ami-manifest-path']
        If any of these tests fail, the test case will error out; logging the results.
        """
        if not self.reservation:
            reservation = self.tester.run_image(**self.run_instance_params)
        else:
            reservation = self.reservation
        for instance in reservation.instances:
            ## Need to verify  the public key (could just be checking for a string of a certain length)
            self.assertTrue(re.match(instance.get_metadata("public-keys/0/openssh-key")[0].split('eucalyptus.')[-1],
                                     self.keypair.name), 'Incorrect public key in metadata')
            self.assertTrue(re.match(instance.get_metadata("security-groups")[0], self.group.name),
                            'Incorrect security group in metadata')
            # Need to validate block device mapping
            #self.assertTrue(re.search(instance_ssh.get_metadata("block-device-mapping/")[0], "")) 
            self.assertTrue(re.match(instance.get_metadata("instance-id")[0], instance.id),
                            'Incorrect instance id in metadata')
            self.assertTrue(re.match(instance.get_metadata("local-ipv4")[0], instance.private_ip_address),
                            'Incorrect private ip in metadata')
            self.assertTrue(re.match(instance.get_metadata("public-ipv4")[0], instance.ip_address),
                            'Incorrect public ip in metadata')
            self.assertTrue(re.match(instance.get_metadata("ami-id")[0], instance.image_id),
                            'Incorrect ami id in metadata')
            self.assertTrue(re.match(instance.get_metadata("ami-launch-index")[0], instance.ami_launch_index),
                            'Incorrect launch index in metadata')
            self.assertTrue(re.match(instance.get_metadata("reservation-id")[0], reservation.id),
                            'Incorrect reservation in metadata')
            self.assertTrue(re.match(instance.get_metadata("placement/availability-zone")[0], instance.placement),
                            'Incorrect availability-zone in metadata')
            if self.image.virtualization_type == "paravirtual":
                self.assertTrue(re.match(instance.get_metadata("kernel-id")[0], instance.kernel),
                                'Incorrect kernel id in metadata')
                self.assertTrue(re.match(instance.get_metadata("ramdisk-id")[0], instance.ramdisk),
                                'Incorrect ramdisk in metadata')
            self.assertTrue(re.match(instance.get_metadata("public-hostname")[0], instance.public_dns_name),
                            'Incorrect public host name in metadata')
            self.assertTrue(re.match(instance.get_metadata("local-hostname")[0], instance.private_dns_name),
                            'Incorrect private host name in metadata')
            self.assertTrue(re.match(instance.get_metadata("hostname")[0], instance.private_dns_name),
                            'Incorrect host name in metadata')
            self.assertTrue(re.match(instance.get_metadata("instance-type")[0], instance.instance_type),
                            'Incorrect instance type in metadata')
            bad_meta_data_keys = ['foobar']
            for key in bad_meta_data_keys:
                self.assertTrue(re.search("Not Found", "".join(instance.get_metadata(key))),
                                'No fail message on invalid meta-data node')
        self.set_reservation(reservation)
        return reservation

    def DNSResolveCheck(self):
        """
        This case was developed to test DNS resolution information for public/private DNS
        names and IP addresses.  The tested DNS resolution behavior is expected to follow

        AWS EC2.  The following tests are ran using the associated meta-data attributes:
           - check to see if Eucalyptus Dynamic DNS is configured
           - nslookup on hostname; checks to see if it matches local-ipv4
           - nslookup on local-hostname; check to see if it matches local-ipv4
           - nslookup on local-ipv4; check to see if it matches local-hostname
           - nslookup on public-hostname; check to see if it matches local-ipv4
           - nslookup on public-ipv4; check to see if it matches public-host
        If any of these tests fail, the test case will error out; logging the results.
        """
        if not self.reservation:
            reservation = self.tester.run_image(**self.run_instance_params)
        else:
            reservation = self.reservation

        def validate_instance_dns():
            try:
                for instance in reservation.instances:
                    if not re.search("internal", instance.private_dns_name):
                        self.tester.debug("Did not find instance DNS enabled, skipping test")
                        self.set_reservation(reservation)
                        return reservation
                    self.debug('\n'
                               '# Test to see if Dynamic DNS has been configured \n'
                               '# Per AWS standard, resolution should have private hostname or '
                               'private IP as a valid response\n'
                               '# Perform DNS resolution against public IP and public DNS name\n'
                               '# Perform DNS resolution against private IP and private DNS name\n'
                               '# Check to see if nslookup was able to resolve\n')
                    assert isinstance(instance, EuInstance)
                    self.debug('Check nslookup to resolve public DNS Name to local-ipv4 address')
                    self.assertTrue(instance.found("nslookup " + instance.public_dns_name,
                                                   instance.private_ip_address), "Incorrect DNS resolution for hostname.")
                    self.debug('Check nslookup to resolve public-ipv4 address to public DNS name')
                    if self.managed_network:
                        self.assertTrue(instance.found("nslookup " + instance.ip_address,
                                                       instance.public_dns_name),
                                        "Incorrect DNS resolution for public IP address")
                    self.debug('Check nslookup to resolve private DNS Name to local-ipv4 address')
                    if self.managed_network:
                        self.assertTrue(instance.found("nslookup " + instance.private_dns_name,
                                                       instance.private_ip_address),
                                        "Incorrect DNS resolution for private hostname.")
                    self.debug('Check nslookup to resolve local-ipv4 address to private DNS name')
                    self.assertTrue(instance.found("nslookup " + instance.private_ip_address,
                                                   instance.private_dns_name),
                                    "Incorrect DNS resolution for private IP address")
                    self.debug('Attempt to ping instance public_dns_name')
                    self.assertTrue(self.tester.ping(instance.public_dns_name))
                    return True
            except Exception, e:
                return False
        self.tester.wait_for_result(validate_instance_dns, True, timeout=120)
        self.set_reservation(reservation)
        return reservation

    def Reboot(self):
        """
        This case was developed to test IP connectivity and volume attachment after
        instance reboot.  The following tests are done for this test case:
                   - creates a 1 gig EBS volume, then attach volume
                   - reboot instance
                   - attempts to connect to instance via ssh
                   - checks to see if EBS volume is attached
                   - detaches volume
                   - deletes volume
        If any of these tests fail, the test case will error out; logging the results.
        """
        if not self.reservation:
            reservation = self.tester.run_image(**self.run_instance_params)
        else:
            reservation = self.reservation
        for instance in reservation.instances:
            ### Create 1GB volume in first AZ
            volume = self.tester.create_volume(instance.placement, size=1, timepergig=180)
            instance.attach_volume(volume)
            ### Reboot instance
            instance.reboot_instance_and_verify(waitconnect=20)
            instance.detach_euvolume(volume)
            self.tester.delete_volume(volume)
        self.set_reservation(reservation)
        return reservation

    def Churn(self):
        """
        This case was developed to test robustness of Eucalyptus by starting instances,
        stopping them before they are running, and increase the time to terminate on each
        iteration.  This test case leverages the BasicInstanceChecks test case. The
        following steps are ran:
            - runs BasicInstanceChecks test case 5 times, 10 second apart.
            - While each test is running, run and terminate instances with a 10sec sleep in between.
            - When a test finishes, rerun BasicInstanceChecks test case.
        If any of these tests fail, the test case will error out; logging the results.
        """
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
            self.set_reservation(None)
        try:
            available_instances_before = self.tester.get_available_vms(zone=self.zone)
            if available_instances_before > 4:
                count = 4
            else:
                count = available_instances_before
        except IndexError, e:
            self.debug("Running as non-admin, defaulting to 4 VMs")
            available_instances_before = count = 4

        future_instances = []

        with ThreadPoolExecutor(max_workers=count) as executor:
            ## Start asynchronous activity
            ## Run 5 basic instance check instances 10s apart
            for i in xrange(count):
                future_instances.append(executor.submit(self.BasicInstanceChecks))
                self.tester.sleep(10)

        with ThreadPoolExecutor(max_workers=count) as executor:
            ## Start asynchronous activity
            ## Terminate all instances
            for future in future_instances:
                executor.submit(self.tester.terminate_instances, future.result())

        def available_after_greater():
            try:
                return self.tester.get_available_vms(zone=self.zone) >= available_instances_before
            except IndexError, e:
                self.debug("Running as non-admin, skipping validation of available VMs.")
                return True
        self.tester.wait_for_result(available_after_greater, result=True, timeout=360)

    def PrivateIPAddressing(self):
        """
        This case was developed to test instances that are launched with private-addressing
        set to True.  The tests executed are as follows:
            - run an instance with private-addressing set to True
            - allocate/associate/disassociate/release an Elastic IP to that instance
            - check to see if the instance went back to private addressing
        If any of these tests fail, the test case will error out; logging the results.
        """
        if self.reservation:
            for instance in self.reservation.instances:
                if instance.ip_address == instance.private_ip_address:
                    self.tester.debug("WARNING: System or Static mode detected, skipping "
                                      "PrivateIPAddressing")
                    return self.reservation
            self.tester.terminate_instances(self.reservation)
            self.set_reservation(None)
        reservation = self.tester.run_image(private_addressing=True,
                                            auto_connect=False,
                                            **self.run_instance_params)
        for instance in reservation.instances:
            address = self.tester.allocate_address()
            self.assertTrue(address, 'Unable to allocate address')
            self.tester.associate_address(instance, address)
            self.tester.sleep(30)
            instance.update()
            self.debug('Attempting to ping associated IP:"{0}"'.format(address.public_ip))
            self.assertTrue(self.tester.ping(instance.ip_address),
                            "Could not ping instance with new IP")
            self.debug('Disassociating address:{0} from instance:{1}'.format(address.public_ip,
                                                                             instance.id))
            address.disassociate()
            self.tester.sleep(30)
            instance.update()
            self.debug('Confirming disassociated IP:"{0}" is no longer in use'
                       .format(address.public_ip))
            def wait_for_ping():
                return self.tester.ping(address.public_ip, poll_count=1)
            try:
                self.tester.wait_for_result(callback=wait_for_ping, result=False)
            except WaitForResultException as WE:
                self.errormsg("Was able to ping address:'{0}' that should no long be associated "
                              "with an instance".format(address.public_ip))
                raise WE
            address.release()
            if instance.ip_address:
                if (instance.ip_address != "0.0.0.0" and
                            instance.ip_address != instance.private_ip_address):
                    self.fail("Instance:'{0}' received a new public IP:'{0}' after disassociate"
                              .format(instance.id, instance.ip_address))
        self.tester.terminate_instances(reservation)
        self.set_reservation(reservation)
        return reservation

    def ReuseAddresses(self):
        """
        This case was developed to test when you run instances in a series, and make sure
        they get the same address.  The test launches an instance, checks the IP information,
        then terminates the instance. This test is launched 5 times in a row.  If there
        is an error, the test case will error out; logging the results.
        """
        prev_address = None
        if self.reservation:
            self.tester.terminate_instances(self.reservation)
            self.set_reservation(None)
        for i in xrange(5):
            reservation = self.tester.run_image(**self.run_instance_params)
            for instance in reservation.instances:
                if prev_address is not None:
                    self.assertTrue(re.search(str(prev_address), str(instance.ip_address)),
                                    str(prev_address) + " Address did not get reused but rather  " +
                                    str(instance.public_dns_name))
                prev_address = instance.ip_address
            self.tester.terminate_instances(reservation)

    def BundleInstance(self):
        if not self.reservation:
            self.reservation = self.tester.run_image(**self.run_instance_params)
        original_image = self.run_instance_params['image']
        for instance in self.reservation.instances:
            current_time = str(int(time.time()))
            temp_file = "/root/my-new-file-" + current_time
            instance.sys("touch " + temp_file)
            self.tester.sleep(60)
            starting_uptime = instance.get_uptime()
            self.run_instance_params['image'] = self.tester.bundle_instance_monitor_and_register(instance)
            instance.connect_to_instance()
            ending_uptime = instance.get_uptime()
            if ending_uptime > starting_uptime:
                raise Exception("Instance did not get stopped then started")
            bundled_image_reservation = self.tester.run_image(**self.run_instance_params)
            for new_instance in bundled_image_reservation.instances:
                new_instance.sys("ls " + temp_file, code=0)
            self.tester.terminate_instances(bundled_image_reservation)
        self.run_instance_params['image'] = original_image

if __name__ == "__main__":
    testcase = EutesterTestCase(name='instancetest')
    testcase.setup_parser(description="Test the Eucalyptus EC2 instance store image functionality.")
    testcase.get_args()
    instancetestsuite = testcase.do_with_args(InstanceBasics)

    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    test_list = testcase.args.tests or ["BasicInstanceChecks", "DNSResolveCheck", "Reboot", "MetaData", "ElasticIps",
                                        "MultipleInstances", "LargestInstance", "PrivateIPAddressing", "Churn"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = []
    for test in test_list:
        test = getattr(instancetestsuite, test)
        unit_list.append(testcase.create_testunit_from_method(test))
    testcase.clean_method = instancetestsuite.clean_method
    result = testcase.run_test_case_list(unit_list)
    exit(result)
