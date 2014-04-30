# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: vic.iglesias@eucalyptus.com

from eutester.eutestcase import EutesterTestCase
from multiprocessing import Process
from multiprocessing import Queue
import inspect
import uuid

class ProcessManager():
    def __init__(self):
        self.process_pool = {}
        self.queue_pool = {}

    def lookup_process(self, id):
        try:
            return self.process_pool[id]
        except KeyError,e:
            raise KeyError("Unable to find thread: " + str(id))

    def lookup_queue(self, id):
        try:
            return self.queue_pool[id]
        except KeyError,e:
            raise KeyError("Unable to find queue: " + str(id))

    def run_method_as_process(self, method, *args, **kwargs):
        methvars = EutesterTestCase.get_meth_arg_names(method)
        daemonize = False
        if 'daemonize' in kwargs:
            if 'daemonize' in methvars:
                daemonize = kwargs['daemonize']
            else:
                daemonize = kwargs.pop('daemonize')
        queue = Queue()
        id = uuid.uuid1().hex
        self.queue_pool[id] = queue
        process = Process(target=self.__run_method, args=(method, queue, self.__get_arguments(method,args,kwargs),))
        self.process_pool[id] = process
        process.daemon = daemonize
        process.start()
        return id

    def __run_method(self, method, queue, args):
        try:
            queue.put(method(**args))
        except Exception, e:
            queue.put(e)
            raise e

    def __get_arguments(self, func, args, kwargs):
        """
        Given a function and a set of arguments, return a dictionary of
        argument values that will be sent to the function.
        """
        arguments = {}
        spec = inspect.getargspec(func)
        if spec.defaults:
            arguments.update(zip(reversed(spec.args), reversed(spec.defaults)))
        if spec.keywords:
            arguments.update(spec.keywords)
        arguments.update(zip(spec.args, args))
        arguments.update(kwargs)
        return arguments

    def kill_process(self, id):
        thread = self.process_pool[id]
        assert isinstance(thread, Process)
        thread.terminate()
        self.remove_process(id)

    def remove_process(self, id):
        del self.process_pool[id]
        del self.queue_pool[id]

    def wait_for_process(self, id):
        process = self.lookup_process(id)
        process.join()
        return_value = self.queue_pool[id].get()
        self.remove_process(id)
        return return_value

    def get_all_results(self):
        result_list = []
        for process in self.process_pool:
                result_list.append(self.wait_for_process(process))
        return result_list

