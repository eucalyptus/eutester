*** Settings ***
Documentation   EC2 API Tests
Suite Setup     Prepare EC2 Resources
Suite Teardown  Cleanup Artifacts
Resource        shared_keywords.robot

*** Test Cases ***
Check Ephemeral
  Should Not Be True  ${instance.found("ls -1 /dev/vdb", "No such file or directory")}

Ping public IP
  Ping From Instance  ${instance}  ${instance.ip_address}

Ping private IP
  Ping From Instance  ${instance}  ${instance.private_ip_address}

Metadata
  [Template]  Check Metadata
  security-groups  ${group.name}
  instance-id  ${instance.id}
  local-ipv4  ${instance.private_ip_address}
  public-ipv4  ${instance.ip_address}
  ami-id  ${instance.image_id}
  ami-launch-index  ${instance.ami_launch_index}
  placement/availability-zone  ${instance.placement}
  public-hostname  ${instance.public_dns_name}
  local-hostname  ${instance.private_dns_name}
  hostname  ${instance.private_dns_name}
  instance-type  ${instance.instance_type}

DNS Resolution
  [Template]  Check DNS
  ${instance.public_dns_name}  ${instance.private_ip_address}
  ${instance.ip_address}  ${instance.public_dns_name}
  ${instance.private_dns_name}  ${instance.private_ip_address}
  ${instance.private_ip_address}  ${instance.private_dns_name}

Elastic IPs
  ${address}=  Allocate address
  Associate address  ${instance}  ${address}
  Should Be Equal  ${instance.ip_address}  ${address.public_ip}  msg=Instance address is not allocated IP
  Ping  ${instance.ip_address}
  Disassociate address from instance  ${instance}
  Release address  ${address}
  Ping  ${instance.ip_address}

Multiple Instances
  ${multi_instances}=  Run image  ${image}  min=${2}  max=${2}
  Length Should Be  ${multi_instances}  ${2}  msg=Exact number of instances was not not run
  Terminate instances  ${multi_instances}

Invalid Attachments
  [Documentation]  Attach volumes with invalid device strings
  [Template]  Attachment Fails
  /dev/sda
  2323fwqefsdf
  ${volume}
  vdb
  #  /dev/ ### These are allowed for some reason
  #  /root  ### These are allowed for some reason

Valid Attachments
  [Documentation]  Attach with valid device strings
  [Template]  Attachment Works
  /dev/vdc
  /dev/sdc
  vdc
  ## I dont think this should be allowed
  /dev/vdb1

Snapshots
  [Documentation]  Basic snapshot operations
  ${snapshot}=  Create Snapshot From Volume  volume=${volume}  description=${test_id}
  ${volume}=  Create Volume  @{zones}[0]  snapshot=${snapshot}
  @{resource_ids}=  Create List  ${snapshot.id}  ${volume.id}
  ${resource_tags}=  Create Dictionary  Name=${test_id}
  Create Tags  ${resource_ids}  ${resource_tags}
  Delete Snapshot  ${snapshot}
  Delete Volume  ${volume}

*** Keywords ***
Check Metadata
  [Arguments]  ${key}  ${value}
  Should Contain  ${instance.get_metadata("${key}")[0]}  ${value}  msg=Metadata node ${key} was incorrect

Check DNS
  [Arguments]  ${lookup}  ${result}
  Should Be True  ${instance.found("nslookup ${lookup}", "${result}")}  msg=DNS lookup for ${lookup} failed

Attachment Works
  [Arguments]  ${device_path}
  Attach Volume  instance=${instance}  volume=${volume}  device_path=${device_path}
  Detach Volume  volume=${volume}

Attachment Fails
  [Arguments]  ${device_path}
  Run Keyword And Expect Error  *  Attach Volume  instance=@{instances}[0]  volume=${volume}  device_path=${device_path}
