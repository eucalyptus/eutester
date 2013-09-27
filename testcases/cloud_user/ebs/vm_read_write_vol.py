#!/usr/bin/python

import time, sys
import optparse
import os
import select

parser = optparse.OptionParser(prog='write_volume.py', description='write data to file to verify data integrity')
parser.add_option('-f', dest='testfile', help="file to read", default="/root/testfile")
parser.add_option('-b', dest='bytes', help="bytes to write", default=1000)
parser.add_option('-t', dest='timed_run', help="Number of seconds to run this script, 0 will run forever", default=0)

(args, stuff) = parser.parse_args()
bytes = int(args.bytes)
testfile = args.testfile
timed_run = int(args.timed_run)
readrate = "0"
writerate = "0"
lr = ""
timeout = 2
procfile = "/proc/sys/vm/drop_caches"
print "Starting read/write test, bytes:" + str(bytes) + ", file:" + str(testfile)
time.sleep(1)
f = open(testfile, 'w')
start = time.time()
elapsed = 0
time_remaining = timed_run - elapsed
try:
    while ( timed_run == 0 or time_remaining > 0 ):
        elapsed = time.time() - start
        time_remaining = int(timed_run - elapsed)
        wlength = 0
        start = time.time()
        for x in xrange(0, bytes):
            debug_string = "\nWRITE_VALUE: ".ljust(15) + str(x).ljust(15) + "\n" + \
                           "WRITE_RATE: ".ljust(15) + writerate.ljust(15) + " Bytes/Sec" + "\n" + \
                           "LAST_READ: ".ljust(15) + str(lr).ljust(15) + "\n" + \
                           "READ_RATE: ".ljust(15) + str(readrate + " Bytes/Sec").rjust(15) + "\n" + \
                           "TIME_REMAINING: ".ljust(15) + str(time_remaining)
            #print "\r\x1b[K Writing:" + str(x) + ", Rate:" + writerate + " bytes/sec, Lastread:" \
            #      + str(lr) + ", READ Rate:" + readrate + " bytes/sec",
            print "\r\x1b[K " + debug_string,
            sys.stdout.flush()
            xstr = x, x, x, x, x, x, x, x, x, x, x, x, x, x, x, x, x, x, x, x, x
            xstr = str(xstr).lstrip('(').rstrip(')') + "\n"
            f.write(xstr)
            wlength += len(str(xstr))
            if x and not x % 1:
                f.flush()
                os.fsync(f.fileno())
                time.sleep(.001)
                elapsed = time.time() - start
                writerate = str("%.2f" % (wlength / elapsed))
            f.flush()
            os.fsync(f.fileno())
        elapsed = time.time() - start
        writerate = str("%.2f" % (wlength / elapsed))
        elapsed = time.time() - start
        f.close()
        #Now do the read
        readin = ''
        leftover = ''
        length = 0
        last = 0
        proc = open(procfile, 'w')
        proc.write('3')
        proc.flush()
        proc.close()
        #f = os.open(testfile, os.O_DIRECT | os.O_RD)
        f = open(testfile, 'r')
        readstart = start = time.time()
        while True:
            reads, _, _ = select.select([f.fileno()], [], [], 0)
            elapsed = int(time.time() - start)
            if elapsed >= timeout:
                raise Exception("Could not read from file in timeout:" + str(elapsed))
            time.sleep(.1)
            if len(reads) > 0:
                start = time.time()
                readin = f.read(1024)
                if not readin:
                    break
                while readin:
                    if not readin:
                        break
                    length += len(readin)
                    readin = leftover + readin
                    #add any data not contained within a complete newline from last read() to this cycle...
                    leftover = readin.endswith('\n')
                    lines = readin.splitlines()
                    #if our last line wasn't a complete new line,save it for next read cycle...
                    if not leftover:
                        leftover = lines.pop()
                    for x in lines:
                        #print "\r\x1b[K Reading:" + str(x) + ",",
                        sys.stdout.flush()
                        cur = int(x.split(',')[0])
                        lr = str(cur)
                        if cur != 0 and cur != (last + 1):
                            raise Exception('bad incremented in value, last:' + str(last) + " vs cur:" + str(cur))
                        last = cur
                        cur = 0
                    readin = f.read(1024)
        if length != wlength:
            raise Exception(
                "Read length:" + str(length) + " != written length:" + str(wlength) + ",Diff:" + str(length - wlength))
        elapsed = time.time() - start
        readrate = str("%.2f" % (length / elapsed))
        rbuf = '\n\nREAD Rate:' + readrate + " bytes/sec\n\n"
        f.close()
        f = open(testfile, 'w')
finally:
    f.close()
