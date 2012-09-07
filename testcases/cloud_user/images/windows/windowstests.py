
from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult
from imageutils import ImageUtils
from testcases.cloud_user.images.imageutils import ImageUtils
import socket

class WindowsTests(EutesterTestCase):
    
    def __init__(self, 
                 tester=None, 
                 config_file=None, 
                 cred_path=None,
                 password="foobar", 
                 credpath=None, 
                 destpath='/disk1/storage/',  
                 time_per_gig = 300,
                 inter_bundle_timeout=120, 
                 upload_timeout=0,
                 eof=True,
                 work_component=None,
                 component_credpath=None,
                 bucketname = None,
                 url=None
                 ):
        if tester is None:
            self.tester = Eucaops( config_file=config_file,password=password,credpath=credpath)
        else:
            self.tester = tester
        self.tester.exit_on_fail = eof
        self.destpath = str(destpath)
        self.bucketname = bucketname
        self.component = work_component 
        self.component_credpath = component_credpath
        self.time_per_gig = time_per_gig
        self.credpath=credpath or self.tester.credpath
        self.url = url
        self.upload_timeout = upload_timeout
        self.inter_bundle_timeout = inter_bundle_timeout
        self.iu = ImageUtils(tester=self.tester, destpath=self.destpath, time_per_gig=self.time_per_gig, work_component=self.component)
        
        
    def create_windows_emi_from_url(self,
                                      url, 
                                      component = None, 
                                      component_credpath = None,
                                      bucketname = None, 
                                      destpath = None, 
                                      inter_bundle_timeout = None, 
                                      upload_timeout = None,
                                      wget_user = None,
                                      wget_password = None,
                                      time_per_gig = None,
                                      ):
        '''
        Attempts to download (wget), bundle, upload and register a windows image at 'url' 
        Work is done on a given machine and requires euca2ools present on that machine. 
        Returns the emi of the registered image
        '''
        return self.iu.create_emi_from_url(url, 
                                           component = (component or self.component), 
                                           bucketname = (bucketname or self.bucketname), 
                                           component_credpath = (component_credpath or self.component_credpath), 
                                           destination = (destination or self.destpath),
                                           interbundle_timeout = (inter_bundle_timeout or self.inter_bundle_timeout), 
                                           upload_timeout = (upload_timeout or self.upload_timeout),
                                           destpath = (destination or self.destpath),
                                           wget_user = (wget_user), 
                                           wget_password = (wget_password),   
                                           time_per_gig = (time_per_gig or self.time_per_gig) )
        
    def create_windows_emi_from_file(self,
                                     fpath,
                                     component = None, 
                                     component_credpath = None,
                                     bucketname = None, 
                                     destpath = None, 
                                     inter_bundle_timeout = None, 
                                     upload_timeout = None,
                                     time_per_gig = None,
                                     ):
        '''
        Attempts bundle, upload and register a windows image on component filesystem at fpath.  
        Work is done on a given machine and requires euca2ools present on that machine. 
        Returns the emi of the registered image
        '''
        return self.iu.create_emi_from_url(url, 
                                           component = (component or self.component), 
                                           bucketname = (bucketname or self.bucketname), 
                                           component_credpath = (component_credpath or self.component_credpath), 
                                           destination = (destination or self.destpath),
                                           interbundle_timeout = (inter_bundle_timeout or self.inter_bundle_timeout), 
                                           upload_timeout = (upload_timeout or self.upload_timeout),
                                           destpath = (destination or self.destpath),
                                           filepath = fpath,
                                           time_per_gig = (time_per_gig or self.time_per_gig) )
        
    
                              
    def test_rdp_port(self, ip, port=3389):
        self.debug('test_rdp_port, ip:'+str(ip)+', port:'+str(port))
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.connect((ip, port)) 
        except socket.error, se:
            self.debug('test_rdp_port failed socket error:'+str(se[0]))
            #handle specific errors here maybe later...
            ecode=se[0]
            if ecode == socket.errno.ECONNREFUSED:
                self.debug("test_rdp_port: Connection Refused")
            if ecode == socket.errno.ENETUNREACH:
                self.debug("test_rdp_port: Network unreachable")
            raise se
        except socket.timeout, st:
            self.debug('test_rdp_port failed socket timeout')
            raise st
        finally:
            s.close()
        self.debug('test_rdp_port, success')
        
    
        
        
        
        