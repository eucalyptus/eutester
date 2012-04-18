'''
Created on Mar 7, 2012
@author: clarkmatthew
Place holder for volume test specific convenience methods+objects to extend boto's volume class

'''
from boto.ec2.volume import Volume



class EuVolume(Volume):   
    md5 = ""
    '''
    Note: Different hypervisors will honor the requested cloud dev differently, so the requested device can not 
    be relied up as the device it attached to on the guest 'guestdev'
    '''
    guestdev = "" #the guest device name in use by this attached volume
    clouddev = "" #the device name given to the cloud as a request to be used. 
        
    @classmethod
    def make_euvol_from_vol(cls,volume):
        newvol = EuVolume(volume.connection)
        newvol.__dict__ = volume.__dict__
        newvol.md5 = ""
        return newvol
