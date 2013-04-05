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
import org.testng.annotations.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import static com.eucalyptus.tests.awssdk.Eutester4j.*;

/**
 * This application tests filtering for auto scaling tags.
 * <p/>
 * This is verification for the story:
 * <p/>
 * https://eucalyptus.atlassian.net/browse/EUCA-5137
 */
public class TestAutoScalingDescribeTags {


    private void assertTag(TagDescription tag, String groupName, String key, String value, boolean propagate) {
        assertThat("auto-scaling-group".equals(tag.getResourceType()), "Expected group tag");
        assertThat(groupName.equals(tag.getResourceId()), "Expected group name " + groupName);
        assertThat(key.equals(tag.getKey()), "Expected key " + key);
        assertThat(value.equals(tag.getValue()), "Expected value " + value);
        assertThat(Boolean.valueOf(propagate).equals(tag.getPropagateAtLaunch()), "Expected propagate " + propagate);
    }

    @Test
    public void AutoScalingDescribeTagsTest() throws Exception {
        testInfo(this.getClass().getSimpleName());
        getCloudInfo();

        final List<Runnable> cleanupTasks = new ArrayList<Runnable>();
        try {
            // Create launch configuration
            final String configName = NAME_PREFIX + "TagsTest";
            print("Creating launch configuration: " + configName);
            as.createLaunchConfiguration(new CreateLaunchConfigurationRequest()
                    .withLaunchConfigurationName(configName)
                    .withImageId(IMAGE_ID)
                    .withInstanceType(INSTANCE_TYPE));
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting launch configuration: " + configName);
                    deleteLaunchConfig(configName);
                }
            });

            // Create scaling groups
            final String groupName1 = NAME_PREFIX + "TagsTest1";
            print("Creating auto scaling group: " + groupName1);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName1)
                    .withLaunchConfigurationName(configName)
                    .withMinSize(0)
                    .withMaxSize(1)
                    .withAvailabilityZones(AVAILABILITY_ZONE)
                    .withTags(
                            new Tag().withKey("t1").withValue("v1").withPropagateAtLaunch(false),
                            new Tag().withKey("t2").withValue("v2").withPropagateAtLaunch(true)
                    )
            );
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName1);
                    deleteAutoScalingGroup(groupName1,true);
                }
            });

            final String groupName2 = NAME_PREFIX + "TagsTest2";
            print("Creating auto scaling group: " + groupName2);
            as.createAutoScalingGroup(new CreateAutoScalingGroupRequest()
                    .withAutoScalingGroupName(groupName2)
                    .withLaunchConfigurationName(configName)
                    .withMinSize(0)
                    .withMaxSize(1)
                    .withAvailabilityZones(AVAILABILITY_ZONE)
                    .withTags(
                            new Tag().withKey("t1").withValue("v1").withPropagateAtLaunch(false),
                            new Tag().withKey("t2").withValue("v2").withPropagateAtLaunch(true),
                            new Tag().withKey("t3").withValue("v3").withPropagateAtLaunch(false),
                            new Tag().withKey("t4").withValue("v4").withPropagateAtLaunch(true)
                    )
            );
            cleanupTasks.add(new Runnable() {
                @Override
                public void run() {
                    print("Deleting group: " + groupName2);
                    as.deleteAutoScalingGroup(new DeleteAutoScalingGroupRequest().withAutoScalingGroupName(groupName2));
                }
            });

            // No filters, ensure all tags present
            print("Describing tags without filters");
            {
                final DescribeTagsResult tagsResult = as.describeTags();
                assertThat(tagsResult.getTags() != null, "Expected tags");
                assertThat(tagsResult.getTags().size() == 6, "Expected 6 tags");
                assertTag(tagsResult.getTags().get(0), groupName1, "t1", "v1", false);
                assertTag(tagsResult.getTags().get(1), groupName1, "t2", "v2", true);
                assertTag(tagsResult.getTags().get(2), groupName2, "t1", "v1", false);
                assertTag(tagsResult.getTags().get(3), groupName2, "t2", "v2", true);
                assertTag(tagsResult.getTags().get(4), groupName2, "t3", "v3", false);
                assertTag(tagsResult.getTags().get(5), groupName2, "t4", "v4", true);
            }

            // Filter by group name
            print("Describing tags with group name filter");
            {
                final DescribeTagsResult tagsResult = as.describeTags(new DescribeTagsRequest()
                        .withFilters(new Filter().withName("auto-scaling-group").withValues(groupName1)));
                assertThat(tagsResult.getTags() != null, "Expected tags");
                assertThat(tagsResult.getTags().size() == 2, "Expected 2 tags");
                assertTag(tagsResult.getTags().get(0), groupName1, "t1", "v1", false);
                assertTag(tagsResult.getTags().get(1), groupName1, "t2", "v2", true);
            }

            // Filter by group name ( multiple values )
            print("Describing tags with multiple valued group name filter");
            {
                final DescribeTagsResult tagsResult = as.describeTags(new DescribeTagsRequest()
                        .withFilters(new Filter().withName("auto-scaling-group").withValues(groupName1, groupName2)));
                assertThat(tagsResult.getTags() != null, "Expected tags");
                assertThat(tagsResult.getTags().size() == 6, "Expected 6 tags");
                assertTag(tagsResult.getTags().get(0), groupName1, "t1", "v1", false);
                assertTag(tagsResult.getTags().get(1), groupName1, "t2", "v2", true);
                assertTag(tagsResult.getTags().get(2), groupName2, "t1", "v1", false);
                assertTag(tagsResult.getTags().get(3), groupName2, "t2", "v2", true);
                assertTag(tagsResult.getTags().get(4), groupName2, "t3", "v3", false);
                assertTag(tagsResult.getTags().get(5), groupName2, "t4", "v4", true);
            }

            // Filter by key
            print("Describing tags with key filter");
            {
                final DescribeTagsResult tagsResult = as.describeTags(new DescribeTagsRequest()
                        .withFilters(new Filter().withName("key").withValues("t1")));
                assertThat(tagsResult.getTags() != null, "Expected tags");
                assertThat(tagsResult.getTags().size() == 2, "Expected 2 tags");
                assertTag(tagsResult.getTags().get(0), groupName1, "t1", "v1", false);
                assertTag(tagsResult.getTags().get(1), groupName2, "t1", "v1", false);
            }

            // Filter by value
            print("Describing tags with value filter");
            {
                final DescribeTagsResult tagsResult = as.describeTags(new DescribeTagsRequest()
                        .withFilters(new Filter().withName("value").withValues("v4")));
                assertThat(tagsResult.getTags() != null, "Expected tags");
                assertThat(tagsResult.getTags().size() == 1, "Expected 1 tag");
                assertTag(tagsResult.getTags().get(0), groupName2, "t4", "v4", true);
            }

            // Filter using propagate at launch filter (should be case insensitive)
            print("Describing tags with propagate at launch filter");
            {
                final DescribeTagsResult tagsResult = as.describeTags(new DescribeTagsRequest()
                        .withFilters(new Filter().withName("propagate-at-launch").withValues("TruE")));
                assertThat(tagsResult.getTags() != null, "Expected tags");
                assertThat(tagsResult.getTags().size() == 3, "Expected 3 tags");
                assertTag(tagsResult.getTags().get(0), groupName1, "t2", "v2", true);
                assertTag(tagsResult.getTags().get(1), groupName2, "t2", "v2", true);
                assertTag(tagsResult.getTags().get(2), groupName2, "t4", "v4", true);
            }

            // Filter using all filters at once
            print("Describing tags with all filters");
            {
                final DescribeTagsResult tagsResult = as.describeTags(new DescribeTagsRequest().withFilters(
                        new Filter().withName("auto-scaling-group").withValues(groupName2),
                        new Filter().withName("key").withValues("t1", "t2", "t3"),
                        new Filter().withName("value").withValues("v3", "v2"),
                        new Filter().withName("propagate-at-launch").withValues("true", "FALSE")
                ));
                assertThat(tagsResult.getTags() != null, "Expected tags");
                assertThat(tagsResult.getTags().size() == 2, "Expected 2 tags");
                assertTag(tagsResult.getTags().get(0), groupName2, "t2", "v2", true);
                assertTag(tagsResult.getTags().get(1), groupName2, "t3", "v3", false);
            }

            // Filter using tag that does not match anything.
            print("Describing tags with non-matching filter");
            {
                final DescribeTagsResult tagsResult = as.describeTags(new DescribeTagsRequest()
                        .withFilters(new Filter().withName("key").withValues("DOESNOTMATCH")));
                assertThat(tagsResult.getTags() == null || tagsResult.getTags().isEmpty(), "Expected no tags");
            }

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
}
