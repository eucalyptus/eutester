import time
from eutester import Eutester
if __name__ == '__main__':
    clc_session = Eutester( password="foobar", hostname="clc" )
    
    imglist = clc_session.sys("export EUSTORE_URL=http://192.168.51.187/eustore/ && eustore-describe-images")
    if imglist[0].find("euca-centos5.3-x86_64")>-1 and imglist[0].find("CentOS 5.3 1.3GB root"):
        clc_session.test_name("found centos 5.3 64 bit image")
    else:
        clc_session.fail("Output of eustore-describe-images doesn't match expected")

    if imglist[1].find("OS:centos") and imglist[1].find("Arch:x86_64") and imglist[1].find("Vers:old"):
        clc_session.test_name("found centos 5.3 64 bit image details")
    else:
        clc_session.fail("Output of eustore-describe-images doesn't match expected")

    if imglist[2].find("euca-debian5-x86_64")>-1 and imglist[2].find("Debian 5 1.3GB root"):
        clc_session.test_name("found debian 5 64 bit image")
    else:
        clc_session.fail("Output of eustore-describe-images doesn't match expected")

    if imglist[3].find("OS:debian") and imglist[3].find("Arch:x86_64") and imglist[3].find("Vers:old"):
        clc_session.test_name("found debian 5 64 bit image details")
    else:
        clc_session.fail("Output of eustore-describe-images doesn't match expected")

    if imglist[4].find("euca-ubuntu-9.04-x86_64")>-1 and imglist[4].find("Ubuntu 9.04 1.3GB root"):
        clc_session.test_name("found ubuntu 9.04 64 bit image")
    else:
        clc_session.fail("Output of eustore-describe-images doesn't match expected")

    if imglist[5].find("OS:centos") and imglist[5].find("Arch:x86_64") and imglist[5].find("Vers:old"):
        clc_session.test_name("found ubuntu 9.04 64 bit image details")
    else:
        clc_session.fail("Output of eustore-describe-images doesn't match expected")

    installret = clc_session.sys(cmd="export EUSTORE_URL=http://192.168.51.187/eustore/ && eustore-install-image -i euca-centos5.3-x86_64 -b eutest -k xen", timeout=600)
    emi = installret[len(installret)-1]  #last line
    emi = emi[emi.find("emi-"):].strip()
    clc_session.test_name("installed image! " + emi)
    for i in [1, 2, 3, 4, 5]:
        emilist = clc_session.ec2.get_all_images(image_ids=[emi])
        if len(emilist):
            clc_session.test_name("emi " + emi + " was found via describe-images!")
            break
        else:
            print clc_session.ec2.get_all_images()
            time.sleep(10)
            if i == 5:
                clc_session.fail("eustore-install-image didn't properly install the image!")
        
    clc_session.do_exit()
