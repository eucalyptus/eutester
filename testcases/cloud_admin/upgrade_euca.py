#!/usr/bin/python
from eucaops import Eucaops
import re
import httplib
from optparse import OptionParser

def upgrade_nc(machine):
    upgrade_euca(machine)
    machine.sys("service eucalyptus-nc start", timeout = 300)

def upgrade_vb(machine):
    upgrade_euca(machine)
    machine.sys("service eucalyptus-cloud start", timeout = 300)

def upgrade_cc(machine):
    upgrade_euca(machine)
    machine.sys("service eucalyptus-cc start", timeout = 300)

def upgrade_clc(machine):
    upgrade_euca(machine)
    machine.sys("service eucalyptus-cloud start", timeout = 300)

def upgrade_sc(machine):
    upgrade_euca(machine)
    machine.sys("service eucalyptus-cloud start", timeout = 300)
    
def upgrade_ws(machine):
    upgrade_euca(machine)
    machine.sys("service eucalyptus-cloud start", timeout = 300)

def upgrade_euca(machine):
    ubuntu = re.compile("ubuntu", re.IGNORECASE)
    if ubuntu.search(machine.distro):
         machine.sys("apt-get update ", timeout = 300)
         machine.sys("apt-get dist-upgrade -y --force-yes", timeout = 300)
    else:
        update_yum_repos(machine)
        machine.sys("yum update -y --nogpgcheck", timeout = 300)
        
        

def get_repo_url(host='192.168.51.243:5000',
                 repo='repo-euca@git.eucalyptus-systems.com:internal',
                 distro='centos',
                 releasever='5',
                 arch='x86_64',
                 ref='master'
                 ):
    
    path="/genrepo/?distro="+str(distro)+"&releasever="+str(releasever)+"&arch="+str(arch)+"&url="+str(repo)+"&ref="+str(ref)
    url="http://"+str(host)+str(path)
    print "Using:\n\t Host:"+str(host)+"\n\t path:"+str(path)+"\n\t url:"+str(url)

    conn=httplib.HTTPConnection(host)
    conn.request("GET", path)
    res=conn.getresponse()
    newurl=res.read().strip()
    print "Got newurl: "+str(newurl)
    conn.close()
    return newurl

def update_yum_repos(machine,url= None, euca2ools=False, euca=True, enterprise=True, replace=True):
    if url is None:
        url = get_repo_url()
    if enterprise:
        update_enterprise_repo_yum(machine, url, replace=replace)
    if euca:
        update_euca_repo_yum(machine,url, replace=replace)
    if euca2ools:
        update_euca2ools_repo_yum(machine, replace=replace)
    
    
def update_enterprise_repo_yum(machine, url=None, replace=True):
    repos = []
    if url is None:
        url = get_repo_url()
    if replace:
        #repace any existing euca enterprise repos to replace with new info
        repos = machine.sys('grep "\[eucalyptus-enterprise\]" /etc/yum.repos.d/* -l')
        if repos != []:
            for repo in repos:
                machine.sys('rm '+str(repo.strip()))
    repo = "/etc/yum.repos.d/eucalyptus-enterprise.repo"
    text='[eucalyptus-enterprise]\nname=eucalyptus-enterprise\nbaseurl='+str(url)+'\nenabled=1'
    machine.sys('echo -e "'+text+'" > '+ str(repo) )


def update_euca_repo_yum(machine,url=None, replace=True):
    repos = []
    if url is None:
        url = get_repo_url()
    if replace:
        #remove any existing repos with eucalyptus to replace with new info
        repos = machine.sys('grep "\[eucalyptus\]" /etc/yum.repos.d/* -l')
        if repos != []:
            for repo in repos:
                machine.sys('rm '+str(repo.strip()))
    repo = "/etc/yum.repos.d/euca.repo"
    text= '[eucalyptus]\nname=eucalyptus\nbaseurl='+str(url)+'\nenabled=1'
    machine.sys('echo -e "'+str(text)+'" > '+ str(repo) )

    
def update_euca2ools_repo_yum(machine,url="http://mirror.eucalyptus/qa-pkg-storage/qa-euca2ools-pkgbuild/latest-success/phase3/centos/5/x86_64", replace=True):
    if replace:
        #remove any preexisting euca2ools repos to replace with new info
        repos = machine.sys('grep "\[euca2ools\]" /etc/yum.repos.d/* -l')
        if repos != []:
            for repo in repos:
                machine.sys('rm '+str(repo.strip()))
    repo = "/etc/yum.repos.d/euca2ools.repo"
    text='[euca2ools]\nname=euca2ools\nbaseurl='+str(url)+'\nenabled=1'
    machine.sys('echo -e "'+str(text)+'" > '+ str(repo) )


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--url", dest="url", type="string",
                      help="Url to be used for eucalyptus baseurl", default=None)   
    
    parser.add_option("--config", dest="config", type="string",
                      help="Eutester config file to be used", default=None) 
    
    
    (options, args) = parser.parse_args()
     
    if options.config is not None:
        config = options.config
    else:
        config = "2b_tested.lst"
    tester = Eucaops(config_file=config, password="foobar")
    
    
    for machine in tester.get_component_machines("nc"):
        vmware = re.compile("vmware", re.IGNORECASE)
        if not vmware.search(machine.distro):
            upgrade_nc(machine)
        else:
            for machine in tester.get_component_machines("cc"):
                upgrade_vb(machine)
                
    for machine in tester.get_component_machines("sc"):
        upgrade_sc(machine)

    for machine in tester.get_component_machines("cc"):
        upgrade_cc(machine)
   
    for machine in tester.get_component_machines("clc"):
        upgrade_clc(machine)
        
    for machine in tester.get_component_machines("ws"):
        upgrade_ws(machine)
    
       
        
        
        
        