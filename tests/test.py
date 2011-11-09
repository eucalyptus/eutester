from eutester import eutester
import time
if __name__ == '__main__':
    clc_session = eutester( credpath="eucarc-eucalyptus-admin", password="foobar")
    clc_session.do_exit()
