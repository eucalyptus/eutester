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
                
    def get_property(self, tester, prop):
        '''
        Returns a tuple containing the current property value from a eucaops/eutester object, plus the property string. 
        tester - mandatory - the eucaops/eutester object to fetch the property from
        prop - mandatory - string representing the property to fetch. 
        '''
        return self.get_property_at_tester(prop, eucaops=tester)
        
    def get_property_at_tester(self, prop, eucaops=None):
        '''
        Returns a tuple containing the current property value plus the property string. 
        prop - mandatory - string representing the property to fetch. 
        ecuaops -optional - the eucaops/eutester object to fetch the property from
        '''
        print "Getting property:"+prop
        if eucaops is None:
            eucaops = self.tester
        prop_string = eucaops.sys('euca-describe-properties | grep ' + prop)
        if (prop_string != []):
            value = str(prop_string[0]).split()[2]
        else:
            raise Exception("describe properties returned null for "+prop)
        return value,prop
    
    def set_property(self, tester, prop, value):
        '''
        Sets the property 'prop' at eucaops/eutester object 'tester' to 'value'
        tester - mandatory - the eucaops/eutester object to set the property at
        prop - mandatory - string representing the property to set
        value - mandatory - string representing the value to set the property to
        '''
        return self.set_property_at_tester(prop, value, eucaops=tester)
        
    def set_property_at_tester(self,  prop, value, eucaops=None):
        '''
        Sets the property 'prop' at eucaops/eutester object 'tester' to 'value'    
        Returns new value  
        prop - mandatory - string representing the property to set
        value - mandatory - string representing the value to set the property to
        eucaops - optional - the eucaops/eutester object to set the property at
        '''
        value = str(value)
        if eucaops is None:
            eucaops = self.tester
        self.debug('Setting property('+prop+') to value:'+str(value))
        ret_string = str(eucaops.sys('euca-modify-property -p '+prop+'='+str(value))[0])
        ret_value= ret_string.split()[2]
        if (ret_value != value):
            raise Exception("set property("+prop+") to value("+str(value)+") failed.Ret Value ("+str(ret_value)+")\nRet String\n"+ret_string)
        return ret_value
        
    def reset_property_to_default(self, prop, eucaops=None):
        '''
        Sets a property 'prop' at eucaops/eutester object 'eucaops' to it's default value
        Returns new value
        prop - mandatory - string representing the property to set
        ucaops - optional - the eucaops/eutester object to set the property at
        '''
        if eucaops is None:
            eucaops = self.tester
        ret_string = str(eucaops.sys('euca-modify-property -r '+prop)[0])
        ret_value= ret_string.split()[2]
        self.debug('Reset property('+prop+') to default value('+str(ret_value)+')')
        return ret_value
        
    def get_property_default_value(self, prop, ireadthewarning=False, eucaops=None):
        '''
        Note: This method is intrusive! It will briefly reset the property
        This is a temporary method to get a properties default method
        prop - mandatory - string, eucalyptus property
        ireadthewarning - mandatory - boolean, to warn user this method is intrusive 
        '''
        if (ireadthewarning is False):
            raise Exception("ireadthewarning is set to false in get_property_default_value")
        if eucaops is None:
            eucaops = self.tester
        original = self.get_property(prop, eucaops)
        default = self.reset_property_to_default(prop, eucaops)
        self.set_property(prop, original, eucaops)
        return default
    
        
        
        
    '''
    ########################################################################
    STORAGE RELATED PROPERTIES
    ########################################################################
    '''
          
    #PARTI00.storage.maxvolumesizeingb
    def get_max_volume_size_in_gb(self, tester=None, zone='PARTI00'):
        value = self.get_property(tester, zone+'.storage.maxvolumesizeingb')
        return value
    
    def set_max_volume_size_in_gb(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.maxvolumesizeingb', value)
    
    #PARTI00.storage.maxtotalvolumesizeingb 
    def get_max_total_volume_size_in_gb(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.maxtotalvolumesizeingb')
        return value
    
    def set_max_total_volume_size_in_gb(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.maxtotalvolumesizeingb', value)
        
    #PARTI00.storage.zerofillvolumes 
    def get_zerofillvolumes(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.zerofillvolumes')
        return value
    
    def set_zerofillvolumes(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.zerofillvolumes', value)
        
    #PARTI00.storage.volumesdir 
    def get_volumesdir(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.volumesdir')
        return value
    
    def set_volumesdir(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.volumesdir', value)
        
    #PARTI00.storage.tid
    def get_storage_tid(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.tid')
        return value
    
    def set_storage_tid(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.tid', value)
    
    #PARTI00.storage.storeprefix
    def get_storage_storeprefix(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.storeprefix')
        return value
    
    def set_storage_storeprefix(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.storeprefix', value)
    
    #PARTI00.storage.storageinterface
    def get_storageinterface(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.storageinterface')
        return value
    
    def set_storageinterface(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.storageinterface', value)
    
    #PARTI00.storage.snappercent
    def get_storage_snappercent(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.snappercent')
        return value
    
    def set_storage_snappercent(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.snappercent', value)
        
    #PARTI00.storage.shouldtransfersnapshots
    def get_storage_shouldtransfersnapshots(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.shouldtransfersnapshots')
        return value
    
    def set_storage_shouldtransfersnapshots(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.shouldtransfersnapshots', value)
        
    #PARTI00.storage.sanuser
    def get_storage_sanuser(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.sanuser')
        return value
    
    def set_storage_sanuser(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.sanuser', value)
    
    #PARTI00.storage.sanpassword
    def get_storage_sanpassword(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.sanpassword')
        return value
    
    def set_storage_sanpassword(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.sanpassword', value)
        
    #PARTI00.storage.sanhost
    def get_storage_sanhost(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.sanhost')
        return value
    
    def set_storage_sanhost(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.sanhost', value)
        
    #PARTI00.storage.minornumber
    def get_storage_minornumber(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.minornumber')
        return value
    
    def set_storage_minornumber(self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.minornumber', value)
    
    #PARTI00.storage.majornumber 
    def get_storage_majornumber (self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.majornumber ')
        return value
    
    def set_storage_majornumber (self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.majornumber', value)
        
    #PARTI00.storage.dasdevice 
    def get_storage_dasdevice (self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.dasdevice')
        return value
    
    def set_storage_dasdevice (self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.dasdevice ', value)
        
    #PARTI00.storage.aggregate
    def get_storage_aggregate (self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.aggregate')
        return value
    
    def set_storage_aggregate (self, value, tester=None, zone='PARTI00'):
        self.set_property(tester, zone+'.storage.aggregate', value)  
    
        
        
        
    '''
    ########################################################################
    Walrus related properties
    ########################################################################
    '''
    #walrus.storagemaxtotalsnapshotsizeingb 
    def get_max_total_snap_size_in_gb(self, tester=None):
        value = self.get_property(tester, 'walrus.storagemaxtotalsnapshotsizeingb')
        return value
    def set_max_total_snap_size_in_gb(self, value, tester=None):
        self.set_property(tester, 'walrus.storagemaxtotalsnapshotsizeingb', value)
    
    
    