#!/usr/bin/python

import os

def pcmd(cmd):
	print  '\nCOMMAND :' + cmd + '\n'
        os.system(cmd)

f = open('/root/eutester_install_log', 'w')
f.write() 




def main(): 
	cmd="yum -y install python-virtualenv"
	pcmd(cmd)
        value=pcmd(cmd)
        s=str(value)
        f.write() 

        cmd="cd /root/ &&  mkdir virtual_env"
     	pcmd(cmd)

     	cmd="cd /root/ &&  virtualenv virtual_env"
	pcmd(cmd)

	cmd="cd virtual_env/bin && source activate"
	pcmd(cmd)

        cmd="cd /root/ && wget wget http://192.168.51.136/deps/argparse-1.2.1.tar.gz -O argparse.tar.gz && tar -zxvf argparse.tar.gz"
	pcmd(cmd)

	cmd="cd /root/argparse-1.2.1 && python setup.py install"
	pcmd(cmd)

 	cmd="cd /root/ && wget http://192.168.51.136/deps/boto-2.5.2.tar.gz -O boto.tgz && tar -zxvf boto.tgz"
	pcmd(cmd)

	cmd="cd /root/boto-2.5.2 && python setup.py install"
	pcmd(cmd)

	cmd="cd /root/ && yum -y install git gcc python-paramiko python-devel"
	pcmd(cmd)

	cmd="cd /root/ && git clone https://github.com/eucalyptus/eutester.git"
	pcmd(cmd)

	cmd="cd /root/eutester && git checkout testing"
        pcmd(cmd)

	cmd="cd /root/eutester && python ./setup.py install"
        pcmd(cmd)

	cmd="cd /root/ && mkdir testerworkdir"
        pcmd(cmd)

       	cmd="cd virtual_env/bin && source activate"
        pcmd(cmd)

	cmd="cd /root/ && python /root/eutester_set.py"
        pcmd(cmd)

	cmd="cd /root/ && yum install ntp"
        pcmd(cmd)
      	
        cmd="chkconfig ntpd on && service ntpd start && ntpdate -u 0.centos.pool.ntp.org"
        pcmd(cmd)
	        
    # to extract ntp server address from ntp.conf file:  
    # cat /etc/ntp.conf|grep "server 0.*pool.ntp.org" |awk '{print $2}'

        cmd="ntpdate -u 0.centos.pool.ntp.org"
        pcmd(cmd)


	#from eucaops import Eucaops

       	#tester = Eucaops(config_file='../input/2b_tested.lst', password='foobar')


if __name__ == '__main__': 
	main() 



