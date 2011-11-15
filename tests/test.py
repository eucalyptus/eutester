from eutester import Eutester
if __name__ == '__main__':
    clc_session = Eutester( hostname="clc",password="foobar")
    ### ACCESS THE CONNECTION TO EC2
    print clc_session.ec2.get_all_images()
    ### ACCESS THE CONNECTION TO WALRUS
    print clc_session.walrus.get_all_buckets()
    ### ACCESS THE SSH SESSION TO THE CLC
    clc_session.found("free","cached")
    clc_session.connect_euare()
    clc_session.do_exit()
