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
# Author: matt.clark@eucalyptus.com
'''
Created on Mar 21, 2013
@author: clarkmatthew
Place holder for availability zone test specific convenience methods+objects to extend boto's zone class

'''
import eutester
from boto.ec2.zone import Zone
import re

class Vm_Type():
    def __init__(self, name,free,max, cpu, ram, disk):
        self.name = name
        self.free = free
        self.max = max
        self.cpu = cpu
        self.ram = ram
        self.disk = disk

class EuZone(Zone):
    tester = None
    vm_types = []

    @classmethod
    def make_euzone_from_zone(cls, zone, tester):
        newzone = EuZone(zone.connection)
        newzone.__dict__ = zone.__dict__
        newzone.tester = tester
        newzone.vm_types = newzone.get_all_vm_type_info()
        return newzone

    def debug(self,msg):
        self.tester.debug(msg)

    def update(self):
        super(EuZone, self).update()
        self.vm_types = self.get_all_vm_type_info()

    @eutester.Eutester.printinfo
    def get_all_vm_type_info(self):
        vm_types = []
        get_zone = [str(self.name)]
        get_zone.append('verbose')
        found = False
        try:
            myzone = self.tester.ec2.get_all_zones(zones=get_zone)
        except Exception, e:
            tb = self.tester.get_traceback()
            raise Exception(str(tb) + '\n Could not get zone:' + str(self.name) + "\n" + str(e))
        for zone in myzone:
            if zone.name == self.name:
                found = True
            if found:
                name_split = zone.name.split()
                if '|-' in name_split and len(name_split) == 2:
                    type_name = str(name_split[1])
                    state_split = zone.state.split()
                    if '/' in state_split:
                        state_split.remove('/')
                    free = int(state_split[0])
                    max  = int(state_split[1])
                    cpu = int(state_split[2])
                    ram = int(state_split[3])
                    disk = int(state_split[4])
                    it = Vm_Type(type_name,free,max,cpu,ram,disk)
                    vm_types.append(it)
                    #Remove the setattr part after dev/debug?
                    self.__setattr__('vmtype_' + str(type_name.replace('.','_')), it)
                else:
                    if not re.search('vm types', zone.name) and  zone.name != self.name:
                        break
        return vm_types

    @eutester.Eutester.printinfo
    def get_vm_types(self, name=None, free=None, max=None, cpu=None, ram=None, disk=None, refresh_types=False):
        ret_list = []
        if refresh_types or not self.vm_types:
            types_list = self.update_all_vm_type_info()
        else:
            types_list = self.vm_types

        for type in types_list:
            if name and name != type.name:
                continue
            if cpu and cpu > type.cpu:
                continue
            if ram and ram > type.ram:
                continue
            if disk and disk > type.disk:
                continue
            if free and  free > type.free:
                continue
            if max and max > type.max:
                continue
            ret_list.append(type)
        return ret_list


