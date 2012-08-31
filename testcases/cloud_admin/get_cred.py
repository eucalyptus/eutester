#!/usr/bin/python
from eucaops import Eucaops
import argparse
if __name__ == "__main__":
    ## If given command line arguments, use them as test names to launch
    parser = argparse.ArgumentParser(description='Get credentials for a cloud')
    parser.add_argument('--config', default="../input/2b_tested.lst")
    parser.add_argument("--password",default='foobar')
    args = parser.parse_args()
    tester = Eucaops(config_file=args.config, password=args.password)       
