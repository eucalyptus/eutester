#!/usr/bin/env python
#
#
# Description:  This script upgrades a Eucalyptus cloud
import re
from testcases.cloud_admin.install_euca import Install

class Upgrade(Install):
    def __init__(self):
        super(Upgrade, self).__init__(download_creds=True)
        self.clc_service = self.tester.service_manager.get_enabled_clc()
        self.clc = self.clc_service.machine
        self.old_version = self.clc.sys("cat /etc/eucalyptus/eucalyptus-version")[0]
        for machine in self.tester.config["machines"]:
            if re.search(machine.distro.name, "vmware"):
                self.add_enterprise_repo()
                break

    def upgrade_packages(self):
        for machine in self.tester.config["machines"]:
            if machine.distro.name is "vmware":
                continue
            if self.args.nogpg:
                machine.upgrade(nogpg=True)
            else:
                machine.upgrade("eucalyptus")
            ## IF its a CLC and we have a SAN we need to install the san package after upgrade before service start
            if re.search("^3.1", self.old_version):
                if hasattr(self.args, 'ebs_storage_manager'):
                    if re.search("SANManager" ,self.args.ebs_storage_manager):
                        if re.search("clc", " ".join(machine.components)):
                            if hasattr(self.args, 'san_provider'):
                                if re.search("EquallogicProvider", self.args.san_provider):
                                    pass # Nothing to install on CLC for this case
                                if re.search("NetappProvider", self.args.san_provider):
                                    machine.install("eucalyptus-enterprise-storage-san-netapp-libs")
                                if re.search("EmcVnxProvider", self.args.san_provider):
                                    machine.install("eucalyptus-enterprise-storage-san-emc-libs")
                        if re.search("sc", " ".join(machine.components)):
                            if hasattr(self.args, 'san_provider'):
                                if re.search("EquallogicProvider", self.args.san_provider):
                                    machine.install("eucalyptus-enterprise-storage-san-equallogic")
                                if re.search("NetappProvider", self.args.san_provider):
                                    machine.install("eucalyptus-enterprise-storage-san-netapp")
                                if re.search("EmcVnxProvider", self.args.san_provider):
                                    machine.install("eucalyptus-enterprise-storage-san-emc")
            if re.search("^3.2", self.old_version):
                if hasattr(self.args, 'ebs_storage_manager'):
                    if re.search("SANManager" ,self.args.ebs_storage_manager):
                        if re.search("clc", " ".join(machine.components)):
                            if hasattr(self.args, 'san_provider'):
                                if re.search("NetappProvider", self.args.san_provider):
                                    for zone in self.tester.get_zones():
                                        machine.sys("source " + self.tester.credpath + "/eucarc && " +
                                                    self.tester.eucapath + "/usr/sbin/euca-modify-property -p " +
                                                    zone + ".storage.chapuser=" + self.tester.id_generator())
            new_version = machine.sys("cat /etc/eucalyptus/eucalyptus-version")[0]
            if not self.args.nightly and re.match( self.old_version, new_version):
                raise Exception("Version before (" + self.old_version +") and version after (" + new_version + ") are the same")

    def UpgradeAll(self):
        self.add_euca_repo()
        try:
            self.clc.sys("rpm -qa | grep eucalyptus-enterprise", code=0)
            self.add_enterprise_repo()
        except Exception, e:
            pass
        self.stop_components()
        self.upgrade_packages()
        self.start_components()
        self.tester.service_manager.all_services_operational()

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