#!/usr/bin/python
import json
import os
import time
from eucaops import Eucaops, S3ops
from eutester.eutestcase import EutesterTestCase

class InstallRiak(EutesterTestCase):
    def __init__(self):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--admin-name", default="admin")
        self.parser.add_argument("--admin-email", default="admin@admin.com")
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config,password=self.args.password)

    def clean_method(self):
        pass

    def InstallRiakCS(self):
        """
        This is where the test description goes
        """
        try:  
            for machine in self.tester.get_component_machines("riak"):
                machine.sys("yum install -y http://yum.basho.com/gpg/basho-release-6-1.noarch.rpm")
                machine.sys("yum install -y riak stanchion riak-cs")
                machine.sys("ulimit -n 65536")
                for component in ['riak', 'stanchion', 'riak-cs']:
                    for config_file in ["app.config", "vm.args"]:
                        local_file = os.getcwd() + "/templates/" + config_file + "." + component
                        remote_file = "/etc/" + component + "/" + config_file
                        machine.sftp.put(local_file, remote_file)
                        machine.sys("sed -i s/IPADDRESS/" + machine.hostname + "/g " + remote_file)
                machine.sys("service riak start", code=0)
                machine.sys("service stanchion start", code=0)
                machine.sys("service riak-cs start", code=0)
                response_json = machine.sys('curl -H \'Content-Type: application/json\' -X POST http://' + machine.hostname +
                                       ':8080/riak-cs/user --data \'{"email":"' + self.args.admin_email +'", '
                                       '"name":"' + self.args.admin_name +'"}\'', code=0)[0]
                response_dict = json.loads(response_json)
                cs_tester = S3ops(endpoint=machine.hostname, aws_access_key_id=response_dict["key_id"],
                                  aws_secret_access_key=response_dict["key_secret"], port=8080)
                test_time = str(int(time.time()))
                bucket_name = "riak-test-bucket-" + test_time
                key_name = "riak-test-key-" + test_time
                bucket = cs_tester.create_bucket(bucket_name)
                cs_tester.upload_object(bucket_name, key_name, contents=response_dict["id"])
                key = cs_tester.get_objects_by_prefix(bucket_name, key_name).pop()
                key_contents = key.read()
                cs_tester.debug("Uploaded Key contents: " + key_contents + "  Original:" + response_dict["id"])
                assert key_contents == response_dict["id"]
                
                self.tester.info("Configuring OSG to use RiakCS backend")
                self.tester.modify_property("objectstorage.providerclient","s3")

                endpoint = machine.hostname + ":8080"
                self.tester.info("Configuring OSG to use s3 endpoint: " + endpoint)
                self.tester.modify_property("objectstorage.s3_endpoint", endpoint)

                self.tester.info("Configuring OSG to use s3 access key: " + response_dict["key_id"])
                self.tester.modify_property("objectstorage.s3_access_key", response_dict["key_id"])

                self.tester.info("Configuring OSG to use s3 secret key: " + response_dict["key_secret"][-4:])
                self.tester.modify_property("objectstorage.s3_secret_key",response_dict["key_secret"])

        except IndexError as e:
            self.tester.info("No RIAK component found in component specification. Skipping installation")
            self.tester.info("Configuring OSG to use walrus backend");
            self.tester.modify_property("objectstorage.providerclient", "walrus");
            
if __name__ == "__main__":
    testcase = InstallRiak()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list
    list = testcase.args.tests or ["InstallRiakCS"]

    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list)
    exit(result)