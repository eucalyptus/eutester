#!/usr/bin/python
#This code prepares eutester environment and outputs install log inlogo and exit code inlogo into two logiles.
#Writing olog the log inlogo and exit code inlogo is executed through python (not shell) calls

import sys
import subprocess


def print_command(shell_command):



    command_string = '\nCOMMAND :' + shell_command + '\n'
    print command_string

    execute_shell_command = subprocess.Popen(shell_command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
    output =  execute_shell_command.stdout.read()
    exit_code = str( execute_shell_command.wait())
    log.write(command_string + output)
    log_short.write(command_string+ 'Exitcode: '+exit_code )
subprocess.call('rm -f install_log.txt', shell=True)
subprocess.call('rm -f install_exit_code.txt', shell=True)

workmain = "/root/" #main working directory

log = open("install_log.txt", "w")
log_short = open("install_exit_code.txt", "w")


def main():



    if (sys.version_info < (2, 6)):
        print "found python version "+str(sys.version_info[0])+"."+str(sys.version_info[1])+ " must use python 2.6 or greater."
        sys.exit()

    shell_command="cd "+ workmain + " ;" +" yum -y install python-setuptools"
    print_command(shell_command)

    shell_command="cd "+ workmain +";"+" easy_install virtualenv"
    print_command(shell_command)

    shell_command="cd "+ workmain +";"+" virtualenv virtual_env"
    print_command(shell_command)

    shell_command="bash -c 'cd "+ workmain +"virtual_env/bin; source activate'"
    #; echo exit code $?; echo prompt $PS1 '"
    print_command(shell_command)


    shell_command="cd "+ workmain +";"+" wget http://argparse.googlecode.com/files/argparse-1.2.1.tar.gz -O argparse.tar.gz && tar -zxvf argparse.tar.gz"
    print_command(shell_command)

    shell_command="cd "+ workmain +"argparse-1.2.1 ; python setup.py install"
    print_command(shell_command)

    shell_command="cd "+ workmain +";"+" easy_install boto==2.5.2"
    print_command(shell_command)

    shell_command="cd "+ workmain +";"+" yum -y install git gcc python-paramiko python-devel"
    print_command(shell_command)

    shell_command="cd "+ workmain +";"+" git clone https://github.com/eucalyptus/eutester.git"
    print_command(shell_command)

    shell_command="cd " + workmain +"eutester ; git checkout testing"
    print_command(shell_command)

    shell_command="cd " + workmain +"eutester ; python ./setup.py install"
    print_command(shell_command)

    shell_command="cd "+ workmain +";"+" mkdir testerworkdir"
    print_command(shell_command)

    shell_command="cd "+ workmain +";"+" yum -y install ntp"
    print_command(shell_command)

    shell_command="chkconfig ntpd on ; service ntpd start && ntpdate -u 0.centos.pool.ntp.org"
    print_command(shell_command)

    # to extract ntp server address logrom ntp.conlog logile:  
    # cat /etc/ntp.conlog|grep "server 0.*pool.ntp.org" |awk '{print $2}'

    shell_command="ntpdate -u 0.centos.pool.ntp.org"
    print_command(shell_command)

    log.close()
    log_short.close()

if __name__ == '__main__':
    main()

