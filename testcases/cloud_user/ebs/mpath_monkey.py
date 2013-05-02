import threading
import time
import re
import sys
import Queue 
from eutester.sshconnection import SshConnection
from eutester.eutestcase import EutesterTestCase
from eutester.eutestcase import EutesterTestResult
import types


my_queue = Queue.Queue()


class Mpath_Monkey(EutesterTestCase):
    #a unique comment to add to iptables rules to signify the rule was added by this test
    ipt_msg = "eutester block data to san"
    
    def __init__(self,
                 node=None,
                 queue=None,
                 interval=None,
                 restore_time=None,
                 sp_ip_list=None,
                 path_iterations=None):
        self.queue = queue or my_queue
        self.setuptestcase()
        if not (node or queue or sp_ip_list):
            self.setup_parser(testname='Mpath_monkey', vmtype=False,zone=False, keypair=False,emi=False,credpath=False,
                              description='Run multipath failover script')
            self.parser.add_argument('--clear_rules', help='If set will clear all eutester applied rules matching ipt_msg string',action='store_true', default=False)
            self.parser.add_argument('--hostname', help='String representing host address or FQDN',default=None)
            self.parser.add_argument('--clear_on_exit', help='If set will clear rules on exit',action='store_true', default=False)
            self.parser.add_argument('--username', help='String representing username for host login, default:root',default='root')
            self.parser.add_argument('--keypath', help='String representing local path to host ssh key',default=None)
            self.parser.add_argument('--interval', help='Integer representing seconds between path failover',default=30)
            self.parser.add_argument('--restore_time', help='Integer representing seconds to allow path recovery',default=15)
            self.parser.add_argument('--sp_ip_list', help='String with SP addrs, comma delimited',default=None)
            self.parser.add_argument('--path_iterations', help='Number of times to iterate through sp_ip_list when \
                                     blocking paths. "0" loops forever', default=2)
            self.get_args()

        # Allow __init__ to get args from __init__'s kwargs or through command line parser...
        """
        for kw in kwargs:
            print 'Setting kwarg:' + str(kw) + " to " + str(kwargs[kw])
            self.set_arg(kw ,kwargs[kw])
        """

        if self.has_arg('path_iterations'):
            self.path_iterations =  self.args.path_iterations
        else:
            self.path_iterations =  path_iterations or 2
        self.remaining_iterations = self.path_iterations or -1
        self.node = node
        if self.node:
            self.host = node.hostname
            self.ssh = self.node.machine.ssh
        else:
            self.host = self.args.hostname
            self.ssh = SshConnection(self.args.host,
                                     keypath=self.args.keypath,
                                     password=self.args.password,
                                     username=self.args.username,
                                     debugmethod=self.debug,
                                     verbose=True)
        self.sys = self.ssh.sys
        self.cmd = self.ssh.cmd

        if self.has_arg('interval'):
            self.interval = int(self.args.interval)
        else:
            self.interval = interval or 30

        if self.has_arg('restore_time'):
            self.restore_time = int(self.args.restore_time)
        else:
            self.restore_time = restore_time or 15
        self.start = time.time()
        self.lastblocked = None
        self.blocked = []
        self.get_sp_ip_list(sp_ip_list=sp_ip_list)
        self.timer = None
        self.debug('Mpath_Monkey init:' \
                    + "\nhost:" + str(self.host) \
                    + "\nsp_ipt_list:" + str(self.sp_ip_list) \
                    + "\ninterval:" + str(self.interval) \
                    + "\nrestore_time:" + str(self.restore_time))



    def get_sp_ip_list(self,sp_ip_list=None, sp_ip_list_string=None):
        ret_list = []
        if sp_ip_list and isinstance(sp_ip_list, types.ListType):
            ret_list = sp_ip_list
        else:
            sp_ip_list_string = sp_ip_list_string or self.args.sp_ip_list
            if not sp_ip_list_string:
                raise Exception('No sp_ip_list provided')
            for path in str(sp_ip_list_string).split(','):
                for part in path.split(':'):
                    #Don't use iface strings for this test...
                    if not re.search('iface', part):
                        ret_list.append(part)
        if not ret_list:
            raise Exception('No sp_ip_list parsed from sp_ip_list_string:'+str(sp_ip_list_string))
        self.sp_ip_list = ret_list
        return ret_list

    def clear_all_eutester_rules(self, timeout=60):
        self.debug('Clear_all_eutester_rules...')
        #clears all rules which match the description string ipt_msg
        start = time.time()
        elapsed = 0
        out = self.sys('iptables -L -n --line-numbers | grep "'+str(self.ipt_msg)+'"')
        while out and elapsed < timeout:
            elapsed = int(time.time()-start)
            self.debug("Attempting to remove "+str(len(out))+" eutester rules from system. Elapsed: "+str(elapsed)+'/'+str(timeout))
            for line in out:
                self.debug('Clearing rule: '+str(line))
                rule_number = str(line).split()[0]
                self.sys('iptables -D OUTPUT '+str(rule_number))
            out = self.sys('iptables -L -n --line-numbers | grep "'+str(self.ipt_msg)+'"')
            time.sleep(2)
            
        
        
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


    def get_blocked_paths(self):
        list = []
        for ip in self.sp_ip_list:
            if self.is_path_blocked(ip):
                list.append(ip)
        self.blocked = list
        return list


    def restore_path(self, addr):
        self.debug("restore_path starting for path:'"+str(addr)+"'")
        if self.is_path_blocked(addr):
            self.debug('Attempting to remove iptables rule blocking traffic to: "'+str(addr)+'"')
            self.sys('iptables -D OUTPUT -j DROP -d '+str(addr), code=0)
            self.wait(2)
            #time.sleep(2)
            if not self.can_ping_path(addr):
                raise Exception("Could not ping path:"+str(addr)+" after restoring path rule")
        if addr in self.blocked:
            self.blocked.remove(addr)
    
    def restore_paths(self, addr_list ):
        self.debug('restore_paths starting, for list:'+str(",").join(addr_list))
        for addr in addr_list:
            self.restore_path(addr)  
             
    def block_path(self,addr):
        self.debug('Attempting to add iptables rule blocking traffic to: "'+str(addr)+'"')
        #First delete rule before adding in the case a duplicate exists
        try:
            self.sys('iptables -D OUTPUT -j DROP -d '+str(addr))
        except: pass
        #Add rule to block...
        self.sys('iptables -A OUTPUT -j DROP -d '+str(addr)+' -m comment --comment "'+str(self.ipt_msg)+'"', code=0)
        if not addr in self.blocked:
            self.blocked.append(addr)
        self.lastblocked = addr

    def can_ping_path(self, addr, count=1, timeout=10):
        self.debug('can_ping_path starting:'+str(addr)+", count:"+str(count)+", timeout:"+str(timeout))
        try:
            self.sys('ping -c '+str(count)+' -t '+str(timeout), code=0)
            return True
        except:pass
        return False
 
    def block_single_path_cycle(self, lastblocked=None, wait_for_clear=True):
        self.debug('block_single_path_cycle start...')
        try:
            #iterate through sp ip list, block the next available ip in the list. 
            #if we've reached the end of the list restore all paths for an interval period
            block = None
            if not self.sp_ip_list:
                return
            self.clear_all_eutester_rules()
            if self.remaining_iterations == 0:
                return
            #self.restore_paths(self.sp_ip_list)
            blocked_paths = self.get_blocked_paths()
            if blocked_paths:
                if not wait_for_clear:
                    self.set_timer(self.restore_time, self.get_blocked_paths)
                    return
                else:
                    self.wait(self.restore_time)
            lastblocked = lastblocked or self.lastblocked
            #time.sleep(self.restore_time)
            if lastblocked:
                index = self.sp_ip_list.index(lastblocked)
                if index == (len(self.sp_ip_list)-1):
                    block = self.sp_ip_list[0]
                else:
                    block = self.sp_ip_list[index+1]
            else:
                block = self.sp_ip_list[0]
            self.debug("block_single_path_cycle, attempting to block path:"+str(block)+", set timer to:"+str(self.interval))
            self.remaining_iterations -= 1
            self.block_path(block)
            args = [block,wait_for_clear]
            self.set_timer(self.interval, self.block_single_path_cycle, args)
            self.timer.start()
        except KeyboardInterrupt, k:
            if self.timer:
                self.timer.cancel()
                raise Exception('Caught keyboard interrupt...')
        nqstr = 'Blocking:' +str(self.blocked)
        self.queue.put(nqstr)

    def get_blocked_string(self):
        out = ""
        for addr in self.blocked:
            out += str(addr) + ","
        return str(out)

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
    qinterval = int(monkey.args.interval) * (2+(len(monkey.sp_ip_list)))
    if monkey.args.clear_rules:
        monkey.clear_all_eutester_rules()
        sys.exit()
    else:
        m_thread = threading.Thread(target=monkey.block_single_path_cycle)
        m_thread.daemon=True
        #monkey.block_single_path_cycle(None)
        m_thread.start()
        try:
            #while(1):
            #    time.sleep(2)
            q_empty_cnt = 0 
            while m_thread.isAlive: 
                m_thread.join(5)
                time.sleep(1)
                try:
                    qstr = my_queue.get_nowait()
                except Queue.Empty, qe:
                    q_empty_cnt += 1
                    print "(q-check)",
                    sys.stdout.flush()
                else:
                    q_empty_cnt = 0
                    q_time = time.time()
                    print "Got from thread queue: "+qstr
                if q_empty_cnt > qinterval:
                    q_elapsed = int(time.time() - q_time )
                    raise Exception("q-check was empty for for "+str(q_elapsed)+" seconds")
        except KeyboardInterrupt:
            if monkey.timer:
                monkey.timer.cancel()
                print "Caught keyboard interrupt, killing timer and exiting..."
                if monkey.clean_on_exit:
                    monkey.clear_all_eutester_rules()
                sys.exit()
        except Exception, e:
            if monkey.timer:
                monkey.timer.cancel()
                print str(e)
                if monkey.args.clean_on_exit:
                    monkey.clear_all_eutester_rules()
                sys.exit()
       
            
            
        
            

