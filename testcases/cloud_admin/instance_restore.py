#!/usr/bin/env python
#
#
# Description:  This script encompasses test cases/modules concerning instance specific behavior and
#               features for Eucalyptus.  The test cases/modules that are executed can be
#               found in the script under the "tests" list.


import time
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
import os
import random

class InstanceRestore(EutesterTestCase):
    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config_file, password=self.args.password)
        self.tester.poll_count = 120

        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        self.image = self.tester.get_emi(root_device_type="instance-store")
        self.reservation = None
        self.private_addressing = False
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name
        clcs = self.tester.get_component_machines("clc")
        if len(clcs) is 0:
            raise Exception("No CLC found")
        else:
            self.clc = clcs[0]
        self.cur_time = str(int(time.time()))
        self.ncs = self.tester.get_component_machines("nc")

    def clean_method(self):
        ncs = self.tester.get_component_machines("nc")
        for nc in ncs:
            nc.sys("service eucalyptus-nc start")

        ### RESET vmstate properties
        self.tester.modify_property("cloud.vmstate.instance_timeout","60")
        self.tester.modify_property("cloud.vmstate.terminated_time","60")
        for nc in self.ncs:
            nc.sys("service eucalyptus-nc start")
        self.tester.cleanup_artifacts()
        try:
            image = self.tester.get_emi(self.image)
        except Exception,e:
            self.tester.register_image(image_location=self.image.location,
                                       ramdisk=self.image.ramdisk_id,
                                       kernel=self.image.kernel_id,
                                       virtualization_type=self.image.virtualization_type)

    def RestoreLogic(self):
        self.tester.modify_property("cloud.vmstate.instance_timeout","1")
        self.tester.modify_property("cloud.vmstate.terminated_time","1")

        ### desired number of instances in the reservation
        res_count = 2
        self.reservation = self.tester.run_instance(self.image, keypair=self.keypair.name, group=self.group.name, zone=self.zone, min=res_count, max=res_count)

        for nc in self.ncs:
            nc.sys("service eucalyptus-nc stop")

        ### Wait for instance to show up as terminated
        self.tester.monitor_euinstances_to_state(self.reservation.instances, state="terminated", timeout=600)

        instance_under_test = None
        for instance in self.reservation.instances:
            instance_under_test = instance
            instance.terminate()

        self.tester.deregister_image(self.image)

        for nc in self.ncs:
            nc.sys("service eucalyptus-nc start")

        def check_for_instance():
            try:
                if not self.tester.ec2.get_all_instances(instance_ids=[instance_under_test.id]):
                    raise Exception("Unable to find instance")
                else:
                    return True
            except Exception, e:
                return False
        self.tester.wait_for_result(check_for_instance, True, timeout=600)
        self.tester.monitor_euinstances_to_state(self.reservation.instances, state="running", timeout=600)

        for instance in self.reservation.instances:
            instance.sys("uname -r", code=0)


if __name__ == "__main__":
    testcase = InstanceRestore()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or ["RestoreLogic"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append(testcase.create_testunit_by_name(test))
        ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
