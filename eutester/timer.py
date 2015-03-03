#!/usr/bin/python

import time
import uuid
import random

class TimeUnit:
    def __init__(self):
        self._start = time.time()
        self._elapsed_time = 0

    def end(self):
        self._elapsed_time = time.time() - self._start

    def elapsed(self):
        return self._elapsed_time

class Timer:
    def __init__(self, logfile="/tmp/eutester", debug=False):
        self._timers = {}
        self._log = open(logfile, "a+b")
        self._debug = debug
        if self._debug:
            print("logging elapsed time to: " + logfile)

    def start(self):
        index = "%s" % (uuid.uuid4())
        self._timers[index] = TimeUnit()
        return index

    def end(self, id, msg):
        self._timers[id].end()
        self._log.write(msg + "\tid: %s\t%fms\n" % (id, self._timers[id].elapsed()*1000))
        if self._debug:
            print("elapsed: " + self._timers[id].elapsed()*1000 + "ms")


    def finish(self):
        self._log.close()

