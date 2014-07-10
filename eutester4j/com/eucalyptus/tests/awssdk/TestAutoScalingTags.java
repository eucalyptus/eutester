/*************************************************************************
 * Copyright 2009-2013 Eucalyptus Systems, Inc.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see http://www.gnu.org/licenses/.
 *
 * Please contact Eucalyptus Systems, Inc., 6755 Hollister Ave., Goleta
 * CA 93117, USA or visit http://www.eucalyptus.com/licenses/ if you need
 * additional information or have any questions.
 ************************************************************************/
package com.eucalyptus.tests.awssdk;

import com.amazonaws.services.autoscaling.model.*;
import com.amazonaws.services.ec2.model.DescribeTagsRequest;
import com.amazonaws.services.ec2.model.Filter;
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests tags for auto scaling.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-4758
 */
public class TestAutoScalingTags {

    @Test
    public void AutoScalingTagsTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();
        Boolean hasImageWorker=false;

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Register cleanup for launch config
            final String launchConfig = NAME_PREFIX + "TagTest";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + launchConfig);
                    deleteLaunchConfig(launchConfig);
                }
            });

            // Create launch configuration
            print("Creating launch configuration: " + launchConfig);
            createLaunchConfig(launchConfig, IMAGE_ID, INSTANCE_TYPE, null, null, null, null, null, null, null, null);

            // Register cleanup for auto scaling group
            final String groupName1 = NAME_PREFIX + "TagTest1";
            final String groupName2 = NAME_PREFIX + "TagTest2";
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName1);
                    deleteAutoScalingGroup(groupName1, true);
                    print("Deleting group: " + groupName2);
                    deleteAutoScalingGroup(groupName2, true);
                }
            });

            // Create scaling group
            print("Creating auto scaling group with tags: " + groupName1);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName1)
                    .withLaunchConfigurationName(launchConfig)
                    .withMinSize(0)
                    .withMaxSize(1)
                    .withAvailabilityZones(AVAILABILITY_ZONE)
                    .withTags(
                            new Tag().withKey("tag1").withValue("propagate").withPropagateAtLaunch(Boolean.TRUE),
                            new Tag().withKey("tag2").withValue("don't propagate").withPropagateAtLaunch(Boolean.FALSE)
                    )
            );

            print("Creating auto scaling group without tags: " + groupName2);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName2)
                    .withLaunchConfigurationName(launchConfig)
                    .withMinSize(0)
                    .withMaxSize(1)
                    .withAvailabilityZones(AVAILABILITY_ZONE)
            );

            // Verify tags
            {
                print("Verifying tags when describing group");
                final DescribeAutoScalingGroupsResult describeGroupsResult =
                        as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName1));
                assertThat(describeGroupsResult.getAutoScalingGroups() != null, "Expected groups in result");
                assertThat(describeGroupsResult.getAutoScalingGroups().size() == 1, "Expected one group in result");
                final AutoScalingGroup group = describeGroupsResult.getAutoScalingGroups().get(0);
                assertThat(group != null, "Expected group");
                assertThat(groupName1.equals(group.getAutoScalingGroupName()), "Unexpected group name: " + group.getAutoScalingGroupName());
                assertThat(group.getTags() != null, "Expected tags");
                print("Found tags: " + group.getTags());
                assertThat(group.getTags().size() == 2, "Expected two tags but found " + group.getTags().size());
                assertTag(group.getTags().get(0), "tag1", "propagate", true);
                assertTag(group.getTags().get(1), "tag2", "don't propagate", false);

                print("Verifying tags when describing tags");
                final DescribeTagsResult describeTagsResult = as.describeTags();
                assertThat(describeTagsResult.getTags() != null, "Expected tags");
                print("Found tags: " + describeTagsResult.getTags());

                for (TagDescription tag : describeTagsResult.getTags()){
                    print("tag=" + tag.getKey() + " value=" + tag.getValue());
                    if (tag.getValue().equals("euca-internal-imaging-workers")) hasImageWorker=true;
                }

                if(hasImageWorker){
                    assertThat(describeTagsResult.getTags().size() == 3, "Expected three tags but found " + describeTagsResult.getTags().size());
                } else {
                    assertThat(describeTagsResult.getTags().size() == 2, "Expected two tags but found " + describeTagsResult.getTags().size());
                }

                int tag1Index = "tag1".equals(describeTagsResult.getTags().get(0).getKey()) ? 0 : 1;
                assertTag(describeTagsResult.getTags().get(tag1Index), "tag1", "propagate", true);
                assertTag(describeTagsResult.getTags().get(++tag1Index % 2), "tag2", "don't propagate", false);
            }

            // Delete tags
            as.deleteTags(new DeleteTagsRequest().withTags(
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName1).withKey("tag1").withValue("propagate").withPropagateAtLaunch(Boolean.TRUE),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName1).withKey("tag2").withValue("don't propagate").withPropagateAtLaunch(Boolean.FALSE)
            ));

            // Verify deleted
            {
                print("Verifying no tags when describing group");
                final DescribeAutoScalingGroupsResult describeGroupsResult =
                        as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName1));
                assertThat(describeGroupsResult.getAutoScalingGroups() != null, "Expected groups in result");
                assertThat(describeGroupsResult.getAutoScalingGroups().size() == 1, "Expected one group in result");
                final AutoScalingGroup group = describeGroupsResult.getAutoScalingGroups().get(0);
                assertThat(group != null, "Expected group");
                assertThat(groupName1.equals(group.getAutoScalingGroupName()), "Unexpected group name: " + group.getAutoScalingGroupName());
                assertThat(group.getTags() == null || group.getTags().isEmpty(), "Expected no tags");

                print("Verifying no tags when describing tags");
                final DescribeTagsResult describeTagsResult = as.describeTags();
                if(hasImageWorker){
                    assertThat(describeTagsResult.getTags().size() == 1, "Expected one tag");
                } else {
                    assertThat(describeTagsResult.getTags() == null || describeTagsResult.getTags().isEmpty(), "Expected no tags");

                }
            }

            // Create via API
            as.createOrUpdateTags(new CreateOrUpdateTagsRequest().withTags(
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName1).withKey("tag1").withValue("propagate").withPropagateAtLaunch(Boolean.TRUE),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName1).withKey("tag2").withValue("don't propagate").withPropagateAtLaunch(Boolean.FALSE)
            ));

            // Verify tags
            {
                print("Verifying tags when describing group");
                final DescribeAutoScalingGroupsResult describeGroupsResult =
                        as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName1));
                assertThat(describeGroupsResult.getAutoScalingGroups() != null, "Expected groups in result");
                assertThat(describeGroupsResult.getAutoScalingGroups().size() == 1, "Expected one group in result");
                final AutoScalingGroup group = describeGroupsResult.getAutoScalingGroups().get(0);
                assertThat(group != null, "Expected group");
                assertThat(groupName1.equals(group.getAutoScalingGroupName()), "Unexpected group name: " + group.getAutoScalingGroupName());
                assertThat(group.getTags() != null, "Expected tags");
                print("Found tags: " + group.getTags());
                assertThat(group.getTags().size() == 2, "Expected two tags but found " + group.getTags().size());
                assertTag(group.getTags().get(0), "tag1", "propagate", true);
                assertTag(group.getTags().get(1), "tag2", "don't propagate", false);

                print("Verifying tags when describing tags");
                final DescribeTagsResult describeTagsResult = as.describeTags();
                assertThat(describeTagsResult.getTags() != null, "Expected tags");
                print("Found tags: " + describeTagsResult.getTags());
                if(hasImageWorker){
                    assertThat(describeTagsResult.getTags().size() == 3, "Expected three tags but found " + group.getTags().size());
                } else {
                    assertThat(describeTagsResult.getTags().size() == 2, "Expected two tags but found " + group.getTags().size());

                }
                assertTag(describeTagsResult.getTags().get(0), "tag1", "propagate", true);
                assertTag(describeTagsResult.getTags().get(1), "tag2", "don't propagate", false);
            }

            // Create via API for group 2
            print("Creating tags up to limit for group: " + groupName2);
            as.createOrUpdateTags(new CreateOrUpdateTagsRequest().withTags(
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag01").withValue("1"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag02").withValue("2"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag03").withValue("3"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag04").withValue("4"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag05").withValue("5"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag06").withValue("6"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag07").withValue("7"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag08").withValue("8"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag09").withValue("9"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag10").withValue("10")
            ));

            // Create over limit to test exception
            print("Creating tag over limit for group: " + groupName2);
            try {
                as.createOrUpdateTags(new CreateOrUpdateTagsRequest().withTags(
                        new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag1").withValue("1")
                ));
                assertThat(false, "Expected creation to fail over limit");
            } catch (LimitExceededException e) {
                print("Caught expected exception: " + e);
            }

            // Update via API for group 2
            print("Updating all tags for group: " + groupName2);
            as.createOrUpdateTags(new CreateOrUpdateTagsRequest().withTags(
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag01").withValue("100"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag02").withValue("200"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag03").withValue("300"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag04").withValue("400"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag05").withValue("500"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag06").withValue("600"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag07").withValue("700"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag08").withValue("800"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag09").withValue("900"),
                    new Tag().withResourceType("auto-scaling-group").withResourceId(groupName2).withKey("tag10").withValue("1000").withPropagateAtLaunch(true)
            ));

            // Verify tags updated
            {
                print("Verifying tags when describing group: " + groupName2);
                final DescribeAutoScalingGroupsResult describeGroupsResult =
                        as.describeAutoScalingGroups(new DescribeAutoScalingGroupsRequest().withAutoScalingGroupNames(groupName2));
                assertThat(describeGroupsResult.getAutoScalingGroups() != null, "Expected groups in result");
                assertThat(describeGroupsResult.getAutoScalingGroups().size() == 1, "Expected one group in result");
                final AutoScalingGroup group = describeGroupsResult.getAutoScalingGroups().get(0);
                assertThat(group != null, "Expected group");
                assertThat(groupName2.equals(group.getAutoScalingGroupName()), "Unexpected group name: " + group.getAutoScalingGroupName());
                assertThat(group.getTags() != null, "Expected tags");
                print("Found tags: " + group.getTags());
                assertThat(group.getTags().size() == 10, "Expected ten tags but found " + group.getTags().size());
                assertTag(group.getTags().get(0), "tag01", "100", false);
                assertTag(group.getTags().get(1), "tag02", "200", false);
                assertTag(group.getTags().get(2), "tag03", "300", false);
                assertTag(group.getTags().get(3), "tag04", "400", false);
                assertTag(group.getTags().get(4), "tag05", "500", false);
                assertTag(group.getTags().get(5), "tag06", "600", false);
                assertTag(group.getTags().get(6), "tag07", "700", false);
                assertTag(group.getTags().get(7), "tag08", "800", false);
                assertTag(group.getTags().get(8), "tag09", "900", false);
                assertTag(group.getTags().get(9), "tag10", "1000", true);
            }

            // Launch instance
            print("Launching instance to test tag propagation");
            as.setDesiredCapacity(new SetDesiredCapacityRequest().withAutoScalingGroupName(groupName1).withHonorCooldown(false).withDesiredCapacity(1));
            final String instanceId = (String) waitForInstances(TimeUnit.MINUTES.toMillis(15), 1, groupName1, true).get(0);

            // Verify tag on instance
            final com.amazonaws.services.ec2.model.DescribeTagsResult describeTagsResult =
                    ec2.describeTags(new DescribeTagsRequest().withFilters(
                            new Filter().withName("resource-id").withValues(instanceId),
                            new Filter().withName("resource-type").withValues("instance"),
                            new Filter().withName("key").withValues("tag1"),
                            new Filter().withName("value").withValues("propagate")
                    ));
            assertThat(describeTagsResult.getTags() != null, "Expected tags");
            assertThat(describeTagsResult.getTags().size() == 1, "Expected one tag");

            print("Test complete");
        } finally {
            // Attempt to clean up anything we created
            Collections.reverse(cleanupTasks);
            for (final Runnable cleanupTask : cleanupTasks) {
                try {
                    cleanupTask.run();
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
        }
    }

    private void assertTag(final TagDescription tagDescription,
                           final String key, final String value, final boolean propagate) {
        assertThat(tagDescription != null, "Null tag");
        assertThat(key.equals(tagDescription.getKey()), "Unexpected tag key: "
                + tagDescription.getKey());
        assertThat(value.equals(tagDescription.getValue()),
                "Unexpected tag value: " + tagDescription.getValue());
        assertThat(
                propagate == tagDescription.getPropagateAtLaunch(),
                "Unexpected tag propagation: "
                        + tagDescription.getPropagateAtLaunch());
    }

}
