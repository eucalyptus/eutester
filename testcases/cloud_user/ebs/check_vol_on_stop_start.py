from eucaops import Eucaops
from eutester.eutestcase import EutesterTestCase
from eutester.euinstance import EuInstance
import time






class Check_vol_on_stop_start(EutesterTestCase):
        # init with argument list that makes these mandatory, but can fetch them from special 'args' later. 
        def __init__(self):
            self.setuptestcase()
            self.setup_parser(description="Test EBS on BFEBS during restart", testlist=False)
            self.parser.add_argument('--count',
                                     help='Number of times to start/stop instance', default=5)
            self.parser.add_argument('--pause',
                                     help='Number of seconds to pause between tests',default=5)
            self.parser.add_argument('--size',
                                     help='Size of volume to create', default=1)
            self.get_args()
            self.set_arg('azone', self.args.zone)
            try:
                self.do_with_args(self.checkargs)
            except Exception:
                raise Exception("Mandotory arguments missing: emi and zone and (credpath or (config and password))")
            self.tester = self.do_with_args(Eucaops)
            self.volume = None
            self.instance = EuInstance()
            #self.tester = Eucaops()
            
        def checkargs(self,emi,zone, credpath=None, config=None, password=None):
            if emi and zone and (credpath or (config and password)):
                return
            raise Exception("Mandotory arguments missing: emi and zone and (credpath or (config and password))")
        
        def get_keypair(self,keypair=None):
            self.keypair = None
            if keypair:
                self.keypair=self.tester.add_keypair(keypair)
        
    
            
        def run_instance(self):
            image = self.do_with_args(self.tester.get_emi)
            reservation = self.do_with_args(self.tester.run_instance, image=image, username='root')
            self.instance = reservation.instances[0]
            
        def create_volume(self):
            self.volume = self.do_with_args(self.tester.create_volume)
        
        def attach_volume_to_instance(self):
            self.instance.attach_volume(self.volume)
        
        def stop_start_check(self,pause=5):
            self.instance.stop_instance_and_verify()
            self.volume.update()
            self.instance.start_instance_and_verify(checkvolstatus=True)
            time.sleep(pause)
        
            
        def run_list(self):
            list=[]
            list.append(self.create_testunit_from_method(self.run_instance, eof=True))
            list.append(self.create_testunit_from_method(self.create_volume, eof=True))
            list.append(self.create_testunit_from_method(self.attach_volume_to_instance, eof=True))
            for x in xrange(1,int(self.args.count)):
                list.append(self.create_testunit_by_name('stop_start_check'))
            self.run_test_case_list(list)
            
if __name__ == "__main__":
    test = Check_vol_on_stop_start()
    test.run_list()


