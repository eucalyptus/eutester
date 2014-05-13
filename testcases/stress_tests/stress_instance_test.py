#!/usr/bin/python

import time
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
import os

class InstanceBasicsTest(EutesterTestCase):
    def __init__(self):
        #### Pre-conditions
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--test-zone", default="PARTI00")
        self.parser.add_argument("--test-emi", default=None)
        self.parser.add_argument("--build-number", default='')
        self.get_args()

        # Setup basic eutester object
        if not self.args.credpath:
            self.tester = Eucaops(config_file=self.args.config, password=self.args.password)
        else:
            self.tester = Eucaops(credpath=self.args.credpath)
        self.reservation = None

        ### Generate a group for the instance
        self.group = self.tester.add_group(group_name="inst-kvm-grp-" + str(time.time()).replace(".", "") +
                                                      self.tester.id_generator() + "-" + self.args.build_number)
        self.tester.authorize_group_by_name(group_name=self.group.name)
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp")

        self.keypair = self.tester.add_keypair("inst-kvm-" + str(time.time()).replace(".", "") +
                                               self.tester.id_generator() + "-" + self.args.build_number)

        if not self.args.emi:
            self.image = self.tester.get_emi(root_device_type="instance-store")
        else:
            self.image = self.tester.get_emi(self.args.test_emi)

    def clean_method(self):
        """
        Description: Attempts to clean up resources created in this test
        """
        self.tester.cleanup_artifacts()

    def stress_instance_test(self):
        self.reservation = self.tester.run_image(self.image,
                                                 zone=self.args.test_zone,
                                                 min=1, max=1,
                                                 keypair=self.keypair.name,
                                                 group=self.group,
                                                 timeout=600)

if __name__ == "__main__":
    testcase = InstanceBasicsTest()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["stress_instance_test"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = []
    for test in list:
        unit_list.append(testcase.create_testunit_by_name(test))

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list, clean_on_exit=True)
    exit(result)

######################
### Jenkins Setup  ###
######################
# CREDPATH=credentials
# if [ ! -d "$CREDPATH" ]; then
#     mkdir $CREDPATH
# fi
# cat > credentials/eucarc << EOF
# $eucarc
# EOF
# 
# cat > test_script << EOF
# $script
# EOF
# /share/eutester-base/bin/python ./test_script --credpath credentials --zone $zone --emi $emi --build-number $BUILD_NUMBER