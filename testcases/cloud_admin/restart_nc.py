#!/usr/bin/python
import os
import time
import random
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from testcases.cloud_user.instances.instancetest import InstanceBasics

class NCAdmin(EutesterTestCase, InstanceBasics):

    def __init__(self, config_file="cloud.conf", password="foobar"):
        self.tester = Eucaops( config_file=config_file, password=password)
        self.servman = self.tester.service_manager
        self.nc_list = self.tester.get_component_machines("nc")
        self.group = self.tester.add_group(group_name="group-" + str(time.time()))
        self.tester.authorize_group_by_name(group_name=self.group.name )
        self.tester.authorize_group_by_name(group_name=self.group.name, port=-1, protocol="icmp" )
        ### Generate a keypair for the instance
        self.keypair = self.tester.add_keypair( "keypair-" + str(time.time()))
        self.keypath = '%s/%s.pem' % (os.curdir, self.keypair.name)
        self.image = self.tester.get_emi(root_device_type="instance-store")
        zones = self.tester.ec2.get_all_zones()
        self.zone = random.choice(zones).name
        self.reservation = None
        self.conf_file = '%s/etc/eucalyptus/eucalyptus.conf' % self.tester.eucapath
        self.nc_restart_time = 30

    def restart_nc(self):
        ## Use reboot testcase to ensure we are able to attach volumes and run instances
        testcase = self.create_testcase_from_method(self.Reboot)

        ## run at least as many instances as there are NCs
        for i in xrange(len(self.nc_list)):
            testcase.run()

        for nc in self.nc_list:
            nc.sys('service eucalyptus-nc restart')

        ## Wait for ncs to come back up
        self.tester.sleep(self.nc_restart_time)

        ## rerun testcase
        for i in xrange(len(self.nc_list)):
            testcase.run()

    def replace_conf_property(self, nc, property, replacement):
        self.default_conf_property(nc, property)
        nc.sys('echo "' + property + '=' + replacement + '" >> ' + self.conf_file)

    def default_conf_property(self,nc, property):
        nc.sys('sed -i \'s/^' +  property + '/#' + property  +'/g\' ' + self.conf_file)

    def disable_caching(self):
        ## Use basic instance testcase testcase to ensure we are able to attach volumes and run instances
        testcase = self.create_testcase_from_method(self.BasicInstanceChecks)
        property = 'NC_CACHE_SIZE'
        ## run at least as many instances as there are NCs
        for i in xrange(len(self.nc_list)):
            testcase.run()

        for nc in self.nc_list:
            self.replace_conf_property(nc,  property, "0")
            command_list = ['service eucalyptus-nc stop',
                            'rm -rf {0}/var/lib/eucalyptus/instances/cache/*'.format(self.tester.eucapath),
                            'service eucalyptus-nc start']
            for command in command_list:
                nc.sys(command)

        ## Wait for ncs to come back up
        self.tester.sleep(self.nc_restart_time)

        testcase = self.create_testcase_from_method(self.Churn)
        ## rerun testcase

        testcase.run()
        for nc in self.nc_list:
            self.default_conf_property(nc, property)

    def cleanup(self):
        self.tester.cleanup_artifacts()

    def run_suite(self):
        self.testlist = []
        testlist = self.testlist
        #testlist.append(self.create_testcase_from_method(self.restart_nc))
        testlist.append(self.create_testcase_from_method(self.disable_caching))
        self.run_test_case_list(testlist)
        self.cleanup()

if __name__ == "__main__":
    parser = NCAdmin.get_parser()
    args = parser.parse_args()
    nc_admin_suite = NCAdmin(config_file=args.config, password = args.password)
    nc_admin_suite.run_suite()
   
