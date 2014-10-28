*** Settings ***
Documentation   Shared setup and teardown routines
Library         eucaops.Eucaops  credpath=${credpath}  config_file=${config_file}  password=${password}
Library         Collections

*** Variables ***
${credpath}     ${None}
${password}     ${None}
${config_file}  ${None}
${image_id}     mi-

*** Keywords ***
Prepare EC2 Resources
  Set Log Level  TRACE
  ${test_id}=  ID generator  ${12}
  ${image}=  get_emi  root_device_type=instance-store  emi=${image_id}
  ${keypair}=  Add Keypair  key_name=${test_id}
  ${group}=  Add Group  group_name=${test_id}
  Authorize Group  ${group}  port=22
  Authorize Group  ${group}  port=-1  protocol=icmp
  @{instances}=  Run Image  image=${image}  keypair=${test_id}  group=${test_id}
  @{zones}=  Get Zones
  ${volume}=  Create Volume  @{zones}[0]
  Set Global Variable  ${image}  ${image}
  Set Global Variable  ${keypair}  ${keypair}
  Set Global Variable  ${group}  ${group}
  Set Global Variable  ${test_id}  ${test_id}
  Set Global Variable  @{zones}  @{zones}
  Set Global Variable  ${volume}  ${volume}
  Set Global Variable  @{instances}  @{instances}
  Set Global Variable  ${instance}  @{instances}[0]

Ping From Instance
  [Arguments]  ${instance}  ${address}
  Should be True  ${instance.sys("ping -c 1 ${address}", code=0)}
