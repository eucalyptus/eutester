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
# Author: vic.iglesias@eucalyptus.com

from eucaops import Eucaops
import re
import string
from eutester.euinstance import EuInstance
from eutester.eutestcase import EutesterTestCase

class ChangeVLAN(EutesterTestCase):
    
    def __init__(self,extra_args = None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.parser.add_argument("--min-vlan", default=1)
        self.parser.add_argument("--max-vlan", default=4096)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config, password=self.args.password)

    def clean_method(self):
        pass

    def ChangeVLAN(self):
        '''
        Change VLAN range to a given subset
        '''
        clc = self.tester.get_component_machines("clc")[0]
        clc.sys("source " + self.tester.credpath + "/eucarc && " + self.tester.eucapath + "/usr/sbin/euca-modify-property -p cloud.network.global_max_network_tag=" + str(self.args.max_vlan))
        clc.sys("source " + self.tester.credpath + "/eucarc && " + self.tester.eucapath + "/usr/sbin/euca-modify-property -p cloud.network.global_min_network_tag=" + str(self.args.min_vlan))

if __name__ == "__main__":
    testcase = ChangeVLAN()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or ["ChangeVLAN"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
        ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)