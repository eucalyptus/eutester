import threading
import time
import re
import sys
import Queue 
from eutester.sshconnection import SshConnection
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult



my_queue = Queue.Queue()


class Mpath_Monkey(EutesterTestCase):
    #a unique comment to add to iptables rules to signify the rule was added by this test
    ipt_msg = "eutester block data to san"
    
    def __init__(self):
        self.setuptestcase()
        self.setup_parser(testname='Mpath_monkey', vmtype=False,zone=False, keypair=False,emi=False,credpath=False,
                          description='Run multipath failover script')
        self.parser.add_argument('--host', help='String representing host address or FQDN',default=None)
        self.parser.add_argument('--username', help='String representing username for host login, default:root',default='root')
        self.parser.add_argument('--keypath', help='String representing local path to host ssh key',default=None)
        self.parser.add_argument('--interval', help='Integer representing seconds between path failover',default=30)
        self.parser.add_argument('--restore_time', help='Integer representing seconds to allow path recovery',default=30)
        self.parser.add_argument('--sp_ip_list', help='String with SP addrs, comma delimited',default="10.109.25.186,192.168.25.182")
        
        self.get_args()
        
        self.ssh = SshConnection( self.args.host, keypath=self.args.keypath, password=self.args.password, username=self.args.username, 
                                  debugmethod=self.debug, verbose=True)
        self.sys = self.ssh.sys
        self.cmd = self.ssh.cmd
        self.interval = int(self.args.interval)
        self.restore_time = int(self.args.restore_time)
        self.start = time.time()
        
        self.sp_ip_list = []
        print self.args.sp_ip_list
        if self.args.sp_ip_list:
            
            self.args.sp_ip_list = str(self.args.sp_ip_list).split(',')
            for ip in self.args.sp_ip_list:
                ip = str(ip).lstrip().rstrip()
                print 'adding ip to sp_ip_list:'+str(ip)
                self.sp_ip_list.append(ip)
        self.timer = None
        
        
    def set_timer(self, interval=30, cb=None, *args):
        self.debug("set_timer starting with interval "+str(interval)+"...")
        if self.timer:
            self.timer.cancel()
            self.timer = None
        self.timer = threading.Timer(interval, cb, args)
    
    def is_path_blocked(self, addr):
        self.debug('Checking iptables for path state: '+str(addr)+' ...')
        out = self.sys('iptables -L',code=0)
        for line in out:
            if re.match(self.ipt_msg, line) and re.match("^DROP", line):
                #make sure we don't get a partial match...
                lines = line.rstrip().split()
                for word in lines:
                    if re.match(addr, word):
                        return True
        return False
    
    def restore_path(self, addr):
        self.debug("restore_path starting for path:'"+str(addr)+"'")
        if self.is_path_blocked(addr):
            self.debug('Attempting to remove iptables rule blocking traffic to: "'+str(addr)+'"')
            self.sys('iptables -D OUTPUT -j DROP -d '+str(addr), code=0)
            self.wait(2)
            #time.sleep(2)
            if not self.can_ping_path(addr):
                raise Exception("Could not ping path:"+str(addr)+" after restoring path rule")
    
    def restore_paths(self, addr_list ):
        self.debug('restore_paths starting, for list:'+str(",").join(addr_list))
        for addr in addr_list:
            self.restore_path(addr)  
             
    def block_path(self,addr):
        self.debug('Attempting to add iptables rule blocking traffic to: "'+str(addr)+'"')
        self.sys('iptables -A OUTPUT -j DROP -d '+str(addr)+' -m comment --comment "'+str(self.ipt_msg)+'"', code=0)
                    
    def can_ping_path(self, addr, count=1, timeout=10):
        self.debug('can_ping_path starting:'+str(addr)+", count:"+str(count)+", timeout:"+str(timeout))
        try:
            self.sys('ping -c '+str(count)+' -t '+str(timeout), code=0)
            return True
        except:pass
        return False
 
    def block_single_path_cycle(self, lastblocked=None):
        self.debug('block_single_path_cycle start...')
        try:
            #iterate through sp ip list, block the next available ip in the list. 
            #if we've reached the end of the list restore all paths for an interval period
            block = None
            self.restore_paths(self.sp_ip_list)
            self.wait(self.restore_time)
            #time.sleep(self.restore_time)
            if lastblocked:
                if lastblocked != self.sp_ip_list[len(self.sp_ip_list)-1]:
                    for path in self.sp_ip_list:
                        if lastblocked == path:
                            block = self.sp_ip_list[self.sp_ip_list.index(path)]
                            break    
            else:
                block = self.sp_ip_list[0]
            self.debug("block_single_path_cycle, attempting to block path:"+str(block)+", set timer to:"+str(self.interval))
            self.block_path(block)
            self.set_timer(self.interval, self.block_single_path_cycle, block)
            self.timer.start()
        except KeyboardInterrupt, k:
            if self.timer:
                timer.cancel()
                raise Exception('Caught keyboard interrupt...')
        nqstr = 'Running for: '+str(int(time.time()-self.start))+' seconds'
        my_queue.put(nqstr)
        
    def wait(self,seconds):
        seconds = int(seconds)
        self.debug("Waiting for '"+str(seconds)+"' seconds...", traceback=2)
        sys.stdout.write('Elapsed:')
        for x in xrange(0,seconds):
            if (x%seconds == 0):
                sys.stdout.write(str(x))
            else:
                sys.stdout.write('-')
            sys.stdout.flush()
            time.sleep(1)
        print(str(seconds))
 
        
        
if __name__ == "__main__":
    monkey = Mpath_Monkey()
    m_thread = threading.Thread(target=monkey.block_single_path_cycle)
    m_thread.daemon=True
    #monkey.block_single_path_cycle(None)
    m_thread.start()
    try:
        #while(1):
        #    time.sleep(2)
        while m_thread.isAlive: 
            m_thread.join(5)
            time.sleep(1)
            try:
                qstr = my_queue.get_nowait()
            except Queue.Empty, qe:
                print "(q-check)",
                sys.stdout.flush()
            else:
                print "Got from thread queue: "+qstr
            
    except KeyboardInterrupt:
        if monkey.timer:
            monkey.timer.cancel()
            print "Caught keyboard interrupt, killing timer and exiting..."
            sys.exit()
            
            
        
            

