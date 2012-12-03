__author__ = 'viglesias'
import re
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase

class Install(EutesterTestCase):

    def __init__(self, download_creds=False, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument("--euca-url",)
        self.parser.add_argument("--enterprise-url")
        self.parser.add_argument("--branch")
        self.parser.add_argument("--nogpg",action='store_true')
        self.parser.add_argument("--nightly",action='store_true')
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config_file, password=self.args.password, download_creds=download_creds)
        if not self.args.branch and not self.args.euca_url and not self.args.enterprise_url:
            self.args.branch = self.args.upgrade_to_branch

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
        if self.args.branch:
            self.args.euca_url = self.get_repo_url("eucalyptus", self.args.branch)
        for machine in self.tester.config["machines"]:
            if machine.distro.name is "vmware":
                continue
            machine.add_repo(self.args.euca_url,"euca-upgrade")

    def add_enterprise_repo(self):
        if self.args.branch:
            self.args.enterprise_url =self.get_repo_url("internal", self.args.branch)
        for machine in self.tester.config["machines"]:
            if machine.distro.name is "vmware":
                continue
            machine.add_repo(self.args.enterprise_url, "ent-upgrade")

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
        for machine in self.tester.config["machines"]:
            machine.package_manager.install("ntp")
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

    def start_components(self):
        for machine in self.tester.config["machines"]:
            if machine.distro.name is "vmware":
                continue
            if re.search("cc", " ".join(machine.components)):
                machine.sys("service eucalyptus-cc start")
            if re.search("nc", " ".join(machine.components)):
                machine.sys("service eucalyptus-nc start")
            if re.search("clc", " ".join(machine.components)) or re.search("ws", " ".join(machine.components))\
               or re.search("sc", " ".join(machine.components)) or re.search("vb", " ".join(machine.components)):
                machine.sys("service eucalyptus-cloud start")

    def initialize_db(self):
        first_clc = self.tester.get_component_machines("clc")[0]
        first_clc.sys("euca_conf --initialize")

    def setup_bridges(self):
        nc_machines = self.tester.get_component_machines("nc")
        bridge_interface = "em1"
        for nc in nc_machines:
            nc.sys("echo 'DEVICE=br0\nBOOTPROTO=dhcp\nONBOOT=yes\nTYPE=Bridge' > /etc/sysconfig/network-scripts/ifcfg-br0")
            nc.sys("echo 'DEVICE=" + bridge_interface +"\nTYPE=Ethernet\nBRIDGE=br0' > /etc/sysconfig/network-scripts/ifcfg-" + bridge_interface)
            nc.sys("service network restart")

    def extend_logical_volume(self, logical_volume="/dev/vg01/lv_root", extents="100%FREE"):
        for machine in self.tester.config["machines"]:
            machine.sys("lvextend " + logical_volume + " -l" + extents )
            machine.sys("resize2fs -f " + logical_volume)

    def start_components(self):
        for machine in self.tester.config["machines"]:
            if re.search("clc", " ".join(machine.components)) or re.search("ws", " ".join(machine.components)) or re.search("sc", " ".join(machine.components)):
                machine.sys("service eucalyptus-cloud start")
            if re.search("nc", " ".join(machine.components)):
                machine.sys("service eucalyptus-nc start")
            if re.search("cc", " ".join(machine.components)):
                machine.sys("service eucalyptus-cc start")

    def wait_for_creds(self, timeout=300):
        while timeout > 0:
            try:
                self.tester = Eucaops(config_file=self.args.config_file, password=self.args.password)
                break
            except Exception,e:
                pass
            timeout -= 20
            self.tester.sleep(20)

    def register_components(self):
        clcs = self.tester.get_component_machines("clc")
        if len(clcs) > 1:
            clcs[0].sys("euca_conf --register-cloud -C eucalyptus -P eucalyptus -H " + clcs[1].hostname)
        walrii = self.tester.get_component_machines("ws")
        for walrus in walrii:
            clcs[0].sys("euca_conf --register-walrus -C walrus -P walrus -H " + walrus.hostname)
        ccs = self.tester.get_component_machines("cc")
        registered_clusters = {1:None, 2:None,3:None,4:None,5:None,6:None,7:None,8:None}
        cluster_number = 1
        for cluster in ccs:
            if not registered_clusters[cluster_number]:
                registered_clusters[cluster_number] = [cluster]
                clcs[0].sys("euca_conf --register-cluster -C cluster" + str(cluster_number) +
                            "A -P cluster" + str(cluster_number) + " -H " + cluster.hostname)
                cluster_number += 1
            else:
                registered_clusters[cluster_number-1].append(cluster)
                clcs[0].sys("euca_conf --register-cluster -C cluster" + str(cluster_number) +
                            "B -P cluster" + str(cluster_number) + " -H " + cluster.hostname)

        cluster_number = 1
        scs = self.tester.get_component_machines("sc")
        registered_scs = {1:None, 2:None,3:None,4:None,5:None,6:None,7:None,8:None}
        for sc in scs:
            if not registered_scs[cluster_number]:
                registered_scs[cluster_number] = [sc]
                clcs[0].sys("euca_conf --register-sc -C storage" + str(cluster_number) +
                            "A -P cluster" + str(cluster_number) + " -H " + sc.hostname)
                cluster_number += 1
            else:
                registered_scs[cluster_number-1].append(sc)
                clcs[0].sys("euca_conf --register-sc -C storage" + str(cluster_number-1) +
                            "B -P cluster" + str(cluster_number-1) + " -H " + sc.hostname)

        nodes = self.tester.get_component_machines("nc")
        registered_nodes = {1:None, 2:None,3:None,4:None,5:None,6:None,7:None,8:None}
        cluster_number = 1
        for node in nodes:
            if not registered_nodes[cluster_number]:
                registered_nodes[cluster_number] = [node]
                for cluster in registered_clusters[cluster_number]:
                    cluster.sys("euca_conf --register-nodes " + node.hostname)
                cluster_number += 1
            else:
                registered_nodes[cluster_number-1].append(node)
                for cluster in registered_clusters[cluster_number-1]:
                    cluster.sys("euca_conf --register-nodes " + node.hostname)

    def set_block_storage_manager(self):
        self.clc_service = self.tester.service_manager.get("eucalyptus")[0]
        enabled_clc = self.tester.service_manager.wait_for_service(self.clc_service)
        self.zones = self.tester.get_zones()
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
            enabled_clc.machine.sys("source " + self.tester.credpath + "/eucarc && euca-modify-property -p " + zone + ".storage.blockstoragemanager=" + ebs_manager,code=0)


    def clean_method(self):
        pass


    def InstallEuca(self):
        self.add_euca_repo()
        if self.args.enterprise_url:
            self.add_enterprise_repo()
        self.extend_logical_volume()
        self.install_packages()
        self.initialize_db()
        self.setup_bridges()
        self.start_components()
        self.wait_for_creds()
        self.register_components()
        self.set_block_storage_manager()

if __name__ == "__main__":
    testcase = Install()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    list = testcase.args.tests or [ "InstallEuca"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )
        ### Run the EutesterUnitTest objects

    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
