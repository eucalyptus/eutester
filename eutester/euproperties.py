'''
Created on Mar 7, 2012
@author: clarkmatthew
Place holder class to provide convenience for testing, modifying, and retrieving Eucalyptus cloud property information
Intention is to reduce the time in looking up property names, and values outside of the eutester test lib
'''
from eucaops import Eucaops
from eutester import Eutester



class EucaProperties():
    tester = None
    def __init__(self, tester):
        self.tester = tester
        
        
    def get_property(self, prop, eucaops=None):
        if eucaops is None:
            eucaops = self.tester
        prop_string = str(eucaops.sys('euca-descpribe-properties | grep ' + prop)[0])
        value = prop_string.split()[2]
        return value
    
    def get_max_total_snap_size_in_gb(self, tester=None):
        value = self.get_property(tester, 'walrus.storagemaxtotalsnapshotsizeingb')
        return value
    
    def get_max_volume_size_in_gb(self, tester=None, zone='PARTI00'):
        value = self.get_property(tester, zone+'.storage.maxvolumesizeingb')
        return value
    
    def get_max_total_volume_size_in_gb(self, tester=None,  zone='PARTI00'): 
        value = self.get_property(tester, zone+'.storage.maxtotalvolumesizeingb')
        return value