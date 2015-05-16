import json

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
        self.parser.add_argument("--lvm-extents")
        self.parser.add_argument("--vnet-mode", default="MANAGED-NOVLAN")
        self.parser.add_argument("--vnet-subnet", default="1.0.0.0")
        self.parser.add_argument("--vnet-netmask", default="255.255.0.0")
        self.parser.add_argument("--vnet-publicips")
        self.parser.add_argument("--vnet-privateips")
        self.parser.add_argument("--vnet_addrspernet", default="32")
        self.parser.add_argument("--vnet_privinterface", default="br0")
        self.parser.add_argument("--vnet_pubinterface", default="br0")
        self.parser.add_argument("--vnet_bridge", default="br0")
        self.parser.add_argument("--vnet-dns", default="8.8.8.8")
        self.parser.add_argument("--root-lv", default="/dev/vg01/")
        self.parser.add_argument("--dnsdomain")
        self.parser.add_argument("--block-device-manager", default="das")
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        self.tester = Eucaops( config_file=self.args.config_file, password=self.args.password, download_creds=download_creds)
        #if not self.args.branch and not self.args.euca_url and not self.args.enterprise_url:
        #    self.args.branch = self.args.upgrade_to_branch

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
            if machine.distro.name is "vmware":
                continue
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
            if machine.distro.name is "vmware":
                continue
            machine.package_manager.install("eucalyptus-nc")

    def start_components(self):
        for machine in self.tester.get_component_machines("nc"):
            if machine.distro.name is "vmware":
                continue
            machine.sys("service eucalyptus-nc start", timeout=480)
        for machine in self.tester.get_component_machines("cc"):
            machine.sys("service eucalyptus-cc start", timeout=480)
        for machine in self.tester.get_component_machines("sc"):
            machine.sys("service eucalyptus-cloud start", timeout=480)
        for machine in self.tester.get_component_machines("ws"):
            machine.sys("service eucalyptus-cloud start", timeout=480)
        for machine in self.tester.get_component_machines("clc"):
            machine.sys("service eucalyptus-cloud start", timeout=480)

    def stop_components(self):
        for machine in self.tester.get_component_machines("clc"):
            machine.sys("service eucalyptus-cloud stop", timeout=480)
        for machine in self.tester.get_component_machines("sc"):
            machine.sys("service eucalyptus-cloud stop", timeout=480)
        for machine in self.tester.get_component_machines("ws"):
            machine.sys("service eucalyptus-cloud stop", timeout=480)
        for machine in self.tester.get_component_machines("cc"):
            machine.sys("service eucalyptus-cc stop", timeout=480)
        for machine in self.tester.get_component_machines("nc"):
            if machine.distro.name is "vmware":
                continue
            machine.sys("service eucalyptus-nc stop", timeout=480)

    def initialize_db(self):
        first_clc = self.tester.get_component_machines("clc")[0]
        first_clc.sys("euca_conf --initialize")

    def setup_bridges(self):
        nc_machines = self.tester.get_component_machines("nc")
        bridge_interface = "em1"
        for nc in nc_machines:
            if nc.distro.name is "vmware":
                return
            nc.sys("echo 'DEVICE=br0\nBOOTPROTO=dhcp\nONBOOT=yes\nTYPE=Bridge' > /etc/sysconfig/network-scripts/ifcfg-br0")
            nc.sys("echo 'DEVICE=" + bridge_interface +"\nTYPE=Ethernet\nBRIDGE=br0' > /etc/sysconfig/network-scripts/ifcfg-" + bridge_interface)
            nc.sys("service network restart")

    def extend_logical_volume(self, logical_volume="/dev/vg01/lv_root", extents="50%FREE"):
        if self.args.root_lv:
            logical_volume = self.args.root_lv
        if self.args.lv_extents:
            logical_volume= self.args.lv_extents
        for machine in self.tester.config["machines"]:
            machine.sys("lvextend " + logical_volume + " -l" + extents )
            machine.sys("resize2fs -f " + logical_volume, timeout=12000)

    def wait_for_creds(self, timeout=900):
        def get_creds():
            try:
                self.tester = Eucaops(config_file=self.args.config_file, password=self.args.password,download_creds=False)
                self.tester.get_credentials()
                return True
            except Exception:
                return False
        self.tester.wait_for_result(get_creds, True, timeout=timeout)

    def sync_ssh_keys(self):
        ### Sync CLC SSH key to all machines
        clc = self.tester.get_component_machines("clc")[0]
        clc_pub_key = clc.sys("cat ~/.ssh/id_rsa.pub")[0]
        for machine in self.tester.get_component_machines():
            machine.sys("echo " + clc_pub_key + " >> ~/.ssh/authorized_keys")

        ### Sync CC keys to the proper NCs
        try:
            for cluster in ["00", "01", "02", "03"]:
                for machine in self.tester.get_component_machines("cc" + cluster):
                    cc_pub_key = machine.sys("cat ~/.ssh/id_rsa.pub")[0]
                    for nc in self.tester.get_component_machines("nc" + cluster):
                        nc.sys("echo " + cc_pub_key + " >> ~/.ssh/authorized_keys")
        except IndexError:
            pass

    def remove_host_check(self):
        for machine in self.tester.get_component_machines():
            ssh_config_file = 'Host *\nStrictHostKeyChecking no\nUserKnownHostsFile=/dev/null\n'
            #assert isinstance(machine, Machine)
            ssh_config_file = machine.sftp.open("/root/.ssh/config", "w")
            ssh_config_file.write(ssh_config_file)
            ssh_config_file.close()

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

        try:
            for cluster in ["00", "01", "02","03"]:
                for nc in self.tester.get_component_machines("nc" + cluster):
                    for cc in self.tester.get_component_machines("cc" + cluster):
                        cc.sys("euca_conf --register-nodes " + nc.hostname)
        except IndexError:
            pass

    def set_block_storage_manager(self):
        if not hasattr(self.tester, 'service_manager'):
            self.tester = Eucaops(config_file=self.args.config_file, password=self.args.password)
        enabled_clc = self.tester.service_manager.get_enabled_clc()
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
            else:
                ebs_manager = self.args.block_device_manager
            self.tester.modify_property(zone + ".storage.blockstoragemanager", ebs_manager)
            self.tester.modify_property(zone + ".storage.dasdevice", self.args.root_lv)

    def set_config_option(self, machine, option, parameter):
        sed_command = 'sed -i -e "s/^.*{0}=.*$/{0}={1}/" {2}/etc/eucalyptus/eucalyptus.conf'.format(option, parameter, self.tester.eucapath)
        machine.sys(sed_command)

    def configure_network(self):
        for machine in self.tester.get_component_machines("cc"):
            self.set_config_option(machine, "VNET_MODE", self.args.vnet_mode)
            self.set_config_option(machine, "VNET_SUBNET", self.args.vnet_subnet)
            self.set_config_option(machine, "VNET_NETMASK", self.args.vnet_netmask)
            self.set_config_option(machine, "VNET_PUBLICIPS", self.args.vnet_publicips)
            self.set_config_option(machine, "VNET_DNS", self.args.vnet_dns)
            self.set_config_option(machine, "VNET_ADDRSPERNET", self.args.vnet_addrspernet)
            self.set_config_option(machine, "VNET_PRIVINTERFACE", self.args.vnet_privinterface)
            self.set_config_option(machine, "VNET_PUBINTERFACE", self.args.vnet_pubinterface)

        for machine in self.tester.get_component_machines("nc"):
            self.set_config_option(machine, "VNET_MODE", self.args.vnet_mode)
            self.set_config_option(machine, "VNET_BRIDGE", self.args.vnet_bridge)

    def configure_edge_dual_subnet(self):
        if re.search("edge", self.tester.config["network"], re.IGNORECASE):
            if not hasattr(self.tester, 'service_manager'):
                self.tester = Eucaops(config_file=self.args.config_file, password=self.args.password)
            enabled_clc = self.tester.service_manager.get_enabled_clc()
            ip_addr_add_command = "ip addr add {0}/24 dev {1}"
            ### add private subnet GW interface on CC
            cc = self.tester.get_component_machines("cc00")[0]
            cc_interface = "em1"
            base_ip = self.tester.config["subnet_ip"].strip("0")
            private_subnet = base_ip + "0"
            cc_gw_ip = base_ip + "1"
            cc.sys(ip_addr_add_command.format(cc_gw_ip, cc_interface))

            ### Setup IP forwarding
            cc.sys("sysctl -w net.ipv4.ip_forward=1")

            ### Make sure conflicting dhcpd server is not running on Nodes by deleting
            ### hypervisor's default network
            for node in self.tester.service_manager.get_all_node_controllers():
                node.sys('virsh net-destroy default')

            ### add private interface subnet on NC bridges
            ip_index = 2
            for nc in self.tester.get_component_machines("nc"):
                nc_private_ip = base_ip + str(ip_index)
                ip_index += 1
                nc.sys(ip_addr_add_command.format(nc_private_ip, "br0"))

            ### Chunk out private ip pool
            instance_private_ips = []
            for i in xrange(64):
                instance_private_ips.append(base_ip + str(ip_index + i))
            if hasattr(self.args, "vnet_public_ips"):
                public_ips = self.args.vnet_public_ips
            elif "managed_ips" in self.tester.config:
                public_ips = self.tester.config["managed_ips"]
            else:
                raise Exception("Unable to find public ips. Please provide them with --vnet-public-ips")
            ip_list = public_ips.split()
            if len(ip_list) > 1:
                ### individual ips were passed
                public_ips = ip_list
            else:
                public_ips = [public_ips]

            network_config = {"InstanceDnsDomain": "eucalyptus.internal",
                              "InstanceDnsServers": [enabled_clc.hostname],
                              "PublicIps": public_ips,
                              "Subnets": [],
                              "Clusters": [{"Name": "PARTI00",
                                            "MacPrefix": "d0:0d",
                                            "Subnet": {
                                                "Name": private_subnet,
                                                "Subnet": private_subnet,
                                                "Netmask": "255.255.255.0",
                                                "Gateway": cc_gw_ip
                                            },
                                            "PrivateIps": instance_private_ips
                                            }]
                              }
            self.tester.modify_property("cloud.network.network_configuration", "'" + json.dumps(network_config) + "'")

    def setup_dns(self):
        if not hasattr(self.tester, 'service_manager'):
            self.tester = Eucaops(config_file=self.args.config_file, password=self.args.password)
        self.tester.modify_property("bootstrap.webservices.use_dns_delegation", "true")
        self.tester.modify_property("bootstrap.webservices.use_instance_dns", "true")
        enabled_dns = self.tester.service_manager.get_enabled_dns()
        if self.args.dnsdomain:
            self.tester.modify_property("system.dns.dnsdomain", self.args.dnsdomain)
        else:
            hostname = self.tester.get_machine_by_ip(enabled_dns.hostname).sys('hostname')[0].split(".")[0]
            domain = hostname + ".autoqa.qa1.eucalyptus-systems.com"
            self.tester.modify_property("system.dns.dnsdomain", domain)
        self.tester.modify_property("system.dns.nameserveraddress", enabled_dns.hostname)

    def clean_method(self):
        pass

    def InstallEuca(self):
        self.initialize_db()
        self.sync_ssh_keys()
        self.remove_host_check()
        self.configure_network()
        self.start_components()
        self.wait_for_creds()
        self.register_components()
        self.set_block_storage_manager()

if __name__ == "__main__":
    testcase = Install()
    ### Either use the list of tests passed from config/command line to determine what subset of tests to run
    test_list = testcase.args.tests or ["InstallEuca"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in test_list:
        unit_list.append( testcase.create_testunit_by_name(test) )
        ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
