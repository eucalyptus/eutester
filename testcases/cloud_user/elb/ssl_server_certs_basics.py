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
# Author: Tony Beckham tony@eucalyptus.com
#

from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from os.path import join


class SSLIAMServerCerts(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()

        # Setup basic eutester object
        self.tester = Eucaops( credpath=self.args.credpath, config_file=self.args.config,password=self.args.password)


    def cert_CRUD(self):
        """
        This will test upload, list, get, update, and delete server certificates.

        @raise Exception:
        """

        """certificate details"""
        cert_dir="./test_data"
        cert_file = "ssl_server_certs_basics.crt"
        key_file = "ssl_server_certs_basics.pem"
        cert_name = "ssl-server-certs-basics"
        updated_cert_name = cert_name + "-updated"
        new_path="/certs/"
        cert_body = open(join(cert_dir, cert_file)).read()
        cert_key = open(join(cert_dir, key_file)).read()

        """use CRUD operations (list and get are tested by being used in verification in implementation of these ops)"""
        self.tester.upload_server_cert(cert_name=cert_name, cert_body=cert_body, private_key=cert_key)

        self.tester.update_server_cert(cert_name=cert_name, new_cert_name=updated_cert_name, new_path=new_path)

        self.tester.delete_server_cert(updated_cert_name)

if __name__ == "__main__":
    testcase = SSLIAMServerCerts()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["cert_CRUD"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=False)
    exit(result)

