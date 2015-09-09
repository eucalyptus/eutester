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
    def __init__(self, extra_args=None):
        self.setuptestcase()
        self.setup_parser()
        self.parser.add_argument('--clean_on_exit',
                                 action='store_true', default=True,
                                 help='Boolean, used to flag whether to run clean up method after running test list)')
        if extra_args:
            for arg in extra_args:
                self.parser.add_argument(arg)

        self.get_args()
        # ## Setup basic eutester object
        if self.args.region:
            self.tester = CWops(credpath=self.args.credpath, region=self.args.region)
        else:
            self.tester = Eucaops(config_file=self.args.config, password=self.args.password,
                                  credpath=self.args.credpath)
        self.start_time = str(int(time.time()))
        self.zone = self.tester.get_zones()
        self.namespace = 'Namespace-' + self.start_time
        self.keypair = self.tester.add_keypair()
        self.group = self.tester.add_group()
        ### Setup AutoScaling
        self.setUpAutoscaling()
        ### Create Dimensions used in tests
        self.instanceDimension = newDimension('InstanceId', self.instanceid)
        self.volumeDimension = newDimension('VolumeId', self.volume.id)
        self.autoScalingDimension = newDimension('AutoScalingGroupName', self.auto_scaling_group_name)
        ### Setup Alarms
        self.setUpAlarms()
        ### Wait for metrics to populate, timeout 30 minute
        self.tester.wait_for_result(self.IsMetricsListPopulated, result=True, timeout=1800)


    def clean_method(self):
        self.cleanUpAutoscaling()
        self.tester.cleanup_artifacts()
        self.tester.delete_keypair(self.keypair)
        pass

    def get_time_window(self, end=None, **kwargs):
        if not end:
            end = datetime.datetime.utcnow()
        start = end - datetime.timedelta(**kwargs)
        return (start, end)

    def print_timeseries_for_graphite(self, timeseries):
        for datapoint in timeseries:
            print 'graph.Namespace-1361426618 ' + str(int(datapoint['Average'])) + ' ' + \
                  str((datapoint['Timestamp'] - datetime.datetime(1970, 1, 1)).total_seconds())

    def PutDataGetStats(self):
        assert self.testAwsReservedNamspaces()
        seconds_to_put_data = 120
        metric_data = 1
        time_string = str(int(time.time()))
        metric_name = "Metric-" + time_string
        incrementing = True
        while datetime.datetime.now().second != 0:
            self.tester.debug("Waiting for minute edge")
            self.tester.sleep(1)
        start = datetime.datetime.utcnow() - datetime.timedelta(seconds=seconds_to_put_data)
        for i in xrange(seconds_to_put_data):
            timestamp = start + datetime.timedelta(seconds=i)
            self.tester.debug(
                "Adding metric: {metric} to namespace: {namespace} with value {value} at {timestamp}".format(
                    metric=metric_name, namespace=self.namespace, value=metric_data, timestamp=timestamp))
            self.tester.cw.put_metric_data(self.namespace, [metric_name], [metric_data], timestamp=timestamp)
            if metric_data == 600 or metric_data == 0:
                incrementing = not incrementing
            if incrementing:
                metric_data += 1
            else:
                metric_data -= 1
        end = start + datetime.timedelta(seconds=seconds_to_put_data)

        def isMatricsAvailable():
            metrics = self.tester.cw.list_metrics(namespace=self.namespace)
            if not metrics:
                return False
            else:
                return True

        self.tester.wait_for_result(isMatricsAvailable, True, timeout=900, poll_wait=300)

        metric = self.tester.cw.list_metrics(namespace=self.namespace)[0]
        assert isinstance(metric, Metric)
        stats_array = metric.query(start_time=start, end_time=end,
                                   statistics=['Average', 'Sum', 'Maximum', 'Minimum', 'SampleCount'])
        assert len(stats_array) == 2
        if stats_array[0]['Minimum'] == 1:
            first_sample = stats_array[0]
            second_sample = stats_array[1]
        else:
            second_sample = stats_array[0]
            first_sample = stats_array[1]
        print stats_array

        # #Check sample 1
        assert first_sample['Maximum'] <= 60 and first_sample['Minimum'] > 0
        assert first_sample['Average'] < 34 and first_sample['Average'] > 26
        assert first_sample['Sum'] < 1900 and first_sample['Sum'] > 1500
        assert first_sample['SampleCount'] > 50
        ##Check sample 2
        assert second_sample['Maximum'] <= 120 and second_sample['Minimum'] > 50
        assert second_sample['Average'] < 95 and second_sample['Average'] > 80
        assert second_sample['Sum'] < 6100 and second_sample['Sum'] > 4600
        assert second_sample['SampleCount'] > 50

        assert first_sample['Average'] < second_sample['Average']
        assert first_sample['Sum'] < second_sample['Sum']
        assert first_sample['Maximum'] < second_sample['Maximum']
        assert first_sample['Minimum'] < second_sample['Minimum']

    def ListMetrics(self, metricNames, dimension):
        self.debug('Get Metric list')
        metricList = self.tester.list_metrics(dimensions=dimension)
        self.debug('Checking to see if list is populated at all.')
        assert len(metricList) > 0
        self.debug('Make sure dimensions are listed.')
        found = False
        for metric in metricList:
            self.debug(metric.dimensions)
            if str(metric.dimensions).count(dimension[dimension.keys().pop()]):
                self.debug('Dimension ' + dimension[dimension.keys().pop()])
                found = True
                break
        assert found
        self.debug('Checking to see if we get all the expected instance metrics.')
        for metric in metricNames:
            assert str(metricList).count(metric['name']) > 0
            self.debug('Metric ' + metric['name'])
        pass

    def checkMetricFilters(self):
        self.debug('Check list_metrics filtering parameters')
        metricList = self.tester.list_metrics(namespace='AWS/EC2')
        assert len(metricList) > 0
        metricList = self.tester.list_metrics(namespace='AWS/EBS')
        assert len(metricList) > 0
        metricList = self.tester.list_metrics(namespace='NonExistent-NameSpace')
        assert len(metricList) == 0
        metricList = self.tester.list_metrics(metric_name='CPUUtilization')
        assert len(metricList) > 0
        metricList = self.tester.list_metrics(metric_name='NonExistent-Metric-Name')
        assert len(metricList) == 0
        metricList = self.tester.list_metrics(dimensions=self.instanceDimension)
        assert len(metricList) > 0
        metricList = self.tester.list_metrics(dimensions=newDimension('InstanceId', 'NonExistent-InstanceId'))
        assert len(metricList) == 0
        metricList = self.tester.list_metrics(dimensions=self.volumeDimension)
        assert len(metricList) > 0
        metricList = self.tester.list_metrics(dimensions=newDimension('VolumeId', 'NonExistent-VolumeId'))
        assert len(metricList) == 0
        metricList = self.tester.list_metrics(dimensions=newDimension('ImageId', self.image.id))
        assert len(metricList) > 0
        metricList = self.tester.list_metrics(dimensions=newDimension('ImageId', 'NonExistent-imageId'))
        assert len(metricList) == 0
        metricList = self.tester.list_metrics(dimensions=newDimension('InstanceType', self.instance_type))
        assert len(metricList) > 0
        metricList = self.tester.list_metrics(dimensions=newDimension('InstanceType', 'NonExistent-InstanceType'))
        assert len(metricList) == 0
        metricList = self.tester.list_metrics(dimensions=self.autoScalingDimension)
        assert len(metricList) > 0
        metricList = self.tester.list_metrics(
            dimensions=newDimension('AutoScalingGroupName', 'NonExistent-AutoScalingGroupName'))
        assert len(metricList) == 0
        metricList = self.tester.list_metrics(dimensions=self.volumeDimension)
        assert len(metricList) > 0
        metricList = self.tester.list_metrics(dimensions=newDimension('VolumeId', 'NonExistent-VolumeId'))
        assert len(metricList) == 0
        pass

    def IsMetricsListPopulated(self):
        end = datetime.datetime.utcnow()
        start = end - datetime.timedelta(minutes=20)
        metrics1 = self.tester.cw.get_metric_statistics(60, start, end, 'CPUUtilization', 'AWS/EC2', 'Average',
                                                        dimensions=self.instanceDimension, unit='Percent')
        metrics2 = self.tester.cw.get_metric_statistics(60, start, end, 'VolumeReadBytes', 'AWS/EBS', 'Average',
                                                        dimensions=self.volumeDimension, unit='Bytes')
        if len(metrics1) > 0 and len(metrics2) > 0:
            return True
        else:
            return False

    def GetMetricStatistics(self, metricNames, namespace, dimension):
        period = 60
        end = datetime.datetime.utcnow()
        start = end - datetime.timedelta(minutes=20)
        stats = self.tester.get_stats_array()
        # ##Check to make sure we are getting all namespace metrics and statistics
        for i in range(len(metricNames)):
            values = []
            for j in range(len(stats)):
                metricName = metricNames[i]['name']
                statisticName = stats[j]
                unitType = metricNames[i]['unit']
                metrics = self.tester.get_metric_statistics(period, start, end, metricName, namespace, statisticName,
                                                            dimensions=dimension, unit=unitType)
                ### This assures we are getting all statistics for all dimension metrics.
                assert int(len(metrics)) > 0
                statisticValue = str(metrics[0][statisticName])
                self.debug(metricName + ' : ' + statisticName + '=' + statisticValue + ' ' + unitType)
                values.append(statisticValue)
        self.tester.validateStats(values)

    def setUpAutoscaling(self):
        # ## setup autoscaling variables:s
        self.debug('Setting up AutoScaling, starting 1 instance')
        self.instance_type = 'm1.small'
        self.image = self.tester.get_emi(root_device_type='instance-store')
        self.launch_config_name = 'ASConfig'
        self.auto_scaling_group_name = 'ASGroup'
        self.exact = 'ExactCapacity'
        self.change = 'ChangeInCapacity'
        self.percent = 'PercentChangeInCapacity'
        self.cleanUpAutoscaling()
        diskWrite = 'while [ 1 ];do dd if=/dev/zero of=/root/testFile bs=1M count=1; done &'
        diskRead = 'while [ 1 ];do dd if=/root/testFile of=/dev/null bs=1M count=1; done &'
        ### create launch configuration
        self.tester.create_launch_config(name=self.launch_config_name,
                                         image_id=self.image.id,
                                         instance_type=self.instance_type,
                                         key_name=self.keypair.name,
                                         security_groups=[self.group.name],
                                         instance_monitoring=True,
                                         user_data=diskWrite + ' ' + diskRead)
        ### create auto scale group
        self.tester.create_as_group(group_name=self.auto_scaling_group_name,
                                    availability_zones=self.zone,
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
                                     scaling_adjustment=1,
                                     as_name=self.auto_scaling_group_name,
                                     cooldown=0)

        self.tester.create_as_policy(name=self.percent,
                                     adjustment_type=self.percent,
                                     scaling_adjustment=-50,
                                     as_name=self.auto_scaling_group_name,
                                     cooldown=0)

        ## Wait for the instance to go to running state.
        self.tester.wait_for_result(self.tester.wait_for_instances, True, timeout=600,
                                    group_name=self.auto_scaling_group_name)
        self.instanceid = self.tester.get_last_instance_id()
        instance_list = self.tester.get_instances(idstring=self.instanceid)
        self.instance = instance_list.pop()
        self.debug('ASG is now setup.')
        ### Create and attach a volume
        self.volume = self.tester.create_volume(self.zone.pop())
        self.tester.attach_volume(self.instance, self.volume, '/dev/sdf')
        ### Get the newly created policies.
        self.policy_exact = self.tester.autoscale.get_all_policies(policy_names=[self.exact])
        self.policy_change = self.tester.autoscale.get_all_policies(policy_names=[self.change])
        self.policy_percent = self.tester.autoscale.get_all_policies(policy_names=[self.percent])
        self.debug('AutoScaling setup Complete')

    def cleanUpAutoscaling(self):
        self.tester.delete_all_alarms()
        self.tester.delete_all_policies()
        self.tester.delete_as_group(name=self.auto_scaling_group_name, force=True)
        self.tester.delete_launch_config(self.launch_config_name)

    def isInService(self):
        group = self.tester.describe_as_group(name=self.auto_scaling_group_name)
        allInService = True
        for instance in group.instances:
            if not str(instance.lifecycle_state).endswith('InService'):
                allInService = False
                break
        return allInService

    def setUpAlarms(self):
        metric = 'CPUUtilization'
        comparison = '>'
        threshold = 0
        period = 60
        evaluation_periods = 1
        statistic = 'Average'
        # ## This alarm sets the number of running instances to exactly 0
        alarm_exact = self.tester.metric_alarm('exact', metric, comparison, threshold, period, evaluation_periods,
                                               statistic,
                                               description='TEST',
                                               namespace='AWS/EC2',
                                               dimensions=self.instanceDimension,
                                               alarm_actions=self.policy_exact.pop().policy_arn)
        ### This alarm sets the number of running instances to + 1
        alarm_change = self.tester.metric_alarm('change', metric, comparison, threshold, period, evaluation_periods,
                                                statistic,
                                                description='TEST',
                                                namespace='AWS/EC2',
                                                dimensions=self.instanceDimension,
                                                alarm_actions=self.policy_change.pop().policy_arn)
        ### This alarm sets the number of running instances to -50%
        alarm_percent = self.tester.metric_alarm('percent', metric, comparison, threshold, period, evaluation_periods,
                                                 statistic,
                                                 description='TEST',
                                                 namespace='AWS/EC2',
                                                 dimensions=self.instanceDimension,
                                                 alarm_actions=self.policy_percent.pop().policy_arn)
        ### put all the alarms
        self.tester.put_metric_alarm(alarm_change)
        self.tester.put_metric_alarm(alarm_percent)
        self.tester.put_metric_alarm(alarm_exact)

    def testDesribeAlarms(self):
        self.debug(self.tester.describe_alarms())
        assert len(self.tester.describe_alarms()) >= 3
        # ## test describe_alarms_for_metric for created alarms
        assert len(
            self.tester.describe_alarms_for_metric('CPUUtilization', 'AWS/EC2', dimensions=self.instanceDimension)) == 3
        ### There are not be any alarms created for 'DiskReadOps'
        assert len(
            self.tester.describe_alarms_for_metric('DiskReadOps', 'AWS/EC2', dimensions=self.instanceDimension)) == 0
        ### test describe_alarm_history
        self.debug(self.tester.describe_alarm_history())
        assert len(self.tester.describe_alarm_history()) >= 3
        pass

    def testAlarms(self):
        # ## The number of running instances should equal the desired_capacity for the auto_scaling_group = (1)
        group = self.tester.describe_as_group(name=self.auto_scaling_group_name)
        assert len(group.instances) == 1
        ### The number of running instances should still be 1 with 'exact' disabled
        self.tester.disable_alarm_actions('exact')
        self.tester.set_alarm_state('exact')
        self.tester.sleep(15)
        group = self.tester.describe_as_group(name=self.auto_scaling_group_name)
        assert len(group.instances) == 1
        self.tester.enable_alarm_actions('exact')
        self.debug('The number of running ' + self.auto_scaling_group_name + ' instances = 1')
        ### The number of running instances should equal the desired_capacity + scaling_adjustment = (2)
        self.tester.set_alarm_state('change')
        self.tester.sleep(15)
        self.tester.wait_for_result(self.isInService, result=True, timeout=240)
        group = self.tester.describe_as_group(name=self.auto_scaling_group_name)
        self.debug(len(group.instances))
        assert len(group.instances) == 2
        self.debug('Success the number of running ' + self.auto_scaling_group_name + ' instances changed to 2')
        ### The number of running instances should equal the total from the previous scaling_adjustment (2) - 50% = (1)
        self.tester.set_alarm_state('percent')
        self.tester.sleep(15)
        group = self.tester.describe_as_group(name=self.auto_scaling_group_name)
        assert len(group.instances) == 1
        self.debug('Success the number of running ' + self.auto_scaling_group_name + ' instances decreased by 50%')
        ### This should terminate all instances in the auto_scaling_group. 
        self.tester.set_alarm_state('exact')
        self.tester.sleep(15)
        group = self.tester.describe_as_group(name=self.auto_scaling_group_name)
        assert group.instances == None
        self.debug('Success the number of running ' + self.auto_scaling_group_name + ' instances is exactly 0')
        pass

    def testAwsReservedNamspaces(self):
        try:
            self.tester.put_metric_data('AWS/AnyName', 'TestMetricName', 1)
        except Exception, e:
            if str(e).count('The value AWS/ for parameter Namespace is invalid.'):
                self.tester.debug('testAwsReservedNamspaces generated expected InvalidParameterValue error.')
                return True
        self.tester.debug('testAwsReservedNamspaces did not throw expected InvalidParameterValue error.')
        return False

    def MonitorInstancesTest(self):
        self.reservation = self.tester.run_instance(keypair=self.keypair.name, zone=self.zone, group=self.group,
                                                    is_reachable=False)
        instanceid = self.tester.get_last_instance_id()
        # ## Enable Monitoring
        self.tester.monitor_instances([instanceid])
        instance = self.tester.get_instances(idstring=instanceid).pop()
        assert instance.monitored
        ### Disble Monitoring
        self.tester.unmonitor_instances([instanceid])
        instance = self.tester.get_instances(idstring=instanceid).pop()
        assert not instance.monitored
        self.tester.terminate_single_instance(instance)

    def MetricAlarmsTest(self):
        # # Describe Alarms/History with and without Filters
        self.testDesribeAlarms()
        ## Test alarm actions
        self.testAlarms()
        pass

    def ListMetricsTest(self):
        # ## List instance metrics
        self.ListMetrics(self.tester.get_instance_metrics_array(), self.instanceDimension)
        ### List EBS Metrics
        self.ListMetrics(self.tester.get_ebs_metrics_array(), self.volumeDimension)
        ### List EBS/Instance metrics with filters
        self.checkMetricFilters()
        pass

    def GetMetricStatisticsTest(self):
        # ## tests EBS metrics
        self.GetMetricStatistics(self.tester.get_ebs_metrics_array(), 'AWS/EBS', self.volumeDimension)
        ### tests instance metrics
        self.GetMetricStatistics(self.tester.get_instance_metrics_array(), 'AWS/EC2', self.instanceDimension)
        pass


if __name__ == '__main__':
    testcase = CloudWatchBasics()
    # ## Use the list of tests passed from config/command line to determine what subset of tests to run
    ### or use a predefined list  'PutDataGetStats', 'ListMetricsTest', 'GetMetricStatisticsTest', 'MetricAlarmsTest', 'MonitorInstancesTest'
    test_list = testcase.args.tests or ['PutDataGetStats', 'ListMetricsTest', 'GetMetricStatisticsTest',
                                        'MetricAlarmsTest', 'MonitorInstancesTest']
    ### Convert test suite methods to EutesterUnitTest objects
    unit_list = []
    for test in test_list:
        unit_list.append(testcase.create_testunit_by_name(test))

    ### Run the EutesterUnitTest objects
    result = testcase.run_test_case_list(unit_list, clean_on_exit=testcase.args.clean_on_exit)
    exit(result)
