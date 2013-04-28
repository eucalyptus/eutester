#!/usr/bin/python
import time
from eucaops import Eucaops
from eucaops import CWops
from eutester.eutestcase import EutesterTestCase
from boto.ec2.cloudwatch import Metric
import datetime

class newDimension(dict):
    def __init__(self, name, value):
        self[name] = value

class CloudWatchBasics(EutesterTestCase):
    def __init__(self, extra_args= None):
        self.setuptestcase()
        self.setup_parser()
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)
        self.get_args()
        ### Setup basic eutester object
        if self.args.region:
            self.tester = CWops( credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops(config_file=self.args.config, password=self.args.password, credpath=self.args.credpath)
        self.start_time =  str(int(time.time()))
        self.namespace = 'Namespace-' + self.start_time
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        ### Set up autoscaling config, group and policys
        self.setUpAutoscaling()
        ### How long to wait in seconds for monitoring to populate.
        self.tester.wait_for_monitoring(260)

    def clean_method(self):
        self.tester.cleanup_artifacts()
        self.cleanUpAutoscaling()
        self.tester.delete_keypair(self.keypair)
        self.tester.local('rm ' + self.keypair.name + '.pem')
        pass

    def get_time_window(self, end=None, **kwargs):
        if not end:
            end = datetime.datetime.utcnow()
        start = end - datetime.timedelta(**kwargs)
        return (start,end)

    def print_timeseries_for_graphite(self, timeseries):
            for datapoint in timeseries:
                print 'graph.Namespace-1361426618 ' + str(int(datapoint['Average'])) + ' ' + \
                      str((datapoint['Timestamp'] - datetime.datetime(1970,1,1)).total_seconds())

    def PutDataGetStats(self):
        seconds_to_put_data = 120
        metric_data = 1
        time_string =  str(int(time.time()))
        metric_name = 'Metric-' + time_string
        incrementing = True
        while datetime.datetime.now().second != 0:
            self.tester.debug('Waiting for minute edge')
            self.tester.sleep(1)
        start = datetime.datetime.utcnow()
        for i in xrange(seconds_to_put_data):
            self.tester.put_metric_data(self.namespace, [metric_name],[metric_data])
            if metric_data == 600 or metric_data == 0:
                incrementing = not incrementing
            if incrementing:
                metric_data += 1
            else:
                metric_data -= 1
            self.tester.sleep(1)
        end = start + datetime.timedelta(minutes=2)
        metric = self.tester.list_metrics(namespace=self.namespace)[0]
        assert isinstance(metric,Metric)
        stats_array = metric.query(start_time=start, end_time=end, statistics=self.tester.get_stats_array())
        assert len(stats_array) == 2
        if stats_array[0]['Minimum'] == 1:
            first_sample = stats_array[0]
            second_sample = stats_array[1]
        else:
            second_sample = stats_array[0]
            first_sample = stats_array[1]
        print stats_array

        ###Check sample 1
        assert first_sample['Maximum'] < 60 and first_sample['Minimum'] > 0
        assert first_sample['Average'] < 34 and first_sample['Average'] > 26
        assert first_sample['Sum'] < 1800 and first_sample['Sum'] > 1500
        assert first_sample['SampleCount'] > 50
        ###Check sample 2
        assert second_sample['Maximum'] < 120 and second_sample['Minimum'] > 50
        assert second_sample['Average'] < 90 and second_sample['Average'] > 80
        assert second_sample['Sum'] < 6000 and second_sample['Sum'] > 4600
        assert second_sample['SampleCount'] > 50

        assert first_sample['Average'] < second_sample['Average']
        assert first_sample['Sum'] < second_sample['Sum']
        assert first_sample['Maximum'] < second_sample['Maximum']
        assert first_sample['Minimum'] < second_sample['Minimum']

    def ListMetricsTest(self):
        self.debug('Get Metric list')
        outList = self.tester.list_metrics()
        self.debug('Checking to see if list is populated at all.')
        assert len(outList) > 0
        expectedMetricList = self.tester.get_instance_metrics_array()
        print expectedMetricList
        self.debug('Checking to see if we get all the expected instance metrics.')
        for metric in expectedMetricList :
            assert str(outList).count(metric['name']) > 0
            self.debug('Metric ' + metric['name'])
        self.debug('Make sure all Instance dimensions are listed.')
        found=False
        for metric in outList:
            self.debug(metric.dimensions)
            if str(metric.dimensions).count(self.instanceid) :
                self.debug('Dimension ' + str(metric.dimensions))
                found=True
                break
        assert found
        found=False

        self.debug('Check list_metrics filtering parameters')
        outList = self.tester.list_metrics(namespace='AWS/EC2')
        assert len(outList) > 0
        outList = self.tester.list_metrics(namespace='NonExistent-NameSpace')
        assert len(outList) == 0
        outList = self.tester.list_metrics(metric_name=expectedMetricList.pop()['name'])
        assert len(outList) > 0
        outList = self.tester.list_metrics(metric_name='NonExistent-Metric-Name')
        assert len(outList) == 0
        outList = self.tester.list_metrics(dimensions=newDimension('InstanceId', self.instanceid))
        assert len(outList) > 0
        outList = self.tester.list_metrics(dimensions=newDimension('InstanceId','NonExistent-InstanceId'))
        assert len(outList) == 0
        outList = self.tester.list_metrics(dimensions=newDimension('ImageId', self.image.id))
        assert len(outList) > 0
        outList = self.tester.list_metrics(dimensions=newDimension('ImageId','NonExistent-imageId'))
        assert len(outList) == 0
        outList = self.tester.list_metrics(dimensions=newDimension('InstanceType', self.instance_type))
        assert len(outList) > 0
        outList = self.tester.list_metrics(dimensions=newDimension('InstanceType','NonExistent-InstanceType'))
        assert len(outList) == 0
        outList = self.tester.list_metrics(dimensions=newDimension('AutoScalingGroupName', self.auto_scaling_group_name))
        ### https://eucalyptus.atlassian.net/browse/EUCA-5952
        #assert len(outList) > 0
        outList = self.tester.list_metrics(dimensions=newDimension('AutoScalingGroupName','NonExistent-AutoScalingGroupName'))
        assert len(outList) == 0

    def GetInstanceMetricTest(self):
        ###get_metric_statistics parameters
        period       = 60
        end          = datetime.datetime.utcnow()
        start        = end - datetime.timedelta(minutes=5)
        stats        = self.tester.get_stats_array()
        metricNames  = self.tester.get_instance_metrics_array()
        namespace    = 'AWS/EC2'
        dimension    = newDimension('InstanceId', self.instanceid)

        ###Check to make sure we are getting all metrics and statistics
        for i in range(len(metricNames)):
            for j in range(len(stats)):
                metricName = metricNames[i]['name']
                statisticName = stats[j]
                unitType =  metricNames[i]['unit']
                metrics = self.tester.get_metric_statistics(period, start, end, metricName, namespace, statisticName , dimensions=dimension, unit=unitType)
                ### This assures we are getting all statistics for all Instance metrics.
                assert int(len(metrics)) > 0
                statisticValue = str(metrics[0][statisticName])
                self.debug(metricName + ' : ' + statisticName + '=' + statisticValue + ' ' + unitType)

    def setUpAutoscaling(self):
        ### setup autoscaling variables:
        self.debug('Setting up AutoScaling, running 1 instance')
        self.instance_type = 'm1.small'
        self.image = self.tester.get_emi(root_device_type='instance-store')
        self.launch_config_name='ASConfig'
        self.auto_scaling_group_name ='ASGroup'
        self.exact = 'ExactCapacity'
        self.change = 'ChangeInCapacity'
        self.percent = 'PercentChangeInCapacity'
        self.cleanUpAutoscaling()

        ### create launch configuration
        self.tester.create_launch_config(name= self.launch_config_name,
                                         image_id=self.image.id,
                                         instance_type=self.instance_type,
                                         key_name=self.keypair.name,
                                         security_groups=[self.group.name],
                                         instance_monitoring=True)
        ### create auto scale group
        self.tester.create_as_group(group_name=self.auto_scaling_group_name,
                                    availability_zones=self.tester.get_zones(),
                                    launch_config=self.launch_config_name,
                                    min_size=0,
                                    max_size=5,
                                    desired_capacity=1)
        ### create auto scale policys
        self.tester.create_as_policy(name=self.exact,
                                     adjustment_type=self.exact,
                                     scaling_adjustment=0,
                                     as_name=self.auto_scaling_group_name,
                                     cooldown=0)

        self.tester.create_as_policy(name=self.change,
                                     adjustment_type=self.change,
                                     scaling_adjustment=3,
                                     as_name=self.auto_scaling_group_name,
                                     cooldown=0)

        self.tester.create_as_policy(name=self.percent,
                                     adjustment_type=self.percent,
                                     scaling_adjustment=-50,
                                     as_name=self.auto_scaling_group_name,
                                     cooldown=0)

        ## Wait for the last instance to go to running state.
        state=None
        while not (str(state).endswith('running')):
            self.debug('Waiting for instance to go to running state')
            self.tester.sleep(10)
            self.instanceid = self.tester.get_last_instance_id()
            instance = self.tester.get_instances(idstring=self.instanceid)
            state = instance.pop().state
        self.debug(self.instanceid + ' is now running.')
        ### Get the newly created policies.
        self.policy_exact = self.tester.autoscale.get_all_policies(policy_names=[self.exact])
        self.policy_change = self.tester.autoscale.get_all_policies(policy_names=[self.change])
        self.policy_percent = self.tester.autoscale.get_all_policies(policy_names=[self.percent])
        self.debug('AutoScaling setup Complete')

    def cleanUpAutoscaling(self):
        self.tester.delete_all_alarms()
        self.tester.delete_all_policies()
        self.tester.delete_as_group(names=self.auto_scaling_group_name,force=True)
        self.tester.delete_launch_config(self.launch_config_name)

    def VerifyMetricStatValues(self):
        '''
        TODO: Verify we are getting correct Metric statistic values ????
        '''
        pass

    def GetEbsMetricStats(self):
        '''
        TODO: Will these be in 3.0??
        '''
        pass

    def MetricAlarmsTest(self):
        metric            = 'CPUUtilization'
        comparison        = '>'
        threshold         = 0
        period            = 60
        evaluation_periods= 1
        statistic         = 'Average'
        ### This alarm sets the number of running instances to exactly 0
        alarm_exact = self.tester.metric_alarm( 'exact', metric, comparison, threshold ,period, evaluation_periods, statistic,
                                         description='TEST',
                                         namespace='AWS/EC2',
                                         dimensions=newDimension('InstanceId', self.instanceid),
                                         alarm_actions=self.policy_exact.pop().policy_arn)
        ### This alarm sets the number of running instances to + 3
        alarm_change = self.tester.metric_alarm( 'change', metric, comparison, threshold ,period, evaluation_periods, statistic,
                                         description='TEST',
                                         namespace='AWS/EC2',
                                         dimensions=newDimension('InstanceId', self.instanceid),
                                         alarm_actions=self.policy_change.pop().policy_arn)
        ### This alarm sets the number of running instances to -50
        alarm_percent = self.tester.metric_alarm( 'percent', metric, comparison, threshold ,period, evaluation_periods, statistic,
                                         description='TEST',
                                         namespace='AWS/EC2',
                                         dimensions=newDimension('InstanceId', self.instanceid),
                                         alarm_actions=self.policy_percent.pop().policy_arn)
        ## put all the alrams
        self.tester.put_metric_alarm(alarm_change)
        self.tester.put_metric_alarm(alarm_percent)
        self.tester.put_metric_alarm(alarm_exact)

        ### The number of running instances should equal the desired_capacity for the auto_scaling_group = (1)
        group = self.tester.describe_as_group(names=[self.auto_scaling_group_name]).pop()
        assert len(group.instances) == 1
        self.debug('The number of running ' + self.auto_scaling_group_name + ' instances = 1')
        ### The number of running instances should equal the desired_capacity + scaling_adjustment = (4)
        self.tester.set_alarm_state('change')
        self.tester.sleep(60)
        group = self.tester.describe_as_group(names=[self.auto_scaling_group_name]).pop()
        assert len(group.instances) == 4
        self.debug('Success the number of running ' + self.auto_scaling_group_name + ' instances changed to 4')
        ### The number of running instances should equal the total from the previous scaling_adjustment (4) - 50% = (2)
        self.tester.set_alarm_state('percent')
        self.tester.sleep(60)
        group = self.tester.describe_as_group(names=[self.auto_scaling_group_name]).pop()
        assert len(group.instances) == 2
        self.debug('Success the number of running ' + self.auto_scaling_group_name + ' instances decreased by 50%')
        ### This should terminate all instances in the auto_scaling_group. 
        self.tester.set_alarm_state('exact')
        self.tester.sleep(60)
        group = self.tester.describe_as_group(names=[self.auto_scaling_group_name]).pop()
        assert group.instances == None
        self.debug('Success the number of running ' + self.auto_scaling_group_name + ' instances is exactly 0')
        pass

if __name__ == '__main__':
    testcase = CloudWatchBasics()
    ### Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list  'ListMetricsTest', 'GetInstanceMetricTest', 'MetricAlarmsTest'
    test_list = testcase.args.tests or ['ListMetricsTest','GetInstanceMetricTest','MetricAlarmsTest']
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = [ ]
    for test in test_list:
        unit_list.append( testcase.create_testunit_by_name(test) )

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list,clean_on_exit=False)
    exit(result)