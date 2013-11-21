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
Created on Mar 7, 2012
@author: clarkmatthew
Place holder for volume test specific convenience methods+objects to extend boto's volume class

'''
from boto.ec2.volume import Volume
from eutester.taggedresource import TaggedResource
import eucaops
import time



class EuVolume(Volume, TaggedResource):
    tag_md5_key = 'md5'
    tag_md5len_key = 'md5len'
    tag_instance_id_key = 'instance_id'
    tag_guestdev_key = 'guestdev'

    '''
    Note: Different hypervisors will honor the requested cloud dev differently, so the requested device can not 
    be relied up as the device it attached to on the guest 'guestdev'
    '''

        
    @classmethod
    def make_euvol_from_vol(cls,volume, tester=None, cmdstart=None):
        newvol = EuVolume(volume.connection)
        newvol.__dict__ = volume.__dict__
        newvol.tester = tester
        newvol.guestdev = "" #the guest device name in use by this attached volume
        newvol.clouddev = "" #the device name given to the cloud as a request to be used.
        newvol.md5 = None
        newvol.md5len = 1024
        newvol.eutest_failmsg = None
        newvol.eutest_laststatus = newvol.status
        newvol.eutest_ageatstatus = 0 
        newvol.eutest_cmdstart = cmdstart or eucaops.EC2ops.get_volume_time_created(volume)
        newvol.eutest_createorder = None
        newvol.eutest_cmdtime = None
        newvol.eutest_attached_instance_id = None
        if newvol.tags.has_key(newvol.tag_md5_key):
            newvol.md5 = newvol.tags[newvol.tag_md5_key]
        if newvol.tags.has_key(newvol.tag_md5len_key):
            newvol.md5len = newvol.tags[newvol.tag_md5len_key]
        newvol.set_attached_status()

        return newvol
    
    def update(self):
        super(EuVolume, self).update()
        if (self.tags.has_key(self.tag_md5_key) and (self.md5 != self.tags[self.tag_md5_key])) or \
            (self.tags.has_key(self.tag_md5len_key) and (self.md5len != self.tags[self.tag_md5len_key])):
            self.update_volume_attach_info_tags()
        self.set_last_status()
    
    def set_last_status(self,status=None):
        self.eutest_laststatus = status or self.status
        self.eutest_laststatustime = time.time()
        self.set_attached_status()
        self.eutest_ageatstatus = "{0:.2f}".format(time.time() - self.eutest_cmdstart)

    def set_attached_status(self):
        if self.attach_data:
            self.eutest_attached_status = self.attach_data.status
            self.eutest_attached_instance_id = self.attach_data.instance_id
            if self.tags.has_key(self.tag_instance_id_key) and self.tags[self.tag_instance_id_key] != self.eutest_attached_instance_id:
                self.remove_tag(self.tag_instance_id_key)
                self.remove_tag(self.tag_guestdev_key)
            else:
                if not self.guestdev and self.tags.has_key(self.tag_guestdev_key):
                    self.guestdev = self.tags[self.tag_guestdev_key]
        else:
            self.eutest_attached_status = None
            self.eutest_attached_instance_id = None

    def printself(self,title=True, footer=True, printmethod=None):
        buf = "\n"
        if title:
            buf += str("-----------------------------------------------------------------------------------------------------------------------------------------------\n")
            buf += str('VOL_ID').ljust(15)+'|'+str('ORDER').center(5)+'|'+str('LASTSTATUS').center(10)+'|'+str('TESTSTATUS').center(10)+'|'+str('AGE@STATUS').center(15)+'|'+str('SIZE').center(4)+'|'+str('FROM_SNAP').center(15)+'|'+str('MD5_SUM').center(33)+'|'+str('MD5LEN').center(6)+'|'+str('ZONE').center(15)+'|'+str('INSTANCE')+'\n'
            buf += str("-----------------------------------------------------------------------------------------------------------------------------------------------\n")
        buf += str(self.id).ljust(15)+'|'+str(self.eutest_createorder).center(5)+'|'+str(self.eutest_laststatus).center(10)+'|'+str(self.status).center(10)+'|'+str(self.eutest_ageatstatus).center(15)+'|'+str(self.size).center(4)+'|'+str(self.snapshot_id).center(15)+'|'+str(self.md5).center(33)+'|'+str(self.md5len).center(6)+'|'+str(self.zone).center(15)+'|'+str(self.attach_data.instance_id).rstrip()+"\n"
        if footer:
            buf += str("-----------------------------------------------------------------------------------------------------------------------------------------------")
        if printmethod:
            printmethod(buf)
        return buf

    def update_volume_attach_info_tags(self, md5=None, md5len=None, instance_id=None, guestdev=None):
        md5 = md5 or self.md5
        md5len = md5len or self.md5len
        self.add_tag(self.tag_md5_key, md5)
        self.add_tag(self.tag_md5len_key, md5len)
        if self.status == 'in-use' and hasattr(self,'attach_data') and self.attach_data:
            instance_id = instance_id or self.eutest_attached_instance_id
            guestdev = guestdev or self.guestdev
            self.add_tag(self.tag_instance_id_key, instance_id)
            self.add_tag(self.tag_guestdev_key, guestdev)
        else:
            self.set_volume_detached_tags()


    def set_volume_detached_tags(self):
        self.remove_tag(self.tag_instance_id_key)
        self.remove_tag(self.tag_guestdev_key)
    
        
        
        
        
        
        
