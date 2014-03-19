# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: vic.iglesias@eucalyptus.com

import time

class RepoUtils:
    def __init__(self, machine, package_manager="yum" ):
        self.package_manager = None
        if package_manager is "yum":
            self.package_manager = Yum(machine)
        if package_manager is "apt":
            self.package_manager = Apt(machine)

class Package:
    name = None
    version = None
    

class PackageManager:
    name = None
    machine = None
    
    def install(self, package):
        raise NotImplementedError("Method not implemented for package manager " + str(self.name))
    
    def upgrade(self, package = None):
        raise NotImplementedError("Method not implemented for package manager " + str(self.name))
    
    def add_repo(self, url, name= None):
        raise NotImplementedError("Method not implemented for package manager " + str(self.name))
        
    def update_repos(self):
        raise NotImplementedError("Method not implemented for package manager " + str(self.name))
    
    def get_package_info(self):
        raise NotImplementedError("Method not implemented for package manager " + str(self.name))
    
    def get_installed_packages(self):
        raise NotImplementedError("Method not implemented for package manager " + str(self.name))
 
class Yum(PackageManager):
    def __init__(self, machine):
        self.machine = machine
        self.name = "yum"
        
    def install(self, package, nogpg=False):
        gpg_flag = ""
        if nogpg:
            gpg_flag = "--nogpg"

        self.machine.sys("yum install -y " + gpg_flag +  " " + package, code=0)
    
    def upgrade(self, package = None, nogpg=False):
        gpg_flag = ""
        if nogpg:
            gpg_flag = "--nogpg"
        if not package:
            package = ""
        self.machine.sys("yum upgrade -y " + gpg_flag +  " " + package, timeout=480)
    
    def add_repo(self, url, name= None):
        if name is None:
            name = "new-repo-" + str(int(time.time()))
        repo_file = "/etc/yum.repos.d/" + name + ".repo"
        self.machine.sys("echo '[%s]' > %s" % (name, repo_file) )
        self.machine.sys("echo 'name=%s' >> %s"  % (name, repo_file)  );
        self.machine.sys("echo 'baseurl=%s' >> %s" % (url, repo_file) )
        self.machine.sys("echo -e 'enabled=1\ngpgcheck=0' >> %s " % repo_file)
        self.update_repos()
        
    def update_repos(self):
        self.machine.sys("yum clean all")
        
class Apt(PackageManager):
    def __init__(self, machine):
        self.machine = machine
        self.name = "apt"
        self.apt_options = "-o Dpkg::Options::='--force-confold' -y --force-yes "
        
    def install(self, package, timeout=300):
        self.machine.sys("export DEBIAN_FRONTEND=noninteractive; apt-get install %s %s" % (self.apt_options, str(package)),
                         timeout=timeout, code=0)
    
    def upgrade(self, package = None):
        if package is None:
            package = ""
        self.machine.sys("export DEBIAN_FRONTEND=noninteractive; apt-get dist-upgrade %s %s " % (self.apt_options, str(package)) )
    
    def add_repo(self, url, name= None):
        if name is None:
            name = "new-repo-" + str(int(time.time()))
        repo_file = "/etc/apt/sources.list.d/" + name
        self.machine.sys("echo %s >> %s " % (url, repo_file) )
        self.update_repos()
    
    def update_repos(self):
        self.machine.sys("apt-get update")
        
        
        
        