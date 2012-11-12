#!/usr/bin/env python
#
#
# Description:  This script upgrades a Eucalyptus cloud
import re
from eucaops import Eucaops
from eutester.euservice import Euservice
from eutester.eutestcase import EutesterTestCase

class Upgrade(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--euca-url",)
        self.parser.add_argument("--enterprise-url")
        self.parser.add_argument("--branch")
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config_file, password=self.args.password)
        self.clc_service = self.tester.service_manager.get("eucalyptus")[0]
        self.zones = self.tester.get_zones()
        if not self.args.branch and not self.args.euca_url and not self.args.enterprise_url:
            self.args.branch = self.args.upgrade_to_branch
        machine = self.tester.get_component_machines("clc")[0]
        self.old_version = machine.sys("cat /etc/eucalyptus/eucalyptus-version")[0]
        ### IF we were passed a branch, fetch the correct repo urls from the repo API
        if self.args.branch:
            self.args.euca_url = self.get_repo_url("eucalyptus", self.args.branch)
            self.args.enterprise_url =self.get_repo_url("internal", self.args.branch)

    def clean_method(self):
        pass

    def get_repo_url(self, repo = "eucalyptus", branch = "testing"):
        import httplib
        api_host = "packages.release.eucalyptus-systems.com"
        machine = self.tester.get_component_machines("clc")[0]
        path="/api/1/genrepo/?distro="+str(machine.distro.name)+"&releasever=6&arch=x86_64&url=repo-euca@git.eucalyptus-systems.com:"+str(repo)+"&ref="+str(branch) + "&allow-old"
        conn=httplib.HTTPConnection(api_host)
        conn.request("GET", path)
        res=conn.getresponse()
        repo_url = res.read().strip()
        self.tester.debug("Setting " + repo + " URL to: " + repo_url)
        return repo_url

    def add_euca_repo(self):
        for machine in self.tester.config["machines"]:
            machine.add_repo(self.args.euca_url,"euca-upgrade")

    def add_enterprise_repo(self):
        for machine in self.tester.config["machines"]:
            machine.add_repo(self.args.enterprise_url, "ent-upgrade")

    def upgrade_packages(self):
        for machine in self.tester.config["machines"]:
            machine.upgrade()
            new_version = machine.sys("cat /etc/eucalyptus/eucalyptus-version")[0]
            if re.match( self.old_version, new_version):
                raise Exception("Version before (" + self.old_version +") and version after (" + new_version + ") are the same")

    def start_components(self):
        for machine in self.tester.config["machines"]:
            if re.search("cc", " ".join(machine.components)):
                machine.sys("service eucalyptus-cc start")
            if re.search("nc", " ".join(machine.components)):
                machine.sys("service eucalyptus-nc start")
            if re.search("clc", " ".join(machine.components)) or re.search("ws", " ".join(machine.components))\
               or re.search("sc", " ".join(machine.components)) or re.search("vb", " ".join(machine.components)):
                machine.sys("service eucalyptus-cloud start")


    def set_block_storage_manager(self):
        enabled_clc = self.tester.service_manager.wait_for_service(self.clc_service)
        for zone in self.zones:
            ebs_manager = "overlay"
            if hasattr(self.args, 'ebs_storage_manager'):
                if re.search("DASManager" ,self.args.ebs_storage_manager):
                    ebs_manager = "das"
                if re.search("SANManager" ,self.args.ebs_storage_manager):
                    if hasattr(self.args, 'san_provider'):
                        if re.search("EquallogicProvider", self.args.san_provider):
                            ebs_manager = "equallogic"
                        if re.search("NetappProvider", self.args.san_provider):
                            ebs_manager = "netapp"
                        if re.search("EmcVnxProvider", self.args.san_provider):
                            ebs_manager = "emc-fastsnap"
            enabled_clc.machine.sys("source " + self.tester.credpath + "/eucarc && euca-modify-property -p " + zone + ".storage.blockstoragemanager" + ebs_manager,code=0)


    def UpgradeAll(self):
        self.add_euca_repo()
        if self.args.enterprise_url:
            self.add_enterprise_repo()
        self.upgrade_packages()
        self.start_components()
        if re.search("^3.1", self.old_version):
            self.set_block_storage_manager()


if __name__ == "__main__":
    testcase = Upgrade()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ "UpgradeAll"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
        ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)