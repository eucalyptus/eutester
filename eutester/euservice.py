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
# Author: vic.iglesias@eucalyptus.com

import re
import time
from eutester import sshconnection
from eutester.sshconnection import SshCbReturn, CommandTimeoutException
import types
import stat
import eutester
import copy
import os
from eutester import machine
from xml.dom.minidom import parse, parseString
import dns.resolver


class log_marker:
    def __init__(self,
                 tester,
                 components,
                 start_marker=None,
                 log_files=None):
        """
        Manages unique markers placed in log/text files on a list of components.
        Intended to be used to indicate start and stop points of operations within the multiple sets of logs on multiple
        systems. These log segments can then collected, analyzed, etc. at a later point in time.

        :param tester: eutester object
        :param components: list of component objs to operate on
        :param start_marker: unique string, this will be auto-generated if not provided.
        :param log_files: list of files (using full path to files to mark/operate upon on remote components

        """
        self.tester = tester
        self.components = components
        self.start_marker = start_marker or "eutester_marker_start:" + \
                                         str(time.time()) + str(self.tester.id_generator(size=10))
        self.log_files = log_files
        self.start_time = time.time()
        self.end_marker = None
        self.end_time = None
        self.elapsed = None


    def add_start_marker(self, components=None, log_files=None, marker=None):
        """
        Attempts to add a unique 'marker' in the 'log_files' provided in all the 'components' provided.

        :param components:
        :param log_files:
        :param marker:
        """
        marker = marker or self.start_marker
        log_files = log_files or self.log_files
        components = components or self.components

        for component in components:
            if component.machine:
                log_files = log_files or component.log_files

        return marker



class Eunode:
    def __init__(self,
                 tester,
                 hostname,
                 partition,
                 name=None,
                 instance_ids=None,
                 instances=None,
                 state = None,
                 machine = None,
                 debugmethod = None,
                 ):
        """
        init object containing node related info and methods

        :param hostname: mandatory - string - hostname of the node (ie: 192.168.1.1)
        :param partition: mandatory - string - partition name of the node (ie PARTI00)
        :param name:  optional string - optional name for this eunode. Defaults to hostname
        :param instances: - optional -list of instance strings reported on this node
        :param machine: optional eutester machine type object
        :param tester: - eutester obj
        """
        type = EuserviceManager.node_type_string
        self.hostname = hostname
        self.partition = partition
        self.part_name = partition.name
        self.name = name or self.hostname
        self.instance_ids = instance_ids or []
        self.state = state
        self.tester = tester
        self.machine = machine
        self.service_state = None
        self.debugmethod = debugmethod or self.tester.debug

        if not machine:
            try:
                self.machine = self.tester.get_machine_by_ip(hostname)
                self.get_service_state()
            except Exception, e:
                self.debug("Failed to get machine for this node:" + str(hostname) + ", err:" + str(e))
        #if self.machine:
            #self.hypervisor =


    def debug(self, msg):
        """
        Simple method to print debug messsage 'msg'
        :param msg: message to be printed
        """
        if self.debugmethod:
            self.debugmethod(msg)
        else:
            print(msg)


    def sys(self, cmd, code=None):
        """
        Command to be executed via ssh on remote eunode machine
        :param cmd: string - command to be executed
        :param code: int - optional exit code used to determine pass fail of remote command.
        :return: list of lines from remote cmd's output
        """
        return self.machine.sys(cmd,code=code)

    def stop(self):
        self.sys(self.tester.eucapath + "/etc/init.d/eucalyptus-nc stop", code=0)

    def start(self):
        self.sys(self.tester.eucapath + "/etc/init.d/eucalyptus-nc start", code=0)

    def get_hypervisor_from_euca_conf(self):
        """
        Attempts to find HYPERVISOR value in <eucalytpus home>/etc/eucalyptus.conf

        :return: string representing hypervisor type if found
        """
        hypervisor =  None
        out = self.sys("cat /etc/eucalyptus/eucalyptus.conf | grep '^HYPER'")
        if out and re.search('^HYPERVISOR=',out[0]):
            hypervisor = out[0].split('=')[1].strip().strip('"')
        return hypervisor


    def get_service_state(self):
        service_state = None
        if self.machine:
            try:
                if self.machine.distro.name is not "vmware":
                    self.sys("service eucalyptus-nc status", code=0)
                    service_state = 'running'
                else:
                    service_state = 'running'
            except sshconnection.CommandExitCodeException:
                service_state = 'not_running'
            except Exception, e:
                self.debug('Could not get service state from node:' + str(self.hostname) + ", err:"+str(e))
        else:
            print "No machine object for this eunode:" + str(self.hostname)
        self.service_state = service_state
        return service_state


    def get_virsh_list(self):
        """
        Return a dict of virsh list domains.
        dict should have dict['id'], dict['name'], dict['state']

        """
        instance_list = []
        if self.machine:
            keys = []
            output = self.machine.sys('virsh list', code=0)
            if len(output) > 1:
                keys = str(output[0]).strip().lower().split()
                for line in output[2:]:
                    line = line.strip()
                    if line == "":
                        continue
                    domain_line = line.split()
                    instance_list.append({keys[0]:domain_line[0], keys[1]:domain_line[1], keys[2]:domain_line[2]})
        return instance_list

    def tail_instance_console(self,
                              instance,
                              max_lines=None,
                              timeout=30,
                              idle_timeout=30,
                              print_method=None):
        '''


        '''
        if timeout < idle_timeout:
            idle_timeout = timeout
        if not isinstance(instance,types.StringTypes):
            instance = instance.id
        console_path = self.get_instance_console_path(instance)
        start_time = time.time()
        lines_read = 0
        print_method = print_method or self.debug
        prefix = str(instance) + " Console Output:"
        try:
            self.machine.cmd('tail -F ' + str(console_path),
                             verbose=False,
                             cb=self.remote_tail_monitor_cb,
                             cbargs=[instance,
                                     max_lines,
                                     lines_read,
                                     start_time,
                                     timeout,
                                     print_method,
                                     prefix,
                                     idle_timeout],
                             timeout=idle_timeout)
        except CommandTimeoutException, cte:
            self.debug('Idle timeout fired while tailing console: ' + str(cte))


    def remote_tail_monitor_cb(self,
                               buf,
                               instance_id,
                               max_lines,
                               lines_read,
                               start_time,
                               timeout,
                               print_method,
                               prefix,
                               idle_timeout):
        ret = SshCbReturn(stop=False, settimer=idle_timeout)
        return_buf = ""
        now = time.time()
        if (timeout and (now - start_time) >= timeout) or (max_lines and lines_read >= max_lines):
            ret.statuscode = 0
            ret.stop = True
        try:
            for line in str(buf).splitlines():
                lines_read += 1
                print_method(str(prefix) + str(line))
        except Exception, e:
            return_buf = "Error in remote_tail_monitor:" + str(e)
            ret.statuscode = 69
            ret.stop = True
        finally:
            ret.buf = return_buf
            ret.nextargs = [instance_id, max_lines, lines_read, start_time,timeout]
            return ret


    def get_instance_multipath_dev_info_for_instance_ebs_volume(self, instance, volume):
        if not isinstance(instance,types.StringTypes):
            instance = instance.id
        if isinstance(volume,types.StringTypes):
            volume = self.tester.get_volume(volume_id=volume)
        if volume.attach_data and volume.attach_data.instance_id == instance:
            dev = volume.attach_data.device
        else:
            raise Exception(str(volume.id) + 'Vol not attached to instance: ' + str(instance))
        return self.get_instance_multipath_dev_info_for_instance_block_dev(instance, dev)


    def get_instance_multipath_dev_info_for_instance_block_dev(self, instance, ebs_block_dev, verbose=False):
        if not isinstance(instance,types.StringTypes):
            instance = instance.id
        mpath_dev = self.get_instance_multipath_dev_for_instance_block_dev(instance, ebs_block_dev)
        mpath_dev_info = self.machine.sys('multipath -ll ' + str(mpath_dev) + " | sed 's/[[:cntrl:]]//g' ",
                                          verbose=verbose, code=0)
        return mpath_dev_info

    def get_instance_multipath_dev_for_instance_ebs_volume(self, instance, volume):
        if not isinstance(instance,types.StringTypes):
            instance = instance.id
        if isinstance(volume,types.StringTypes):
            volume = self.tester.get_volume(volume_id=volume)

    def get_instance_multipath_dev_for_instance_block_dev(self, instance, ebs_block_dev, verbose=False):
        mpath_dev = None
        ebs_block_dev = os.path.basename(ebs_block_dev)
        if not isinstance(instance,types.StringTypes):
            instance = instance.id
        dm_dev = self.get_instance_block_disk_dev_on_node(instance, ebs_block_dev)
        sym_links = self.machine.sys('udevadm info --name ' + str(dm_dev) + ' --query symlink',
                                     verbose=verbose, code=0)[0]
        for path in str(sym_links).split():
            if str(path).startswith('mapper/'):
                mpath_dev = path.split('/')[1]
                break
        return mpath_dev


    def get_instance_block_disk_dev_on_node(self, instance, block_dev):
        block_dev = os.path.basename(block_dev)
        if not isinstance(instance,types.StringTypes):
            instance = instance.id
        paths = self.get_instance_block_disk_source_paths(instance)
        sym_link  = paths[block_dev]
        real_dev = self.machine.sys('readlink -e ' + sym_link, verbose=False, code=0)[0]
        fs_stat = self.machine.get_file_stat(real_dev)
        if stat.S_ISBLK(fs_stat.st_mode):
            return real_dev
        else:
            raise(str(instance) + ", dev:" + str(block_dev) + ',Error, device on node is not block type :' + str(real_dev))

    def get_instance_block_disk_source_paths(self, instance, target_dev=None):
        '''
        Returns dict mapping target dev to source path dev/file on NC
        Example return dict: {'vdb':'/NodeDiskPath/dev/sde'}
        '''
        ret_dict = {}
        if target_dev:
            target_dev = os.path.basename(target_dev)
        if not isinstance(instance,types.StringTypes):
            instance = instance.id
        disk_doms = self.get_instance_block_disk_xml_dom_list(instance_id=instance)
        for disk in disk_doms:
            source_dev = disk.getElementsByTagName('source')[0].attributes.get('dev').nodeValue
            target_bus = disk.getElementsByTagName('target')[0].attributes.get('dev').nodeValue
            if not target_dev or target_dev == target_bus:
                ret_dict[target_bus] = str(source_dev)
        return ret_dict

    def get_instance_console_path(self, instance_id):
        if not isinstance(instance_id,types.StringTypes):
            instance = instance_id.id
        dev_dom = self.get_instance_device_xml_dom(instance_id=instance_id)
        console_dom = dev_dom.getElementsByTagName('console')[0]
        return console_dom.getElementsByTagName('source')[0].attributes.get('path').nodeValue


    def get_instance_device_xml_dom(self, instance_id):
        if not isinstance(instance_id,types.StringTypes):
            instance = instance_id.id
        dom = self.get_instance_xml_dom(instance_id)
        return dom.getElementsByTagName('devices')[0]

    def get_instance_block_disk_xml_dom_list(self, instance_id):
        if not isinstance(instance_id,types.StringTypes):
            instance = instance_id.id
        dev_dom = self.get_instance_xml_dom(instance_id)
        return dev_dom.getElementsByTagName('disk')

    def get_instance_xml_dom(self, instance_id):
        if not isinstance(instance_id,types.StringTypes):
            instance = instance_id.id
        output = self.get_instance_xml_text(instance_id)
        dom_xml = parseString(output)
        return dom_xml.getElementsByTagName('domain')[0]

    def get_instance_xml_text(self, instance_id):
        if not isinstance(instance_id,types.StringTypes):
            instance = instance_id.id
        return self.machine.sys('virsh dumpxml ' + str(instance_id),listformat=False, verbose=False, code=0)


    #def get_iscsi_connections(self,):
    #def get_exported_volumes(self,)
    #def get_all_instances_on_node(self, instance_id=None, state=None)



class Euservice(object):

    activeactive_service_types = ["objectstorage"]
    
    def __init__(self, service_string, tester = None):
        values = service_string.split()
        self.type = values[1]
        self.partition = values[2]
        self.name = values[3]
        self.state = values[4]
        self.uri = values[6]
        self.fullname = values[7]
        self.hostname = self.uri.split(":")[1].split("/")[2]
        self.running = True
        self.tester = tester
        self.machine = None
        if self.tester:
            self.machine = tester.get_machine_by_ip(self.hostname)
        
    def isEnabled(self):
        if re.search('ENABLED',self.state) :
            return True
        else:
            return False
        
    def isDisabled(self):
        if not re.search('ENABLED', self.state):
            return True
        else:
            return False
    
    def isActiveActive(self):
        return self.type in Euservice.activeactive_service_types
        
    def disable(self):
        self.tester.service_manager.disable(self)
        
    def enable(self):
        self.tester.service_manager.enable(self)
    
    def stop(self):
        self.tester.service_manager.stop(self)
    
    def start(self):
        self.tester.service_manager.start(self)

    def get_service_string(self):
        if self.type == 'cluster':
            return 'eucalyptus-cc'
        else:
            return 'eucalyptus-cloud'

    def print_self(self, header=True, footer=True, printmethod=None):
        part_len = 16 #self.partition
        type_len  = 16 #self.type
        hostname_len = 24 #self.hostname
        state_len = 10 #self.state
        uri_len = 36 #self.uri
        buf = "\n"
        line = "------------------------------------------------------------------------------------------------------------------------------------------"
        if header:
            buf += str(line+"\n")
            buf += str('PARTITION').center(part_len)+'|'+str('TYPE').center(type_len)+'|'+str('HOSTNAME').center(hostname_len)+'|'+str('STATE').center(state_len)+'|'+str('URI').center(uri_len)+'\n'
            buf += str(line+"\n")
        buf += str(self.partition).center(part_len)+'|'+str(self.type).center(type_len)+'|'+str(self.hostname).center(hostname_len)+'|'+str(self.state).center(state_len)+'|'+str(self.uri).center(uri_len)
        if footer:
            buf += str("\n"+ line)
        if printmethod:
            printmethod(buf)
        return buf

    @staticmethod
    def create_service(service_string, tester=None):
        if service_string.split()[1] == 'dns':
            return DnsService(service_string)
        else:
            return Euservice(service_string, tester)



class DnsService(Euservice):
    def __init__(self, service_string):
        super(DnsService, self).__init__(service_string)
        self.resolver = dns.resolver.Resolver(configure=False)
        self.resolver.nameservers = [self.hostname]

    def resolve(self, name, timeout=360, poll_count=20):
        """Resolve hostnames against the Eucalyptus DNS service"""
        poll_sleep = timeout/poll_count
        for _ in range(poll_count):
            try:
                print("DNSQUERY: Resolving `{0}' against nameserver(s) {1}".format(name, self.resolver.nameservers))
                ans = self.resolver.query(name)
                return str(ans[0])
            except dns.resolver.NXDOMAIN:
                raise Exception("Unable to resolve hostname `{0}'".format(name))
            except dns.resolver.NoNameservers:
                # Note that this usually means our DNS server returned a malformed message
                pass
            finally:
                time.sleep(poll_sleep)
        raise Exception("Unable to resolve hostname `{0}'".format(name))


        
class Partition:

    
    def __init__(self, name, service_manager ):
        self.name = name
        self.service_manager = service_manager
        name = ""
        self.ccs = []
        self.scs = []
        self.vbs = []
        self.ncs = []
        self.volumes = []
        self.instances = []
        
    def get_enabled(self, list):
        self.service_manager.update()
        for service in list:
            if service.isEnabled():
                return service
        raise Exception("Unable to find an enabled service in: " + str(list))
    
    def get_disabled(self, list):
        self.service_manager.update()
        for service in list:
            if not service.isEnabled():
                return service
        raise Exception("Unable to find an disabled service in: " + str(list))
    
    def get_enabled_cc(self):
        return self.get_enabled(self.ccs)
    
    def get_enabled_sc(self):
        return self.get_enabled(self.scs)
    
    def get_enabled_vb(self):
        return self.get_enabled(self.vbs)
    
    def get_disabled_cc(self):
        return self.get_disabled(self.ccs)
    
    def get_disabled_sc(self):
        return self.get_disabled(self.scs)
    
    def get_disabled_vb(self):
        return self.get_disabled(self.vbs)
 
class EuserviceManager(object):
    cluster_type_string = "cluster"
    walrus_type_string = 'walrus'
    osg_type_string = 'osg'
    storage_type_string = 'storage'
    clc_type_string = 'eucalyptus'
    node_type_string = 'node'
    osg_type_string='objectstorage'

        
    def __init__(self, tester ):
        '''
        SERVICE    storage            PARTI00            SC_61              ENABLED       16      http://192.168.51.32:8773/services/Storage    arn:euca:eucalyptus:PARTI00:storage:SC_61/
        update this service based up on the information parsed out of the "describestring"
        '''
        ### Make sure i have the right connection to make first contact with euca-describe-services
        self.walruses= []
        self.osgs = []
        self.clcs = []
        self.arbitrators = []
        self.partitions = {}
        self.internal_components = []
        self.dns = None
        self.all_services = []
        self.node_list = []
        self.tester = tester
        self.debug = tester.debug
        self.eucaprefix = ". " + self.tester.credpath + "/eucarc && " + self.tester.eucapath
        if self.tester.clc is None:
            raise AttributeError("Tester object does not have CLC machine to use for SSH")
        self.last_updated = None
        self.update()

    @eutester.Eutester.printinfo
    def get(self, type=None, partition=None, attempt_both=True, poll_interval=15, allow_clc_start_time=300):
        """
        Method attempts to 'get' euservices by parsing euca-describe-services on the CLC(s). The method
        will do some basic service state checks as well as wait for a reasonable amount
        of time 'allow_clc_start_time' in seconds to allow the eucalyptus service(s) to initialize/sync and be ready
        to service requests.

        :param type: service type string to filter returned services list by
        :param partition: partition, aka zone, aka cluster to filter by.
        :param attempt_both: When set, query the alternate CLC if the first errors
        :param allow_clc_start_time: In the case both CLCs are not responding, this is used as the timeout. This time
                                     represents the amount of time allowed from the time the clc process(s) were started.
                                     If a valid response is not detected, this method will error out.
        :return: list of euservices
        """

        good_clc_hosts = []
        describe_services = []
        services = []
        clc_hostnames = ""
        err_msg = ""
        dbg_msg = ""

        if type is not None:
            type = " -T " + str(type) 
        else:
            type = ""
        #### This is a hack around the fact that the -P filter is not working need to fix this once that functionality is fixed
        if partition is None:
            partition = ""
        #Check each CLC to make sure the eucalyptus-cloud service is running on that machine
        if attempt_both:
            clc_machines =self.tester.get_component_machines("clc")
        else:
            clc_machines =[self.tester.clc]

        for clc_machine in clc_machines:
            clc_hostnames += clc_machine.hostname + ","
            if clc_machine.get_eucalyptus_cloud_is_running_status():
                #Add to front of check list if this is the current tester clc, otherwise append to end.
                if clc_machine == self.tester.clc:
                    good_clc_hosts.insert(0,clc_machine)
                else:
                    good_clc_hosts.append(clc_machine)
            else:
                self.debug('Eucalyptus cloud was not found running on CLC:'+str(clc_machine.hostname))

        for clc_host in good_clc_hosts:
            dbg_msg += clc_host.hostname + ", "
        self.debug("Checking the following CLCs for services/status: " + str(dbg_msg) + "...")
        while good_clc_hosts and not describe_services:
            clc_process_uptimes = []
            process_uptime = None
            for clc in good_clc_hosts:
                try:
                    #Save proess uptime for potential debug if request fails.
                    process_uptime = self.tester.clc.get_eucalyptus_cloud_process_uptime()
                    #Store all CLC's process uptimes in list, compare for youngest later...
                    clc_process_uptimes.append(process_uptime)
                    out = clc.sys(self.eucaprefix + "/usr/sbin/euca-describe-services " + str(type), code=0,timeout=15)
                    for line in out:
                        if re.search("SERVICE.+"+str(partition), line):
                            describe_services.append(line)
                    if not describe_services:
                        raise IndexError("Did not receive proper response from describe services when looking for " + str(type))
                    else:
                        #if the check was successful, we may need to swap the tester's primary clc
                        if clc != self.tester.clc:
                            self.tester.swap_clc()
                        break
                except Exception, e:
                    self.debug("Did not get a valid response from clc:" + str(clc.hostname) +", err:" +str(e))
                    err_msg += str(e) + "\n"
                    # Check to make sure the CLC process is evening running on this machine, and if the youngest CLC process
                    # has been up for a reasonable amount of time to sync and/or service requests.
                    is_running = self.tester.clc.get_eucalyptus_cloud_is_running_status()
                    if not is_running:
                        good_clc_hosts.remove(self.tester.clc)
                        err_msg += "Error in service request on CLC:" + str(self.tester.clc.hostname) \
                                   + ". PID uptime:" + str(process_uptime) + "/" + str(allow_clc_start_time) \
                                   + ", service_running:"+ str(is_running) + "\n"
            #If we've checked both CLCs and still don't have a valid response to parse, 'and' the youngest CLC
            #process uptime has exceeed 'allow_clc_start_time' then raise error.
            if not good_clc_hosts or \
                    not clc_process_uptimes or \
                    (not describe_services and min(clc_process_uptimes) > allow_clc_start_time):
                raise Exception("Could not get services from " + str(clc_hostnames)
                                + ", after clc process uptime of at least "
                                + str(allow_clc_start_time) + "\nErrors:"+str(err_msg))
            if not describe_services:
                time.sleep(poll_interval)
        #Create euservice objects from command output and return list of euservices.
        for service_line in describe_services:
            services.append(Euservice.create_service(service_line, self.tester))
        return services

    def print_services_list(self, services=None):
        services = services or self.all_services
        services_list = copy.copy(services)
        service1 = services_list.pop(0)
        buf = service1.print_self()
        for service in services_list:
            buf += service.print_self(header=False,)
        self.debug(buf)



    def reset(self):
        self.walruses= []
        self.osgs = []
        self.clcs = []
        self.arbitrators = []
        self.internal_components = []
        for k, v in self.partitions.iteritems():
            self.partitions[k].ccs = []
            self.partitions[k].scs = []
            self.partitions[k].vbs = []


    def compare_versions(self, version1, version2):
        '''
        :param version1:
        :param version2:
        :returns: 1 - if version1 is newer than version2
        :returns: 0 - if versions are equal
        :returns: -1 - if version1 is older than version2
        '''
        ver1 = str(version1).split('.')
        ver2 = str(version2).split('.')
        if not ver1 or not ver2:
            raise Exception('Failed to parse versions from strings:' + str(version1) + ", " + str(version2))
        while ver1:
            if not len(ver2):
                return 1
            sub_ver1 = int(ver1.pop(0))
            sub_ver2 = int(ver2.pop(0))
            if sub_ver1 > sub_ver2:
                return 1
            if sub_ver1 < sub_ver2:
                return -1
        #version 1 has no additional sub release ids, and until this point ver1 == ver2...
        while ver2:
            if int(ver2.pop(0)) != 0:
                #ver2 has a none '0' sub release id so it is > than ver1
                return -1
        #versions are equal
        return 0


    def populate_nodes(self, enabled_clc=None):
        """
        Sort output of 'list nodes cmd' on clc, create/update eunode objects.
        Returned list is used to update:'service_manager.node_list'

        :param enabled_clc: To avoid an update() or update() loop the current enabled clc can be provided. This can
                            also be used to test nc lookup on disabled CLC by providing this component obj instead.
        :return: list of eunode objects
        """
        return_list = []
        #to avoid update() loop allow enabled_clc to be provided as arg
        clc = enabled_clc or self.get_enabled_clc()
        clc_version = clc.machine.get_eucalyptus_version()
        if self.compare_versions(clc_version,'3.3') >= 0:
            try:
                return self.populate_nodes_3_3(enabled_clc)
            except:
                return self.populate_nodes_pre_3_3(enabled_clc)
        else:
            return self.populate_nodes_pre_3_3(enabled_clc)


    def populate_nodes_3_3(self, enabled_clc=None):
        """
        Sort output of 'list nodes cmd' on clc, create/update eunode objects.
        Returned list is used to update:'service_manager.node_list'

        :param enabled_clc: To avoid an update() or update() loop the current enabled clc can be provided. This can
                            also be used to test nc lookup on disabled CLC by providing this component obj instead.
        :return: list of eunode objects

        version >= 3.3.0 output (note state and instances on lines to follow node(s)
        [type]  [partition]     [node hostname] [state]
        NODE    PARTI00         192.168.51.15   ENABLED
        NODE    PARTI00         192.168.51.13   ENABLED
        [type]           [instances per line]
        INSTANCE        i-A1BE4281
        """
        type_loc = 0
        partition_loc = 1
        hostname_loc = 2
        state_loc = 3
        instance_id_loc = 1
        return_list = []
        instance_list = []
        last_node = None
        #to avoid update() loop allow enabled_clc to be provided as arg
        clc = enabled_clc or self.get_enabled_clc()
        nodes_strings = clc.machine.sys(self.eucaprefix + \
                                        "/usr/sbin/euca_conf --list-nodes 2>1 | grep 'NODE\|INSTANCE'")
        for node_string in nodes_strings:
            #handle/skip any blank lines first...
            node_string = node_string.strip()
            if not node_string:
                continue
            partition = None
            #sort out the node string...
            split_string = node_string.split()
            if split_string[type_loc] == 'INSTANCE':
                node.instance_ids.append(split_string[instance_id_loc])
            elif(split_string[type_loc] == 'NODE'):
                hostname = split_string[hostname_loc]
                partition_name = split_string[partition_loc]
                state = split_string[state_loc]
                # grab the list of instances if any found in the string
                #Try to match the part_name to the partition name it resides in
                for part in self.get_all_partitions():
                    if part.name == partition_name:
                            partition = part
                            break
                if not partition:
                    raise Exception('populate_nodes: Node:' + str(hostname) + ' Failed to find partition for name: '
                                    + str(partition_name))
                node = Eunode(self.tester,
                              hostname,
                              partition,
                              state = state)
                return_list.append(node)
                if node in part.ncs:
                    part.ncs[part.ncs.index(node)]=node
                else:
                    part.ncs.append(node)
        self.node_list = return_list
        return return_list


    def populate_nodes_pre_3_3(self,enabled_clc=None):
        """
        Sort output of 'list nodes cmd' on clc, create/update eunode objects.
        Returned list is used to update:'service_manager.node_list'

        :param enabled_clc: To avoid an update() or update() loop the current enabled clc can be provided. This can
                            also be used to test nc lookup on disabled CLC by providing this component obj instead.
        :return: list of eunode objects

        output for <= 3.2.2
        [type]  [node hostname] [cc_name] [instances....]
        NODE	192.168.51.72	CC_71	i-9A293E9B
        """
        type_loc = 0
        hostname_loc = 1
        cc_name_loc = 2
        instances_loc = 3
        return_list = []
        #to avoid update() loop allow enabled_clc to be provided as arg
        clc = enabled_clc or self.get_enabled_clc()
        nodes_strings = clc.machine.sys(self.eucaprefix + \
                                        "/usr/sbin/euca_conf --list-nodes 2>/dev/null | grep '^NODE'")

        for node_string in nodes_strings:
            #handle/skip any blank lines first...
            self.debug('Handling Node string:' + str(node_string))
            node_string = node_string.strip()
            if not node_string:
                continue
            instance_list = []
            partition = None
            #sort out the node string...
            split_string = node_string.split()
            cc_name = split_string[cc_name_loc]
            hostname = split_string[hostname_loc]
            # grab the list of instances if any found in the string
            if len(split_string) > instances_loc:
                instance_list = split_string[instances_loc:]
                #Try to match the part_name to the partition name it resides in
            for part in self.get_all_partitions():
                for cc in part.ccs:
                    if cc.name == cc_name:
                        partition = part
                        break
            if not partition:
                raise Exception('populate_nodes: Node:' + str(hostname) + ' Failed to find partition for component: '
                                + str(cc_name))
            node = Eunode(self.tester,
                          hostname,
                          partition,
                          instance_ids = instance_list,
                          state = 'ENABLED')
            return_list.append(node)
            if node in part.ncs:
                part.ncs[part.ncs.index(node)]=node
            else:
                part.ncs.append(node)
        self.node_list = return_list
        return return_list


    def update_node_list(self, enabled_clc=None):
        self.populate_nodes(enabled_clc=enabled_clc)

    def update_service_list(self):
        return self.get()

    @eutester.Eutester.printinfo
    def get_all_services_by_filter(self,
                                   type=None,
                                   partition=None,
                                   state=None,
                                   name=None,
                                   hostname=None,
                                   running=None,
                                   use_cached_list=True):
        """
        Returns a list of services of service that match the provided filter criteria.

        :param type: type of service to look for (cluster, eucalyptus, storage, walrus)
        :param partition: partition to filter returned service list with
        :param state: state to filter returned service list with
        :param name: name to filter returned service list with
        :param hostname: hostname/ip to filter returned service list with
        :param running: running boolean to filter returned service list with
        :param use_cached_list: use current list and state of self.all_services, else get_all_services()
        :return: list of matching cc euservice objects

        Examples:
                - Get all the services running on a specific machine "XYZ":
                    get_all_services_by_filter(hostname="XYZ")
                - Get all services in ENABLED state:
                    get_all_services_by_filter(state="ENABLED")
                - Get all Storage controllers in zone/partition "MYZONE":
                    get_all_services_by_filter(type=self.storage_type_string, partition="MYZONE")
        """
        euservice_list = []
        if use_cached_list:
            services = self.all_services or self.get_all_services()
        else:
            services = self.get_all_services()
        for service in services:
                if type and service.type != type:
                    continue
                if partition and service.partition != partition:
                    continue
                if state and service.state != state:
                    continue
                if name and service.name != name:
                    continue
                if hostname and service.hostname != hostname:
                    continue
                if running is not None and service.running != running:
                    continue
                euservice_list.append(service)
        return euservice_list


    def get_all_cluster_controllers(self,
                                    partition=None,
                                    state=None,
                                    name=None,
                                    hostname=None,
                                    running=None,
                                    use_cached_list=True):
        """
        Returns a list of services of cluster services that match the provided filter criteria.

        :param partition: partition to filter returned service list with
        :param state: state to filter returned service list with
        :param name: name to filter returned service list with
        :param hostname: hostname/ip to filter returned service list with
        :param running: running boolean to filter returned service list with
        :param service_list: list of euservices to filter from
        :param use_cached_list: use current list and state of self.all_services, else get_all_services()
        :return: list of matching cc euservice objects
        """
        return self.get_all_services_by_filter(type=self.cluster_type_string,
                                                 partition=partition,
                                                 state=state,
                                                 name=name,
                                                 hostname=hostname,
                                                 running=running,
                                                 use_cached_list=use_cached_list)

    def get_all_storage_controllers(self,
                                    partition=None,
                                    state=None,
                                    name=None,
                                    hostname=None,
                                    running=None,
                                    use_cached_list=True):
        """
        Returns a list of services of storage controller services that match the provided filter criteria.

        :param partition: partition to fileter returned service list with
        :param state: state to filter returned service list with
        :param name: name to filter returned service list with
        :param hostname: hostname/ip to filter returned service list with
        :param running: running boolean to filter returned service list with
        :param service_list: list of euservices to filter from
        :param use_cached_list: use current list and state of self.all_services, else get_all_services()
        :return: list of matching cc euservice objects
        """
        return self.get_all_services_by_filter(type=self.storage_type_string,
                                             partition=partition,
                                             state=state,
                                             name=name,
                                             hostname=hostname,
                                             running=running,
                                             use_cached_list=use_cached_list)

    def get_all_walrus(self,
                       partition=None,
                       state=None,
                       name=None,
                       hostname=None,
                       running=None,
                       use_cached_list=True):
        """
        Returns a list of services of walrus services that match the provided filter criteria.

        :param partition: partition to fileter returned service list with
        :param state: state to filter returned service list with
        :param name: name to filter returned service list with
        :param hostname: hostname/ip to filter returned service list with
        :param running: running boolean to filter returned service list with
        :param service_list: list of euservices to filter from
        :param use_cached_list: use current list and state of self.all_services, else get_all_services()
        :return: list of matching cc euservice objects
        """
        return self.get_all_services_by_filter(type=self.walrus_type_string,
                                             partition=partition,
                                             state=state,
                                             name=name,
                                             hostname=hostname,
                                             running=running,
                                             use_cached_list=use_cached_list)

    def get_all_osgs(self, partition=None,
                                  state=None,
                                  name=None,
                                  hostname=None,
                                  running=None,
                                  use_cached_list=True):
        """
        Returns a list of Object Storage Gateways that match the provided filter criteria.

        :param partition: partition to filter returned service list with
        :param state: state to filter returned service list with
        :param name: name to filter returned service list with
        :param hostname: hostname/ip to filter returned service list with
        :param running: running boolean to filter returned service list with
        :param service_list: list of euservices to filter from
        :param use_cached_list: use current list and state of self.all_services, else get_all_services()
        :return: list of matching cc euservice objects
        """
        return self.get_all_services_by_filter(type=self.osg_type_string,
                                             partition=partition,
                                             state=state,
                                             name=name,
                                             hostname=hostname,
                                             running=running,
                                             use_cached_list=use_cached_list)

    def get_all_cloud_controllers(self,
                                 partition=None,
                                 state=None,
                                 name=None,
                                 hostname=None,
                                 running=None,
                                 use_cached_list=True):
        """
        Returns a list of services of CLC services that match the provided filter criteria.

        :param partition: partition to fileter returned service list with
        :param state: state to filter returned service list with
        :param name: name to filter returned service list with
        :param hostname: hostname/ip to filter returned service list with
        :param running: running boolean to filter returned service list with
        :param service_list: list of euservices to filter from
        :param use_cached_list: use current list and state of self.all_services, else get_all_services()
        :return: list of matching cc euservice objects
        """
        return self.get_all_services_by_filter(type=self.clc_type_string,
                                             partition=partition,
                                             state=state,
                                             name=name,
                                             hostname=hostname,
                                             running=running,
                                             use_cached_list=use_cached_list)

    def get_all_node_controllers(self,
                                 hostname=None,
                                 partition=None,
                                 part_name=None,
                                 instance_id=None,
                                 has_instances=None,
                                 service_state=None,
                                 use_cached_list=True):
        """
        Returns a list of services of node controllers that match the provided filter criteria.

        :param part_name: name of partition to filter list with
        :param instance_id: filter list for specific instance id
        :param has_instances: filter list by nodes which have instance ids associated with them
        :param partition: partition obj to filter returned service list with
        :param name: name to filter returned service list with
        :param hostname: hostname/ip to filter returned service list with
        :param running: running boolean to filter returned service list with
        :param use_cached_list: use current list and state of self.all_services, else get_all_services()
        :return: list of matching cc euservice objects
        """
        return_list = []
        if use_cached_list:
            nodes = self.node_list or self.populate_nodes()
        else:
            nodes = self.populate_nodes()
        for node in nodes:
            if partition and node.partition != partition:
                continue
            if part_name and node.part_name != part_name:
                continue
            if hostname and node.hostname != hostname:
                continue
            if instance_id and not instance_id in node.instance_ids:
                continue
            if service_state and service_state != node.service_state:
                continue
            if has_instances and not node.instance_ids:
                continue
            return_list.append(node)
        return return_list


    def get_all_partitions(self):
        return_list = []
        for key in self.partitions:
            part = self.partitions[key]
            return_list.append(part)
        return return_list

    def get_all_services(self):
        all_services = []
        self.update()
        if len(self.clcs) > 0:
            all_services = all_services + self.clcs
        if len(self.walruses) > 0:
            all_services = all_services + self.walruses
            
        if len(self.osgs) > 0:
            all_services = all_services + self.osgs
            
        for partition in self.partitions.keys():

            ccs = self.partitions[partition].ccs
            if len(ccs) > 0:
                all_services = all_services + ccs
                
            scs = self.partitions[partition].scs
            if len(scs) > 0:
                all_services = all_services + scs
            
            vbs = self.partitions[partition].vbs
            if len(vbs) > 0:
                all_services = all_services + vbs
        return all_services
            
    def start_all(self):
        all_services = self.get_all_services() 
        for service in all_services:
            try:
                service.start()
            except Exception, e:
                self.tester.debug("Caught an exception when trying to turn up a service. Probably was already running")
                
    def get_conclusive_enabled_clc(self):
        self.reset()
        try:
            first_clc = self.get("eucalyptus")
        except:
            first_clc = None
            
        self.tester.swap_clc()
        
        try:
            second_clc = self.get("eucalyptus")
        except:
            second_clc = None
        
        ### Only one responded properly
        if second_clc is None:
            return first_clc 
        if first_clc is None:
            return second_clc
        
        ### Inconsistency among 2 CLCs
        if second_clc.host is first_clc.host:
                return first_clc
        else:
            raise Exception("Could not find a CLC to connect to")
        
    def sync_credentials(self):
        self.reset()



    def update(self, name=None):
        ### Get all services
        if self.last_updated:
            if (time.time() - self.last_updated) < 1:
                return
        self.reset()
        services = self.get(name)
        self.all_services = services
        for current_euservice in services:
            ### If this is system wide component add it to the base level array
            if re.search("eucalyptus", current_euservice.type) :
                self.clcs.append(current_euservice)
                continue
            elif re.search("walrus", current_euservice.type):
                self.walruses.append(current_euservice)
                continue
            elif re.search("osg", current_euservice.type):
                self.osgs.append(current_euservice)
                continue
            elif re.search("dns", current_euservice.type):
                self.dns = current_euservice
                continue
            elif re.search("arbitrator", current_euservice.type):
                self.arbitrators.append(current_euservice)
                continue
            ### If this is a partition specific component nest the service in its partition array
            if re.search("eucalyptus", current_euservice.partition) or re.search("bootstrap", current_euservice.partition):
                self.internal_components.append(current_euservice)
                continue
            else:
                append = False
                if current_euservice.partition in self.partitions:
                    my_partition = self.partitions[current_euservice.partition]
                else:
                    ### First time accessing this partition
                    my_partition = Partition(current_euservice.partition, self)
                    append = True
                if re.search("cluster", current_euservice.type):
                    my_partition.ccs.append(current_euservice)
                if re.search("storage", current_euservice.type):
                    my_partition.scs.append(current_euservice)
                if re.search("vmwarebroker", current_euservice.type):
                    my_partition.vbs.append(current_euservice)          
                if append:
                    self.partitions[current_euservice.partition] = my_partition
        enabled_clc = self.get_all_cloud_controllers(state='ENABLED')
        if enabled_clc:
            enabled_clc = enabled_clc[0]
            self.update_node_list(enabled_clc=enabled_clc)
        self.last_updated=time.time()
    
    def isReachable(self, address):
        return self.tester.ping(address)
        
    def modify_service(self, euservice, state):
        if not self.isReachable(self.tester.clc.hostname):
            self.tester.clc = self.tester.get_component_machines("clc")[1]
        modify_response = self.tester.clc.sys(self.eucaprefix + "/usr/sbin/euca-modify-service -s " + str(state)  + " " + euservice.name)
        if re.search("true",modify_response[0]):
            return True
        else:
            raise AssertionError("Response to modify service was not true: " + str(modify_response))
    
    def modify_process(self, euservice, command): 
        service_name = "eucalyptus-cloud"
        if re.search("cluster", euservice.type):
            service_name = "eucalyptus-cc"
        if euservice.type == self.node_type_string:
            service_name = "eucalyptus-nc"
        if not euservice.machine.found(self.tester.eucapath + "/etc/init.d/" + service_name + " " + command, "done"):
            self.tester.fail("Was unable to " +str(command) + " service: " + euservice.name + " on host "
                             + euservice.machine.hostname)
            raise Exception("Did not properly modify service")
    
    def stop(self, euservice):
        if re.search("cluster", euservice.type):
            self.modify_process(euservice, "cleanstop")
        else:
            self.modify_process(euservice, "stop")
        euservice.running = False
        
    def start(self, euservice):
        if euservice.type == 'cluster':
            if euservice.machine.get_eucalyptus_cc_is_running_status():
                euservice.running = True
                return
        else:
            if euservice.machine.get_eucalyptus_cloud_is_running_status():
                euservice.running = True
                return
        self.modify_process(euservice, "start")

    
    def enable(self,euservice):
        self.modify_service(euservice, "ENABLED")
    
    def disable(self,euservice):
        self.modify_service(euservice, "DISABLED")
        
    def wait_for_service(self, euservice, state = "ENABLED", states=None,attempt_both = True, timeout=600):
        interval = 20
        poll_count = timeout / interval
        while (poll_count > 0):
            matching_services = []
            try:
                matching_services = self.get(euservice.type, euservice.partition, attempt_both)
                for service in matching_services:
                    if states:
                        for state in states:
                            if re.search(state, service.state):
                                return service
                    else:
                        if re.search(state, service.state):
                            return service
            except Exception, e:
                self.tester.debug("Caught " + str(e) + " when trying to get services. Retrying in " + str(interval) + "s")
            poll_count -= 1
            self.tester.sleep(interval)
                
        if poll_count is 0:
            self.tester.fail("Service: " + euservice.name + " did not enter "  + state + " state")
            raise Exception("Service: " + euservice.name + " did not enter "  + state + " state")
        
    def all_services_operational(self):
        self.debug('all_services_operational starting...')
        all_services_to_check = self.get_all_services()
        self.print_services_list(all_services_to_check)
        while all_services_to_check:
            ha_counterpart = None
            service = all_services_to_check.pop()
            self.debug('Checking for operational state of services type:' + str(service.type))
            for serv in all_services_to_check:
                if not serv.isActiveActive() and serv.type == service.type and serv.partition == service.partition:
                    ha_counterpart = serv
                    break
            if ha_counterpart:
                all_services_to_check.remove(ha_counterpart)
                self.wait_for_service(service,"ENABLED")
                self.wait_for_service(service,"DISABLED")
            else:
                self.wait_for_service(service,"ENABLED")

    def wait_for_all_services_operational(self, timeout=600):
        '''
        Attempts to wait for a core set of eutester monitored services on the cloud and/or specified in the
        config file to transition to ENABLED. In the HA case will look for both an ENABLED and DISABLED service.
        '''
        start = time.time()
        elapsed = 0
        while elapsed < timeout:
            self.debug("wait_for_all_services_operational, elapsed: " + str(elapsed) + "/" + str(timeout))
            elapsed = int(time.time() - start)
            try:
                self.print_services_list()
                self.all_services_operational()
                self.debug('All services were detected as operational')
                return
            except Exception, e:
                tb = self.tester.get_traceback()
                elapsed = int(time.time() - start )
                error = tb + "\n Error waiting for all services operational, elapsed: " + \
                        str(elapsed) + "/" + str(timeout) + ", error:" + str(e)
                if elapsed < timeout:
                    self.debug(error)
                else:
                    raise Exception(error)
            time.sleep(15)



    def get_enabled_clc(self):
        clc = self.get_enabled(self.clcs)
        if clc is None or len(clc) == 0:
            raise Exception("Neither CLC is enabled")
        else:
            return clc.pop()
    
    def get_disabled_clc(self):
        clc = self.get_disabled(self.clcs)
        if clc is None or len(clc) == 0:
            raise Exception("Neither CLC is disabled")
        else:
            return clc.pop()
    
    def get_enabled_walrus(self):
        walrus = self.get_enabled(self.walruses)
        if walrus is None or len(walrus) == 0:
            raise Exception("Neither Walrus is enabled")
        else:
            return walrus.pop()

    def get_enabled_osg(self):
        osg = self.get_enabled(self.osgs)
        if osg is None:
            raise Exception("No Object Storage Gateways are enabled")
        else:
            return osg
    
    def get_disabled_walrus(self):
        walrus = self.get_disabled(self.walruses)
        if walrus is None or len(walrus) == 0:
            raise Exception("Neither Walrus is disabled")
        else:
            return walrus.pop()

    def get_enabled_osgs(self):
        '''Returns list of enabled osgs'''
        enabled_osgs = self.get_enabled(self.osgs)
        if enabled_osgs is None:
            raise Exception("No OSG is enabled")
        else:
            return enabled_osgs

    def get_enabled_dns(self):
        dns = self.get_enabled([self.dns])
        if dns is None or len(dns) == 0:
            raise Exception("DNS service is not available")
        else:
            return dns.pop()
    
    #modified by zhill to include *all* enabled services of this type, uses a list return
    def get_enabled(self, list_of_services):
        '''Returns a list of the services of the requested type that are in ENABLED state'''
        self.update()
        enabled_services = []
        for service in list_of_services:
            if service.isEnabled():
                enabled_services.append(service)
                
        return enabled_services;
    
    def get_disabled(self, list_of_services):
        '''Returns a list of the services of the requested type that are in DISABLED state'''
        self.update()
        disabled_services = []
        for service in list_of_services:
            if service.isDisabled():
                disabled_services.append(service)
            
        return disabled_services;







