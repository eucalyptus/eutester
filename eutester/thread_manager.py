

__author__ = 'viglesias'

from multiprocessing import Process
from multiprocessing import Queue
import inspect

class ThreadManager():
    def __init__(self):
        self.thread_pool = {}
        self.queue_pool = {}

    def lookup_thread(self, id):
        try:
            return self.thread_pool[id]
        except KeyError,e:
            raise KeyError("Unable to find thread: " + str(id))

    def lookup_queue(self, id):
        try:
            return self.queue_pool[id]
        except KeyError,e:
            raise KeyError("Unable to find queue: " + str(id))

    def run_method_as_thread(self, method, id, *args, **kwargs):
        try:
            self.lookup_thread(id)
        except KeyError:
            pass
        queue = Queue()
        self.queue_pool[id] = queue
        process = Process(target=self.__run_method, args=(method, queue, self.__get_arguments(method,args,kwargs),))
        self.thread_pool[id] = process
        process.start()

    def __run_method(self, method, queue, args):
        try:
            method(**args)
            queue.put(None)
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

    def kill_thread(self, id):
        thread = self.thread_pool[id]
        assert isinstance(thread, Process)
        thread.terminate()
        self.remove_thread(id)

    def remove_thread(self, id):
        del self.thread_pool[id]
        del self.queue_pool[id]

    def wait_for_thread(self, id):
        thread = self.lookup_thread(id)
        thread.join()
        return_value = self.queue_pool[id].get()
        self.remove_thread(id)
        return return_value

