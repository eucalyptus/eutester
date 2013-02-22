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

class Eunode:
    def __init__(self,
                 hostname,
                 partition,
                 name=None,
                 instance_ids=None,
                 tester = None,
                 machine = None,
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
        self.hostname = hostname
        self.partition = partition
        self.part_name = partition.name
        self.name = name or self.hostname
        self.instance_ids = instance_ids or []
        self.tester = tester
        self.machine = machine
        self.service_state = None

        if tester and hostname and not machine:
            try:
                self.machine = self.tester.get_machine_by_ip(hostname)
                self.get_service_state()
            except Exception, e:
                print "Failed to get machine for this node:" + str(hostname) + ", err:" + str(e)
        #if self.machine:
            #self.hypervisor =


    def sys(self, cmd, code=None):
        """
        Command to be executed via ssh on remote eunode machine
        :param cmd: string - command to be executed
        :param code: int - optional exit code used to determine pass fail of remote command.
        :return: list of lines from remote cmd's output
        """
        return self.machine.sys(cmd,code=code)

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
        if self.machine:
            if self.sys('service eucalyptus-nc status | grep running', code=0):
                self.service_state = 'running'
            else:
                self.service_state = 'not_running'
        else:
            print "No machine object for this eunode:" + str(self.hostname)
        return self.service_state


    def get_virsh_list(self):
        """
        Return a dict of virsh list domains.
        dict should have dict['id'], dict['name'], dict['state']

        """
        return_list = {}
        if self.machine:
            keys = []
            output = self.machine.sys('virsh list', code=0)
            if len(output) > 1:
                keys = str(output[0]).strip().lower().split()
                for line in output[2:]:
                    domain_line = line.strip().split()
                    for key in keys:
                        return_list[key] = domain_line[keys.index(key)]
        return return_list

    #def get_iscsi_connections(self,):
    #def get_exported_volumes(self,)





class Euservice:
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
    
    def disable(self):
        self.tester.service_manager.disable(self)
        
    def enable(self):
        self.tester.service_manager.enable(self)
    
    def stop(self):
        self.tester.service_manager.stop(self)
    
    def start(self):
        self.tester.service_manager.start(self)
    
        
class Partition:
    name = ""
    ccs = []
    scs = []
    vbs = []
    ncs = []
    volumes = []
    instances = []
    
    def __init__(self, name, service_manager ):
        self.name = name
        self.service_manager = service_manager
        
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
    storage_type_string = 'storage'
    clc_type_string = 'eucalyptus'

        
    def __init__(self, tester ):
        '''
        SERVICE    storage            PARTI00            SC_61              ENABLED       16      http://192.168.51.32:8773/services/Storage    arn:euca:eucalyptus:PARTI00:storage:SC_61/
        update this service based up on the information parsed out of the "describestring"
        '''
        ### Make sure i have the right connection to make first contact with euca-describe-services
        self.walruses= []
        self.clcs = []
        self.arbitrators = []
        self.partitions = {}
        self.internal_components = []
        self.dns = None
        self.all_services = []
        self.node_list = []
        self.tester = tester
        self.eucaprefix = ". " + self.tester.credpath + "/eucarc && " + self.tester.eucapath
        if self.tester.clc is None:
            raise AttributeError("Tester object does not have CLC machine to use for SSH")
        self.update()

    
    def get(self, type=None, partition=None, attempt_both=True):
        if type is not None:
            type = " -T " + str(type) 
        else:
            type = ""
        describe_services = []
        #### This is a hack around the fact that the -P filter is not working need to fix this once that functionality is fixed
        if partition is None:
            partition = ""
        try:
            out = self.tester.clc.sys(self.eucaprefix + "/usr/sbin/euca-describe-services " + str(type), code=0,timeout=15)
            for line in out:
                if re.search("SERVICE.+"+str(partition), line):
                    describe_services.append(line)
            if not describe_services:
                raise IndexError("Did not receive proper response from describe services when looking for " + str(type))
        except Exception, e:
            if len(self.tester.get_component_machines("clc")) is 1:
                raise Exception("Unable to get service information from the only clc: " + self.tester.clc.hostname+", err:" +str(e))
            if attempt_both:
                self.tester.swap_clc()
                describe_services = self.tester.clc.sys(self.eucaprefix + "/usr/sbin/euca-describe-services " + str(type)  + " | grep SERVICE | grep "  + str(partition)  , timeout=15)
                if len(describe_services) < 1:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
                    raise IndexError("Did not receive proper response from describe services when looking for " + str(type))
            raise e
        
        #self.populate_nodes()
        services = []
        for service_line in describe_services:
            services.append(Euservice(service_line, self.tester))
        return services





    def reset(self):
        self.walruses= []
        self.clcs = []
        self.arbitrators = []
        self.internal_components = []
        for k, v in self.partitions.iteritems():
            self.partitions[k].ccs = []
            self.partitions[k].scs = []
            self.partitions[k].vbs = []


    def populate_nodes(self, enabled_clc=None):
        """
        Sort list nodes ouptut and create/update eunode objects
        updates service_manager.node_list
        :param enabled_clc: To avoid an update() or update() loop the current enabled clc can be provided.
        :returns: list of eunode objects
        """
        #name = 0
        hostname_loc = 1
        cc_name_loc = 2
        instances_loc = 3
        return_list = []
        #to avoid update() loop allow enabled_clc to be provided as arg
        clc = enabled_clc or self.get_enabled_clc()
        nodes_strings = clc.machine.sys("euca_conf --list-nodes")

        for node_string in nodes_strings:
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
            node = Eunode(hostname,
                          partition,
                          instance_ids = instance_list,
                          tester = self.tester)
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

    def get_all_services_of_type(self,
                                 type,
                                 partition=None,
                                 state=None,
                                 name=None,
                                 hostname=None,
                                 running=None,
                                 use_cached_list=True):
        """
        Returns a list of services of service type 'type' that match the provided filter criteria.

        :param type: type of service to look for (cluster, eucalyptus, storage, walrus)
        :param partition: partition to fileter returned service list with
        :param state: state to filter returned service list with
        :param name: name to filter returned service list with
        :param hostname: hostname/ip to filter returned service list with
        :param running: running boolean to filter returned service list with
        :param use_cached_list: use current list and state of self.all_services, else get_all_services()
        :return: list of matching cc euservice objects
        """
        euservice_list = []
        if use_cached_list:
            services = self.all_services or self.get_all_services()
        else:
            services = self.get_all_services()
        for service in services:
            if service.type == type:
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

        :param partition: partition to fileter returned service list with
        :param state: state to filter returned service list with
        :param name: name to filter returned service list with
        :param hostname: hostname/ip to filter returned service list with
        :param running: running boolean to filter returned service list with
        :param service_list: list of euservices to filter from
        :param use_cached_list: use current list and state of self.all_services, else get_all_services()
        :return: list of matching cc euservice objects
        """
        return self.get_all_services_of_type(self.cluster_type_string,
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
        return self.get_all_services_of_type(self.storage_type_string,
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
        return self.get_all_services_of_type(self.walrus_type_string,
                                             partition=partition,
                                             state=state,
                                             name=name,
                                             hostname=hostname,
                                             running=running,
                                             use_cached_list=use_cached_list)

    def get_all_cloud_controlers(self,
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
        return self.get_all_services_of_type(self.clc_type_string,
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
            if instance_id and not instance_id in node.instances:
                continue
            if service_state and service_state != node.service_state:
                continue
            if has_instances and not node.instances:
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
        enabled_clc = self.get_all_cloud_controlers(state='ENABLED')
        if enabled_clc:
            enabled_clc = enabled_clc[0]
            self.update_node_list(enabled_clc=enabled_clc)
    
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
        if not euservice.machine.found(self.tester.eucapath + "/etc/init.d/" + service_name + " " + command, "done"):
            self.tester.fail("Was unable to stop service: " + euservice.name + " on host " + euservice.machine.hostname)
            raise Exception("Did not properly modify service")
    
    def stop(self, euservice):
        if re.search("cluster", euservice.type):
            self.modify_process(euservice, "cleanstop")
        else:
            self.modify_process(euservice, "stop")
        euservice.running = False
        
    def start(self, euservice):
        self.modify_process(euservice, "start")
        euservice.running = True
    
    def enable(self,euservice):
        self.modify_service(euservice, "ENABLED")
    
    def disable(self,euservice):
        self.modify_service(euservice, "DISABLED")
        
    def wait_for_service(self, euservice, state = "ENABLED", attempt_both = True, timeout=600):
        interval = 20
        poll_count = timeout / interval
        while (poll_count > 0):
            matching_services = []
            try:
                matching_services = self.get(euservice.type, euservice.partition, attempt_both)
                for service in matching_services:
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
        all_services = self.get_all_services()
        for service in all_services:
            self.wait_for_service(service,"ENABLED")
            self.wait_for_service(service,"DISABLED")
    
    def get_enabled_clc(self):
        clc = self.get_enabled(self.clcs)
        if clc is None:
            raise Exception("Neither CLC is enabled")
        else:
            return clc
    
    def get_disabled_clc(self):
        clc = self.get_disabled(self.clcs)
        if clc is None:
            raise Exception("Neither CLC is disabled")
        else:
            return clc
    
    def get_enabled_walrus(self):
        walrus = self.get_enabled(self.walruses)
        if walrus is None:
            raise Exception("Neither Walrus is enabled")
        else:
            return walrus
    
    def get_disabled_walrus(self):
        walrus = self.get_enabled(self.walruses)
        if walrus is None:
            raise Exception("Neither Walrus is disabled")
        else:
            return walrus
    
    def get_enabled(self, list_of_services):
        self.update()
        for service in list_of_services:
            if service.isEnabled():
                return service
        return None
    
    def get_disabled(self, list_of_services):
        self.update()
        for service in list_of_services:
            if service.isDisabled():
                return service
        return None


