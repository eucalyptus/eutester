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
Created on Oct 30, 2012
@author: clarkmatthew
Place holder for snapshot test specific convenience methods+objects to extend boto's snapshot class

'''
from boto.ec2.snapshot import Snapshot
from eutester.taggedresource import TaggedResource
import eucaops
import time



class EuSnapshot(Snapshot, TaggedResource):
    eutest_volume_md5 = None
    eutest_volume_md5len = None
    eutest_volume_zone = None
    eutest_failmsg = None
    eutest_laststatus = None
    eutest_ageatstatus = None
    eutest_cmdstart = None
    eutest_createorder = None
    eutest_cmdtime = None
    eutest_polls = None
    eutest_poll_count = None
    eutest_last_progress = None
    eutest_timeintest = None
    
        
    @classmethod
    def make_eusnap_from_snap(cls, snapshot, tester=None, cmdstart=None):
        newsnap = EuSnapshot(snapshot.connection)
        newsnap.__dict__ = snapshot.__dict__
        newsnap.eutest_volume_md5 = None
        newsnap.tester = tester
        newsnap.eutest_volume_md5len = None
        newsnap.eutest_volume_zone = None
        newsnap.eutest_volumes = []
        newsnap.eutest_failmsg = None
        newsnap.eutest_laststatus = newsnap.status
        newsnap.eutest_ageatstatus = 0 
        newsnap.eutest_cmdstart = cmdstart or eucaops.EC2ops.get_snapshot_time_started(snapshot)
        newsnap.eutest_createorder = None
        newsnap.eutest_cmdtime = None
        newsnap.eutest_polls = 0
        newsnap.eutest_poll_count = 0
        newsnap.eutest_last_progress = int(newsnap.progress.replace('%','')  or 0)
        newsnap.eutest_timeintest = 0
        return newsnap
    
    def update(self):
        super(EuSnapshot, self).update()
        self.set_last_status()
    
    def set_last_status(self,status=None):
        self.eutest_laststatus = self.status
        self.eutest_laststatustime = time.time()
        self.eutest_ageatstatus = "{0:.2f}".format(time.time() - self.eutest_cmdstart)
        
    def printself(self,title=True, printmethod=None):
        buf = "\n"
        if title:
             buf = "\n-------------------------------------------------------------------------------------------------------------------------------------\n"
             buf += str('SNAP_ID').ljust(15)+'|'+str('ORDER').center(5)+'|'+str('CMDTIME').center(8)+'|'+str('ELAPSED').center(8)+'|'+str('%').center(4)+'|'+str('STATUS').center(12)+'|'+str('SRC_VOL').center(15)+'|'+str('SRC_VOL_MD5').center(33)+'|'+str('VOLZONE').center(15)+'|'+str('INFO-MSG')+"\n"
             buf += '-----------------------------------------------------------------------------------------------------------------------\n'     
        buf += str(self.id).ljust(15)+'|'+str(self.eutest_createorder).center(5)+'|'+str(self.eutest_cmdtime).center(8)+'|'+str(self.eutest_timeintest).center(8)+'|'+str(self.eutest_last_progress).center(4)+'|'+str(self.eutest_laststatus).center(12)+'|'+str(self.volume_id).center(15)+'|'+str(self.eutest_volume_md5).center(33)+'|'+str(self.eutest_volume_zone).center(15)+'|'+str(self.eutest_failmsg)+"\n"
        buf += '-------------------------------------------------------------------------------------------------------------------------------------\n'
        if printmethod:
            printmethod(buf)
        return buf
    
        
        
    
        
        
        
