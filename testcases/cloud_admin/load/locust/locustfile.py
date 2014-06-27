import time
from eucaops import Eucaops
from locust import Locust, events, web
import user_profiles

@web.app.route("/added_page")
def my_added_page():
    return "Another page"


class EucaopsClient(Eucaops):
    def __init__(self, *args, **kwargs):
        """
        This class extends Eucaops in order to provide a feedback
        loop to LocustIO. It generates a Eucaops client and fires events
        to the LocustIO when the time_operation wrapper is called with a method
        as its arguments.

        :param args: positional args passed to Eucaops constructor
        :param kwargs: keyword args passed to Eucaops constructor
        """
        super(EucaopsClient, self).__init__(*args, **kwargs)
        self.output_file = open("test-output", "a")
        self.output_file.write('='*10 + " Starting Test " + '='*10 + "\n")

    def time_operation(self, method, *args, **kwargs):
        start_time = time.time()
        output_format = "{0:20} {1:20} {2:20}\n"
        method_name = method.__name__
        try:
            result = method(*args, **kwargs)
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            events.request_failure.fire(request_type="eutester",
                                        name=method_name,
                                        response_time=total_time, exception=e)
            self.output_file.write(output_format.format(method_name, total_time,
                                                        "f"))
        else:
            total_time = int((time.time() - start_time) * 1000)
            try:
                length = len(result)
            except:
                length = 0
            events.request_success.fire(request_type="eutester",
                                        name=method_name,
                                        response_time=total_time,
                                        response_length=length)
            self.output_file.write(output_format.format(method_name, total_time,
                                                        "p"))
            return result


class EucaopsLocust(Locust):
    def __init__(self):
        super(EucaopsLocust, self).__init__()
        self.client = EucaopsClient(credpath="creds")


class EucaopsUser(EucaopsLocust):
    min_wait = 1
    max_wait = 1
    task_set = user_profiles.EC2Read

    def on_start(self):
        pass

    def on_stop(self):
        self.client.cleanup_resources()


