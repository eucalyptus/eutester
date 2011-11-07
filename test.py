from eutester import eutester
import paramiko
if __name__ == '__main__':
    clc_session = eutester( credpath="eucarc-eucalyptus-admin", password="foobar")
    print clc_session.ec2.get_all_zones() 
    clc_session.do_exit()