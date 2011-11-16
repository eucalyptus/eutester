from eutester import Eutester
if __name__ == '__main__':
    tester2 = Eutester( hostname="clc",password="foobar")
    #tester2 = Eutester( credpath="eucarc-eucalyptus-admin")
    ### ACCESS THE CONNECTION TO EC2
    print tester2.ec2.get_all_images()
    tester2.logger.debug("Testing the logger")
    ### ACCESS THE CONNECTION TO WALRUS
    #print clc_session.walrus.get_all_buckets()
    ### ACCESS THE SSH SESSION TO THE CLC
    #clc_session.found("free","cached")
    #clc_session.connect_euare()
    #clc_session.do_exit()
