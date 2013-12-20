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
# Author: clarkmatthew

import eucaops
from eutester.eutestcase import EutesterTestCase
import time

class MyTestCase(EutesterTestCase):
    def __init__(self, config_file=None, password=None):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--timeout", default=600)
        self.get_args()


    def clean_method(self):
        self.debug('No clean_method defined for this test')
        pass

    def wait_for_services_operational(self, timeout=None):
        """
        Definition:
        Test attempts to query the state of a subset of core services. The test will continue to poll the system
        until it finds an ENABLED instance of each service. In the HA case it will wait for an ENABLED and DISABLED
        instance of each.
        """
        timeout= timeout or self.args.timeout
        last_err = ""
        elapsed = 0
        start = time.time()
        self.tester = None
        while (not self.tester and elapsed < timeout):
            elapsed = int(time.time() - start)
            self.status('Attempting to create tester object. Elapsed:' + str(elapsed))
            try:
                self.tester = eucaops.Eucaops(config_file=self.args.config_file, password=self.args.password)
            except Exception, e:
                tb = eucaops.Eucaops.get_traceback()
                last_err = str(tb) + "\n" + str(e)
                print 'Services not up because of: ' + last_err + '\n'
        if not self.tester:
            raise Exception(str(last_err) + 'Could not create tester object after elapsed:' + str(elapsed))
        timeout = timeout - elapsed
        self.status('starting wait for all services operational, timeout:' + str(timeout))
        self.tester.service_manager.wait_for_all_services_operational(timeout)
        self.status('All services are up')
        self.tester.service_manager.print_services_list()



if __name__ == "__main__":
    testcase = MyTestCase()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list  "VolumeTagging", "InstanceTagging", "SnapshotTagging", "ImageTagging"
    list = testcase.args.tests or ["wait_for_services_operational"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects, dont worry about clean on exit until we need it for this method
    result = testcase.run_test_case_list(unit_list,clean_on_exit=False)
    exit(result)

