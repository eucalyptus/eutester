#!/usr/bin/python

from eucaops import Eucaops
from eutester import eupopulator
import argparse
import os

parser = argparse.ArgumentParser(prog="populate.py",
                                     description="Populate a user with various resources including snapshots,volumes,buckets,keypairs,security groups",
                                     usage="%(prog)s --credpath=<path to creds>")
parser.add_argument('--credpath',
                        help="path to user credentials"
			, required=True)
args = parser.parse_args()

tester = Eucaops(credpath=args.credpath)
pop = eupopulator.EuPopulator(tester)

pop.populate()
pop.serialize_resources(args.credpath.strip("/")  + "-before.dat")
