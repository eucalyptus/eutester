from eucaops import Eucaops
if __name__ == '__main__':
    tester = Eucaops( hostname="clc",password="foobar")
    tester.exit_on_fail = 1
    image = tester.get_emi()
    instance = tester.run_instance(image)
    instance.cmdshell()
    instance.terminate()