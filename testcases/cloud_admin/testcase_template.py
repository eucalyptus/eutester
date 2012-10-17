#!/usr/bin/env python
#
#
# Description:  This script encompasses test cases/modules concerning instance specific behavior and
#               features for Eucalyptus.  The test cases/modules that are executed can be
#               found in the script under the "tests" list.


import time
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase

class MyTestCase(EutesterTestCase):
    def __init__(self, config_file=None, password=None):
        self.setuptestcase()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=config_file, password=password)
        self.reservation = None
        ### Add and authorize a group for the instance
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )

        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))

        ### Get an image to work with
        self.image = self.tester.get_emi(root_device_type="instance-store")
        self.clean_method = self.cleanup

    def cleanup(self):
        if self.reservation:
            self.assertTrue(self.tester.terminate_instances(self.reservation), "Unable to terminate instance(s)")
        self.tester.delete_group(self.group)
        self.tester.delete_keypair(self.keypair)

    def MyTestUnit(self):
        """
        A test description must go here......
        This test will simply run an instance and check that it is reachable via ssh
        """
        self.reservation = self.tester.run_instance(self.image, keypair=self.keypair.name, group=self.group.name)
        for instance in self.reservation.instances:
            instance.sys("uname -r")

if __name__ == "__main__":
    ### Load a generic test case object to parse
    generic_testcase = EutesterTestCase()
    #### Adds args from config files and command line
    generic_testcase.compile_all_args()

    ### Initialize test suite using args found from above
    my_testcase = MyTestCase(config_file=generic_testcase.args.config_file, password=generic_testcase.args.password)

    ### List of test methods to run
    list = [ "MyTestUnit"]
    ### Convert test suite methods to EutesterUnitTest objects
    result = my_testcase.run_test_list_by_name(list)
