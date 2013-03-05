#!/usr/bin/python

import time
from eucaops import Eucaops
from eucaops import CWops
from eutester.eutestcase import EutesterTestCase
from boto.ec2.cloudwatch import Metric
import datetime

class CloudWatchBasics(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        # Setup basic eutester object
        if self.args.region:
            self.tester = CWops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops(config_file=self.args.config, password=self.args.password, credpath=self.args.credpath)
        self.start_time =  str(int(time.time()))
        self.namespace = "Namespace-" + self.start_time

    def clean_method(self):
        pass

    def get_time_window(self, end=None, **kwargs):
        if not end:
            end = datetime.datetime.utcnow()
        start = end - datetime.timedelta(**kwargs)
        return (start,end)

    def print_timeseries_for_graphite(timeseries):
            for datapoint in timeseries:
                print "graph.Namespace-1361426618 " + str(int(datapoint['Average'])) + " " + \
                      str((datapoint['Timestamp'] - datetime.datetime(1970,1,1)).total_seconds())

    def PutDataGetStats(self):
        seconds_to_put_data = 120
        metric_data = 1
        time_string =  str(int(time.time()))
        metric_name = "Metric-" + time_string
        incrementing = True
        while datetime.datetime.now().second != 0:
            self.tester.debug("Waiting for minute edge")
            self.tester.sleep(1)
        start = datetime.datetime.utcnow()
        for i in xrange(seconds_to_put_data):
            self.tester.debug("Adding metric: {metric} to namescace: {namespace} with value {value}".format(
                metric=metric_name, namespace = self.namespace, value=metric_data))
            self.tester.cw.put_metric_data(self.namespace, [metric_name],[metric_data])
            if metric_data == 600 or metric_data == 0:
                incrementing = not incrementing
            if incrementing:
                metric_data += 1
            else:
                metric_data -= 1
            self.tester.sleep(1)
        end = start + datetime.timedelta(minutes=2)
        metric = self.tester.cw.list_metrics(namespace=self.namespace)[0]
        assert isinstance(metric,Metric)
        stats_array = metric.query(start_time=start, end_time=end, statistics=['Average', 'Sum', 'Maximum', 'Minimum','SampleCount'] )
        assert len(stats_array) == 2
        if stats_array[0]['Minimum'] == 1:
            first_sample = stats_array[0]
            second_sample = stats_array[1]
        else:
            second_sample = stats_array[0]
            first_sample = stats_array[1]
        print stats_array

        ##Check sample 1
        assert first_sample['Maximum'] < 60 and first_sample['Minimum'] > 0
        assert first_sample['Average'] < 34 and first_sample['Average'] > 26
        assert first_sample['Sum'] < 1800 and first_sample['Sum'] > 1500
        assert first_sample['SampleCount'] > 50
        ##Check sample 2
        assert second_sample['Maximum'] < 120 and second_sample['Minimum'] > 50
        assert second_sample['Average'] < 90 and second_sample['Average'] > 80
        assert second_sample['Sum'] < 6000 and second_sample['Sum'] > 4600
        assert second_sample['SampleCount'] > 50

if __name__ == "__main__":
    testcase = CloudWatchBasics()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list  "VolumeTagging", "InstanceTagging", "SnapshotTagging", "ImageTagging"
    list = testcase.args.tests or ["PutDataGetStats"]
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=True)
    exit(result)
