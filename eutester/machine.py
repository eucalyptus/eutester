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

import eulogger
import sshconnection
import re

class machine:
    def __init__(self, hostname, distro, distro_ver, arch, source, components, password=None, keypath=None, username="root", timeout=120,retry=2,debugmethod=None):
        self.hostname = hostname
        self.distro = distro
        self.distro_ver = distro_ver
        self.arch = arch
        self.source = source
        self.components = components
        if debugmethod is None:
            logger = eulogger.Eulogger(identifier= str(hostname) + ":" + str(components))
            self.debugmethod = logger.log.debug
        self.ssh = sshconnection.SshConnection(     hostname, 
                                                    keypath=keypath,          
                                                    password=password, 
                                                    username=username, 
                                                    timeout=timeout, 
                                                    retry=retry,
                                                    debugmethod=self.debugmethod,
                                                    verbose=True)
    
        self.sftp = self.ssh.connection.open_sftp()
    
    def update_ssh(self):
        self.update()
        self.ssh = sshconnection.SshConnection(     instance.ip_address, 
                                                    keypair=keypair, 
                                                    keypath=keypath,          
                                                    password=password, 
                                                    username=username, 
                                                    timeout=timeout, 
                                                    retry=retry,
                                                    debugmethod=self.debugmethod,
                                                    verbose=True)
    def debug(self,msg):
        '''
        Used to print debug, defaults to print() but over ridden by self.debugmethod if not None
        msg - mandatory -string, message to be printed
        '''
        if ( self.verbose is True ):
                self.debugmethod(msg)

                
    def sys(self, cmd, verbose=True, timeout=120):
        '''
        Issues a command against the ssh connection to this instance
        Returns a list of the lines from stdout+stderr as a result of the command
        cmd - mandatory - string, the command to be executed 
        verbose - optional - boolean flag to enable debug
        timeout - optional - command timeout in seconds 
        '''
        output = []
        if (self.ssh is not None):
            output = self.ssh.sys(cmd, verbose=verbose, timeout=timeout)
            return output
        else:
            raise Exception("Euinstance ssh connection is None")
    
    def found(self, command, regex):
        """ Returns a Boolean of whether the result of the command contains the regex"""
        result = self.sys(command)
        for line in result:
            found = re.search(regex,line)
            if found:
                return True
        return False                                                
    
    def __str__(self):
        s  = "+++++++++++++++++++++++++++++++++++++++++++++++++++++\n"
        s += "+" + "Hostname:" + self.hostname + "\n"
        s += "+" + "Distro: " + self.distro +"\n"
        s += "+" + "Distro Version: " +  self.distro_ver +"\n"
        s += "+" + "Install Type: " +  self.source +"\n"
        s += "+" + "Components: " +   str(self.components) +"\n"
        s += "+++++++++++++++++++++++++++++++++++++++++++++++++++++"
        return s