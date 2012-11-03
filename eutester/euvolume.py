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
import time



class EuVolume(Volume):   
    md5 = None
    md5len = 32
    eutest_failmsg = None
    eutest_laststatus = None
    eutest_laststatustime = None
    eutest_cmdstart = None
    eutest_createorder = None
    eutest_cmdtime = None
    eutest_ageatstatus = None
    '''
    Note: Different hypervisors will honor the requested cloud dev differently, so the requested device can not 
    be relied up as the device it attached to on the guest 'guestdev'
    '''
    guestdev = "" #the guest device name in use by this attached volume
    clouddev = "" #the device name given to the cloud as a request to be used. 
        
    @classmethod
    def make_euvol_from_vol(cls,volume,cmdstart=None):
        newvol = EuVolume(volume.connection)
        newvol.__dict__ = volume.__dict__
        newvol.md5 = None
        newvol.md5len = 32
        newvol.eutest_failmsg = None
        newvol.eutest_laststatus = newvol.status
        newvol.eutest_ageatstatus = 0 
        newvol.eutest_cmdstart = cmdstart or time.time()
        newvol.eutest_createorder = None
        newvol.eutest_cmdtime = None
        return newvol
    
    def update(self):
        super(EuVolume, self).update()
        self.set_last_status()
    
    def set_last_status(self,status=None):
        self.eutest_laststatus = self.status
        self.eutest_laststatustime = time.time()
        self.eutest_ageatstatus = "{0:.2f}".format(time.time() - self.eutest_cmdstart)
        
    def printself(self,title=True, footer=True, printmethod=None):
        buf = "\n"
        if title:
            buf += str("------------------------------------------------------------------------------------------------------------------------------\n")
            buf += str('ID').center(15)+'|'+str('ORDER').center(5)+'|'+str('LASTSTATUS').center(10)+'|'+str('TESTSTATUS').center(10)+'|'+str('AGE@STATUS').center(10)+'|'+str('SIZE').center(4)+'|'+str('FROM_SNAP').center(15)+'|'+str('MD5_SUM').center(33)+'|'+str('MD5LEN').center(6)+'|'+str('INFO_MSG')+'\n'
            buf += str("------------------------------------------------------------------------------------------------------------------------------\n")
        buf += str(self.id).center(15)+'|'+str(self.eutest_createorder).center(5)+'|'+str(self.eutest_laststatus).center(10)+'|'+str(self.status).center(10)+'|'+str(self.eutest_ageatstatus).center(10)+'|'+str(self.size).center(4)+'|'+str(self.snapshot_id).center(15)+'|'+str(self.md5).center(33)+'|'+str(self.md5len).center(6)+'|'+str(self.eutest_failmsg).rstrip()
        if footer:
            buf += str("------------------------------------------------------------------------------------------------------------------------------\n")
        if printmethod:
            printmethod(buf)
        return buf
    
        
        
        
        
        
        
