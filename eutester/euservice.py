'''
Created on Mar 15, 2012

@author: clarkmatthew
'''

import re

class ServiceState:
    ENABLED=1
    DISABLED=2
    STOPPED=3
    NOT_READY=4
    BROKEN=5
    
class DescribeString:
    #SERVICE    storage  PARTI00  SC_61  ENABLED  16 http://192.168.51.32:8773/services/Storage    arn:euca:eucalyptus:PARTI00:storage:SC_61/
    name=1
    location=2
    component=3
    state=4
    num=5
    uri=6
    path=7


class ServiceName:
    clc="eucalyptus"
    sc="storage"
    cc="cluster"
    walrus="walrus"
    euare="euare"
    properties="properties"
    jetty="jetty"
    bootstrap="bootstrap"
    configuration="configuration"
    component="component"
    notifications="notifications"
    dns="dns"
    
    
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
        if tester is not None:
            self.tester = tester
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
    
    def __init__(self, name, service_manager ):
        self.name = name
        self.service_manager = service_manager
        
    def get_enabled(self, list):
        self.service_manager.update()
        for service in list:
            if service.isEnabled():
                return service
        return None
    
    def get_disabled(self, list):
        self.service_manager.update()
        for service in list:
            if not service.isEnabled():
                return service
        return None
    
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
        #### This is a hack around the fact that the -P filter is not working need to fix this once that functionality is fixed
        if partition is not None:
            partition = " | grep " + str(partition) 
        else:
            partition = ""
        try:
            describe_services = self.tester.clc.sys(self.eucaprefix + "/usr/sbin/euca-describe-services --system-internal " + str(type)  +  "| grep SERVICE" + str(partition), timeout=15)
            if len(describe_services) < 1:
                raise IndexError("Did not receive proper response from describe services when looking for " + str(type))
        except Exception, e:
            if attempt_both:
                self.tester.swap_clc()
                describe_services = self.tester.clc.sys(self.eucaprefix + "/usr/sbin/euca-describe-services --system-internal " + str(type)  + " | grep SERVICE "  + str(partition)  , timeout=15)
            if len(describe_services) < 1:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
                    raise IndexError("Did not receive proper response from describe services when looking for " + str(type))
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
    
    def get_all_services(self):
        all_services = []
        self.update()
        if len(self.clcs) > 0:
            all_services.append(self.clcs)
        if len(self.walruses) > 0:
            all_services.append(self.walruses)
        for partition in self.partitions.keys():

            ccs = self.partitions[partition].ccs
            if len(ccs) > 0:
                all_services.append(ccs)
                
            scs = self.partitions[partition].scs
            if len(scs) > 0:
                all_services.append(scs)
            
            vbs = self.partitions[partition].vbs
            if len(vbs) > 0:
                all_services.append(vbs)
                
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
        if not euservice.machine.found("/etc/init.d/" + service_name + " " + command, "done"):
            self.tester.fail("Was unable to stop service: " + euservice.name + " on host " + euservice.machine.hostname)
            raise Exception("Did not properly modify service")
    
    def stop(self, euservice):
        self.modify_process(euservice, "stop")
        euservice.running = False
        
    def start(self, euservice):
        self.modify_process(euservice, "start")
        euservice.running = True
    
    def enable(self,euservice):
        self.modify_service(euservice, "ENABLED")
    
    def disable(self,euservice):
        self.modify_service(euservice, "DISABLED")
        
    def wait_for_service(self, euservice, state = "ENABLED", attempt_both = True):
        poll_count = 10
        interval = 60
        
        while (poll_count > 0):
            matching_services = []
            try:
                matching_services = self.get(euservice.type, euservice.partition, attempt_both)
            except Exception, e:
                self.tester.debug("Caught an exception when trying to get services. Retrying in " + str(interval) + "s")

            for service in matching_services:
                if re.search(state, service.state):
                    return service 
                 
            poll_count -= 1
            self.tester.sleep(interval)
                
        if poll_count is 0:
            self.tester.fail("Service: " + euservice.name + " did not enter "  + state + " state")
            raise Exception("Service: " + euservice.name + " did not enter "  + state + " state")
        
    
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
    
    

    
    