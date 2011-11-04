# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
import re
import paramiko
import boto

class EucaTester:
    def __init__(self, config_file="../input/2b_tested.lst", host="CLC", password="foobar", keypath=None):
        """  
        EUCADIR => $eucadir, 
        VERIFY_LEVEL => $verify_level, 
        TOOLKIT => $toolkit, 
        DELAY => $delay, 
        FAIL_COUNT => $fail_count, 
        INPUT_FILE => $input_file, 
        PASSWORD => $password }
        , credpath=None, timeout=30, exit_on_fail=0
        EucaTester takes 2 arguments to their constructor
        1. Configuration file to use
        2. Eucalyptus component to connect to [CLC NC00 SC WS CC00] or a hostname
        3. Password to connect to the host
        4. 
        """
        print "Constructing EucaTester Object"
        self.config_file = config_file        
        self.password = password
        self.keypath = keypath
        #self.starttime = time()
        self.credpath = None
        self.timeout = 30
        self.exit_on_fail = 0
        self.eucapath = "/"
        self.fail_count = 0
        
        ### Read input file
        self.read_config(config_file)
        
        ### SETUP SSH CLIENT
        self.ssh = paramiko.SSHClient()
        if keypath == None:
            self.ssh.connect(host, password=password)
        else:
            self.ssh.connect(host, keyfile_name=keypath)
        
        ### read the input file and return the config object/hash whatever it needs to be
    def set_config_file(self, filepath):
        self.config_file = filepath
    
    def get_config_file(self):
        return self.config_file
        
    def set_host(self, host):
        self.host = host
        
    def set_credpath(self, path):
        self.credpath = path
        
    def set_timeout(self, seconds):
        self.timeout = seconds
        
    def set_eucapath(self, path):
        self.config_file = path
    
    def set_exit_on_fail(self, exit_on_fail):
        self.exit_on_fail = exit_on_fail
    
    def clear_fail_count(self):
        self.fail_count = 0
    
    def __str__(self):
        s  = "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Host:" + self.host + "\n"
        s += "+" + "Config File:" + self.config_file +"\n"
        s += "+" + "Fail Count" +  str(self.fail_count) +"\n"
        s += "+++++++++++++++++++++++++++++++++++++++++++++++++++++"
        return s
    
    def read_config(self, filepath):
        config_hash = {}
        machines = []
        f = open(filepath, 'r')
        for line in f:
            ### LOOK for the line that is defining a machine description
            re_machine_line = re.compile('^.+\t.+\t.+\t\d+\t.+\t')
            if re_machine_line.match(line):
                machine = {}
                machine_details = line.split("\t")
                machine["hostname"] = machine_details[0]
                machine["distro"] = machine_details[1]
                machine["distro_ver"] = machine_details[2]
                machine["arch"] = machine_details[3]
                machine["source"] = machine_details[4]
                machine["components"] = machine_details[5].strip('[]').split()
                ### ADD the machine to the array of machines
                machines.append(machine)
            re_network = re.compile('NETWORK')
            if re_network.match(line):
                config_hash["network"] = line.strip()
        config_hash["machines"] = machines 
        return config_hash
            
