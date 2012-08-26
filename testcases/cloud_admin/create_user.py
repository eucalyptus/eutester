#!/usr/bin/python
from eucaops import Eucaops
import argparse
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Create users and accounts with appropriate IAM permissions to use S3 and EC2')
    parser.add_argument('--credpath', required=True)
    parser.add_argument("--account-number", type=int, default=1)
    parser.add_argument("--user-number", type=int, default=1)
    parser.add_argument("--account-prefix", default="test-acc-")
    parser.add_argument("--user-prefix", default="test-user-")
    parser.add_argument("--group-prefix", default="test-group-")
    args = parser.parse_args()
    tester = Eucaops(credpath=args.credpath)
    allow_all_policy = """{
          "Statement": [
            {
             "Action": "ec2:*",
              "Effect": "Allow",
              "Resource": "*"
            },
         {
              "Action": "s3:*",
              "Effect": "Allow",
              "Resource": "*"
            }
          ]
    }"""
    
    for i in xrange(args.account_number):
        account_name = args.account_prefix + str(i)
        group_name = args.group_prefix + str(i)
        tester.create_account(account_name)
        tester.create_group(group_name, "/",account_name)
        tester.attach_policy_group(group_name,"allow-all", allow_all_policy, account_name)
        for k in xrange(args.user_number):
            user_name = args.user_prefix + str(k)
            tester.create_user(user_name, "/", account_name)
            tester.add_user_to_group(group_name, user_name, account_name)
        
        
    