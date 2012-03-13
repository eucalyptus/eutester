'''
Created on Mar 7, 2012
@author: clarkmatthew
Place holder for volume test specific convenience methods+objects to extend boto's volume class

'''
from boto.ec2.volume import Volume



class EuVolume(Volume):   
    md5 = ""
    dev = ""
        
    @classmethod
    def make_euvol_from_vol(cls,volume):
        newvol = EuVolume(volume.connection)
        newvol.__dict__ = volume.__dict__
        return newvol
