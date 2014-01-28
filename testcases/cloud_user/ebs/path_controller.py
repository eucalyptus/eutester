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


class Path_Controller(EutesterTestCase):
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
            self.setup_parser(testname='Path_Controller', vmtype=False,zone=False, keypair=False,emi=False,credpath=False,
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
        self.total_path_iterations = 0
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
        self.last_clear_attempt_time = 0
        self.last_cleared_time = 0
        self.last_block_time = 0
        self.debug('Path_Controller init:' \
                    + "\nhost:" + str(self.host) \
                    + "\nsp_ipt_list:" + str(self.sp_ip_list) \
                    + "\ninterval:" + str(self.interval) \
                    + "\nrestore_time:" + str(self.restore_time))


    def get_tag(self):
        return str(self.ipt_msg) + ", time:" + str(time.time())

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

    def get_eutester_current_block_rules(self):
        output = self.sys('iptables -L -n --line-numbers | grep "'+str(self.ipt_msg)+'"')
        return output

    def clear_all_eutester_rules(self, retry=True,timeout=60):
        #self.debug('Clear_all_eutester_rules...')
        self.last_clear_attempt_time = time.time()
        #clears all rules which match the description string ipt_msg
        start = time.time()
        elapsed = 0
        output = self.sys('iptables -L -n --line-numbers | grep "'+str(self.ipt_msg)+'"')
        while output and elapsed < timeout:
            elapsed = int(time.time()-start)
            self.debug("Attempting to remove "+str(len(output))+" eutester rules from system. Elapsed: "+str(elapsed)+'/'+str(timeout))
            for line in output:
                self.debug('Clearing rule: '+str(line))
                rule_number = str(line).split()[0]
                self.sys('iptables -D OUTPUT '+str(rule_number))
                self.sys('iptables -D INPUT '+str(rule_number))
            output = self.sys('iptables -L -n --line-numbers | grep "'+str(self.ipt_msg)+'"')
            if not output:
                self.last_cleared_time = time.time()
            else:
                self.last_cleared_time = 0
                if not retry:
                    return len(output)
                time.sleep(2)
        if not output:
            self.last_cleared_time = time.time()
        return len(output)

        
    def set_timer(self, interval=30, cb=None, *args):
        self.debug("set_timer starting with interval "+str(interval)+"...")
        if self.timer:
            self.timer.cancel()
            self.timer = None
        self.timer = threading.Timer(interval, cb, args)
    
    def is_path_blocked(self, addr):
        self.debug('Checking iptables for path state: '+str(addr)+' ...')
        if re.match('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', addr):
            out = self.sys('iptables -L -n ',code=0)
        else:
            out = self.sys('iptables -L ',code=0)
        for line in out:
            if re.search(self.ipt_msg, line) and re.match("^DROP", line):
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
        try:
            self.sys('iptables -D INPUT -j DROP -d '+str(addr))
        except: pass
        #Add rule to block...
        self.sys('iptables -A OUTPUT -j DROP -d '+str(addr)+' -m comment --comment "'+str(self.ipt_msg)+'"', code=0)
        self.sys('iptables -A INPUT -j DROP -d '+str(addr)+' -m comment --comment "'+str(self.ipt_msg)+'"', code=0)
        if not addr in self.blocked:
            self.blocked.append(addr)
        self.last_block_time = time.time()
        self.lastblocked = addr

    def can_ping_path(self, addr, count=1, timeout=10):
        self.debug('can_ping_path starting:'+str(addr)+", count:"+str(count)+", timeout:"+str(timeout))
        try:
            self.sys('ping -c '+str(count)+' -t '+str(timeout), code=0)
            return True
        except:pass
        return False

    def block_next_path(self, lastblocked=None):
        last_blocked = lastblocked or self.lastblocked
        if last_blocked:
            index = self.sp_ip_list.index(last_blocked)
            #If were at the end of the list return to index 0
            if index == (len(self.sp_ip_list)-1):
                block = self.sp_ip_list[0]
                self.total_path_iterations += 1
            else:
                block = self.sp_ip_list[index+1]
        else:
            block = self.sp_ip_list[0]
        self.debug("block_next_path, attempting to block path:"+str(block)+", set timer to:"+str(self.interval))
        self.block_path(block)
        return block

    def get_blocked_string(self):
        out = ""
        for addr in self.get_blocked_paths():
            out += str(addr) + ","
        return out

    def reset(self):
        if self.timer:
            self.timer.cancel()
        self.clear_all_eutester_rules()


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




    '''
    def cycle_paths(self, lastblocked=None, wait_for_clear=True, timeout_on_clear=30, set_timer=0):
        self.debug('block_next_path starting...')
        try:
            #iterate through sp ip list, block the next available ip in the list. 
            #if we've reached the end of the list restore all paths for an interval period

            #If we only have a single path, or no paths return...
            if not self.sp_ip_list or len(self.sp_ip_list) == 1:
                return

            blocked_paths = self.get_blocked_paths()
            if blocked_paths:
                self.status('Clearing all blocked paths prior to cycling paths')
                self.clear_all_eutester_rules()

            #If there was a blocked path(s) then wait for restore period...
            if wait_for_clear:
                elapsed = 0
                start = time.time()
                while blocked_paths and elapsed < timeout_on_clear:
                    self.clear_all_eutester_rules()
                    blocked_paths = self.get_blocked_paths()
                    if blocked_paths:
                        time.sleep(1)
                    elapsed = int(time.time() - start)
                if blocked_paths:
                    raise Exception('Could not clear blocked paths within ' + str(elapsed) + ' seconds; ' + ",".join(blocked_paths))
            block = self.block_next_path(lastblocked=lastblocked)
            args = [block,wait_for_clear]
            if set_timer:
                self.set_timer(set_timer, self.block_single_path_cycle, args)
                self.timer.start()
        except KeyboardInterrupt, k:
            if self.timer:
                self.timer.cancel()
                raise Exception('Caught keyboard interrupt...')
        nqstr = 'Blocking:' +str(self.blocked)
        self.queue.put(nqstr)
        '''


 
        

       
            
            
        
            

