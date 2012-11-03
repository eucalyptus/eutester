__author__ = 'viglesias'
import unittest
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from testcases.cloud_user.instances.instancetest import InstanceBasics

class NCAdmin(EutesterTestCase):

    def __init__(self, repo_url, config_file="cloud.conf", password="foobar"):
        self.tester = Eucaops( config_file=config_file, password=password, download_creds=False)
        self.repo_url = repo_url
        self.euca2ools_url = 'http://mirror.eucalyptus/qa-pkg-storage/qa-euca2ools-pkgbuild/latest-success/phase3/centos/6/x86_64'

    def add_repos(self):
        for machine in self.tester.get_component_machines("clc"):
            machine.package_manager.add_repo(self.repo_url, "eucalyptus")
            machine.package_manager.add_repo(self.euca2ools_url, "euca2ools")
        for machine in self.tester.get_component_machines("ws"):
            machine.package_manager.add_repo(self.repo_url, "eucalyptus")
        for machine in self.tester.get_component_machines("cc"):
            machine.package_manager.add_repo(self.repo_url, "eucalyptus")
        for machine in self.tester.get_component_machines("sc"):
            machine.package_manager.add_repo(self.repo_url, "eucalyptus")
        for machine in self.tester.get_component_machines("nc"):
            machine.package_manager.add_repo(self.repo_url, "eucalyptus")
            machine.package_manager.add_repo(self.euca2ools_url, "euca2ools")

    def install_packages(self):
        for machine in self.tester.get_component_machines("clc"):
            machine.package_manager.install("eucalyptus-cloud")
        for machine in self.tester.get_component_machines("ws"):
            machine.package_manager.install("eucalyptus-walrus")
        for machine in self.tester.get_component_machines("cc"):
            machine.package_manager.install("eucalyptus-cc")
        for machine in self.tester.get_component_machines("sc"):
            machine.package_manager.install("eucalyptus-sc")
        for machine in self.tester.get_component_machines("nc"):
            machine.package_manager.install("eucalyptus-nc")

    def initialize_db(self):
        first_clc = self.tester.get_component_machines("clc")[0]
        first_clc.sys("euca_conf --initialize")

    def setup_bridges(self):
        nc_machines = self.tester.get_component_machines("nc")
        bridge_interface = "eth0"
        for nc in nc_machines:
            nc.sys("echo 'DEVICE=br0\nBOOTPROTO=dhcp\nONBOOT=yes\nTYPE=Bridge' > /etc/sysconfig/network-scripts/ifcfg-br0")
            nc.sys("echo 'DEVICE=" + bridge_interface +"\nTYPE=Ethernet\nBRIDGE=br0' > /etc/sysconfig/network-scripts/ifcfg-" + bridge_interface)
            nc.sys("service network restart")

    def setup_disks(self):
        for machine in self.tester.config["machines"]:
            machine.mkfs("/dev/sda3")
            machine.mount("/dev/sda3","/var/lib/eucalyptus/")
            machine.chown("eucalyptus", "/var/lib/eucalyptus")

    def start_components(self):
        for machine in self.tester.config["machines"]:
            if "clc" in machine.components or "ws" in machine.components or "sc" in machine.components:
                machine.sys("service eucalyptus-cloud start")
            if "nc" in machine.components:
                machine.sys("service eucalyptus-nc start")
            if "cc" in machine.components:
                machine.sys("service eucalyptus-cc start")

    def cleanup(self):
        self.tester.cleanup_artifacts()


    def run_testcase_thread(self, queue,delay = 20, name="MetaData"):
        ### Thread that runs a testcase (function) and returns its pass or fail result
        self.tester.sleep(delay)
        try:
            result = unittest.TextTestRunner(verbosity=2).run(self.name)
        except Exception, e:
            queue.put(1)
            raise e
        if result.wasSuccessful():
            self.tester.debug("Passed test: " + name)
            queue.put(0)
            return False
        else:
            self.tester.debug("Failed test: " + name)
            queue.put(1)
            return True

    def run_suite(self):
        testlist = []
        testlist.append(self.create_testcase_from_method(self.install_packages))
        testlist.append(self.create_testcase_from_method(self.initialize_db))
        testlist.append(self.create_testcase_from_method(self.setup_bridges))
        testlist.append(self.create_testcase_from_method(self.setup_disks))
        testlist.append(self.create_testcase_from_method(self.start_components))
        self.run_test_case_list(testlist)
        self.cleanup()

if __name__ == "__main__":
    parser = NCAdmin.get_parser()
    parser.add_argument('--repo-url',
        help="pre-installed emi id which to execute these tests against", default="")
    args = parser.parse_args()
    nc_admin_suite = NCAdmin(args.repo_url, config_file=args.config, password = args.password)
    nc_admin_suite.run_suite()
