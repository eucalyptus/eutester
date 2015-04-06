#!/usr/bin/python

from eutester.euca.euca_ops import Eucaops
from eutester.utils.eutestcase import EutesterTestCase


class SetupDNS(EutesterTestCase):
    def __init__(self, name="SetupDNS"):
        super(SetupDNS, self).__init__(name=name)
        self.setuptestcase()
        self.setup_parser()
        self.get_args()
        self.tester = Eucaops(config_file=self.args.config, password=self.args.password)

    def clean_method(self):
        pass

    def setup_dns(self):
        if not hasattr(self.tester, 'service_manager'):
            self.tester = Eucaops(config_file=self.args.config_file, password=self.args.password)
        self.tester.modify_property("bootstrap.webservices.use_dns_delegation", "true")
        self.tester.modify_property("bootstrap.webservices.use_instance_dns", "true")
        enabled_clc = self.tester.service_manager.get_enabled_clc()
        hostname = enabled_clc.machine.sys('hostname')[0].split(".")[0]
        domain = hostname + ".autoqa.qa1.eucalyptus-systems.com"
        self.tester.modify_property("system.dns.dnsdomain", domain)
        self.tester.modify_property("system.dns.nameserveraddress", enabled_clc.hostname)

if __name__ == "__main__":
    test_case = SetupDNS()
    test_list = test_case.args.tests or ["setup_dns"]
    unit_list = []
    for test in test_list:
        unit_list.append(test_case.create_testunit_by_name(test) )
    result = test_case.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)