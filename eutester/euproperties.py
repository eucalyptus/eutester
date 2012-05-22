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
Place holder class to provide convenience for testing, modifying, and retrieving Eucalyptus cloud property information
Intention is to reduce the time in looking up property names, and values outside of the eutester test lib, etc
Note: Debug output for the tester.sys command are controled by the eutester/eucaops object 

Sample:
    
    props = EucaProperties(myeutesterobject)
    #get some property values 
    mysanhost = props.get_storage_sanhost()[0]
    mysanhostp1 = props.get_storage_sanhost(zone='PARTI01')[0]
    
    #use a convenience method to set a property
    prop.set_storage_sanhost('192.168.1.1',zone='PARTI01')
    
    #get the property string value for a given property
    sanhostp1propertystring = props.get_storage_sanhost(zone=PARTI01)[1]
    
    #reset a cloud property to it's default value
    props.reset_property_to_default(sanhostp1propertystring)
    
    
    

'''
from eucaops import Eucaops
from eutester import Eutester



class EucaProperties():
    tester = None
    verbose = False
    debugmethod = None
    
    def __init__(self, tester, verbose=False, debugmethod=None):
        self.tester = tester
        self.debugmethod = debugmethod
        self.verbose = verbose
        
    def debug(self,msg):
        '''
        simple method for printing debug. 
        msg - mandatory - string to be printed
        method - optional - callback to over ride default printing method 
        '''
        if (self.verbose is True):
            if (self.debugmethod is None):
                print (str(msg))
            else:
                self.debugmethod(msg)
             
            
    def get_property(self, prop):
        '''
        Returns a tuple containing the current property value plus the property string. 
        prop - mandatory - string representing the property to fetch. 
        ecuaops -optional - the eucaops/eutester object to fetch the property from
        '''
        self.debug("Getting property:"+prop)
        eucaops = self.tester
        prop_string = eucaops.sys('euca-describe-properties | grep ' + prop)
        if (prop_string != []):
            value = str(prop_string[0]).split()[2]
        else:
            raise EuPropertiesException("describe properties returned null for "+prop)
        return value,prop
    
    
    def set_property(self,  prop, value):
        '''
        Sets the property 'prop' at eucaops/eutester object 'tester' to 'value'    
        Returns new value  
        prop - mandatory - string representing the property to set
        value - mandatory - string representing the value to set the property to
        eucaops - optional - the eucaops/eutester object to set the property at
        '''
        value = str(value)
        eucaops = self.tester
        self.debug('Setting property('+prop+') to value:'+str(value))
        ret_string = eucaops.sys('euca-modify-property -p '+prop+'='+str(value))
        if ( ret_string != [] ):
            ret_value= str(ret_string[0]).split()[2]
        else:
            raise EuPropertiesException("set_property output from modify was None")
        
        if (ret_value != value):
            raise EuPropertiesException("set property("+prop+") to value("+str(value)+") failed.Ret Value ("+str(ret_value)+")\nRet String\n"+ret_string)
        
        return ret_value
        
    def reset_property_to_default(self, prop):
        '''
        Sets a property 'prop' at eucaops/eutester object 'eucaops' to it's default value
        Returns new value
        prop - mandatory - string representing the property to set
        ucaops - optional - the eucaops/eutester object to set the property at
        '''
    
        eucaops = self.tester
        ret_string = str(eucaops.sys('euca-modify-property -r '+prop)[0])
        ret_value= ret_string.split()[2]
        self.debug('Reset property('+prop+') to default value('+str(ret_value)+')')
        return ret_value
        
    def get_property_default_value(self, prop, ireadthewarning=False):
        '''
        Note: This hack method is intrusive! It will briefly reset the property
        This is a temporary method to get a properties default method
        prop - mandatory - string, eucalyptus property
        ireadthewarning - mandatory - boolean, to warn user this method is intrusive 
        '''
        if (ireadthewarning is False):
            raise EuPropertiesException("ireadthewarning is set to false in get_property_default_value")
    
        original = self.get_property(prop)[0]
        default = self.reset_property_to_default(prop)
        self.set_property(prop, original)
        return default
    
        
        
        
    '''
    ########################################################################
    STORAGE RELATED PROPERTY METHODS...
    ########################################################################
    '''
          
    #PARTI00.storage.maxvolumesizeingb
    def get_storage_maxvolumesizeingb(self,  zone='PARTI00'):
        value = self.get_property(  zone+'.storage.maxvolumesizeingb')
        return value
    
    def set_storage_maxvolumesizeingb(self, value, zone='PARTI00'):
        return self.set_property(  zone+'.storage.maxvolumesizeingb', value)
    
    #PARTI00.storage.maxtotalvolumesizeingb 
    def get_storage_maxtotalvolumesizeingb(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.maxtotalvolumesizeingb')
        return value
    
    def set_storage_maxtotalvolumesizeingb(self, value,  zone='PARTI00'):
        value = self.set_property(  zone+'.storage.maxtotalvolumesizeingb', value)
        return value
    
    #PARTI00.storage.zerofillvolumes 
    def get_storage_zerofillvolumes(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.zerofillvolumes')
        return value
    
    def set_storage_zerofillvolumes(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.zerofillvolumes', value)
        
    #PARTI00.storage.volumesdir 
    def get_storage_volumesdir(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.volumesdir')
        return value
    
    def set_storage_volumesdir(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.volumesdir', value)
        
    #PARTI00.storage.tid
    def get_storage_tid(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.tid')
        return value
    
    def set_storage_tid(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.tid', value)
    
    #PARTI00.storage.storeprefix
    def get_storage_storeprefix(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.storeprefix')
        return value
    
    def set_storage_storeprefix(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.storeprefix', value)
    
    #PARTI00.storage.storageinterface
    def get_storageinterface(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.storageinterface')
        return value
    
    def set_storageinterface(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.storageinterface', value)
    
    #PARTI00.storage.snappercent
    def get_storage_snappercent(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.snappercent')
        return value
    
    def set_storage_snappercent(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.snappercent', value)
        
    #PARTI00.storage.shouldtransfersnapshots
    def get_storage_shouldtransfersnapshots(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.shouldtransfersnapshots')
        return value
    
    def set_storage_shouldtransfersnapshots(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.shouldtransfersnapshots', value)
        
    #PARTI00.storage.sanuser
    def get_storage_sanuser(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.sanuser')
        return value
    
    def set_storage_sanuser(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.sanuser', value)
    
    #PARTI00.storage.sanpassword
    def get_storage_sanpassword(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.sanpassword')
        return value
    
    def set_storage_sanpassword(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.sanpassword', value)
        
    #PARTI00.storage.sanhost
    def get_storage_sanhost(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.sanhost')
        return value
    
    def set_storage_sanhost(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.sanhost', value)
        
    #PARTI00.storage.minornumber
    def get_storage_minornumber(self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.minornumber')
        return value
    
    def set_storage_minornumber(self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.minornumber', value)
    
    #PARTI00.storage.majornumber 
    def get_storage_majornumber (self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.majornumber ')
        return value
    
    def set_storage_majornumber (self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.majornumber', value)
        
    #PARTI00.storage.dasdevice 
    def get_storage_dasdevice (self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.dasdevice')
        return value
    
    def set_storage_dasdevice (self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.dasdevice ', value)
        
    #PARTI00.storage.aggregate
    def get_storage_aggregate (self,   zone='PARTI00'): 
        value = self.get_property(  zone+'.storage.aggregate')
        return value
    
    def set_storage_aggregate (self, value,  zone='PARTI00'):
        return self.set_property(  zone+'.storage.aggregate', value)  
    
        
        
        
    '''
    ########################################################################
    WALRUS RELATED PROPERTY METHODS...
    ########################################################################
    '''
    #walrus.storagemaxtotalsnapshotsizeingb 
    def get_walrus_storagemaxtotalsnapshotsizeingb(self, tester=None):
        value = self.get_property(  'walrus.storagemaxtotalsnapshotsizeingb')
        return value
    def set_walrus_storagemaxtotalsnapshotsizeingb(self, value, tester=None):
        return self.set_property(  'walrus.storagemaxtotalsnapshotsizeingb', value)
    
    
    
    
    
    
    
    
class EuPropertiesException(Exception):
    def __init__(self, value):
        self.value = value
    def __str__ (self):
        return repr(self.value)
    
    