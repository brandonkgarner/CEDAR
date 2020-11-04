#!/usr/bin/python


DOCUMENTATION = '''
---
module: cr_iam_set
short_description: create role/user/group/profile.
description:
    - This module allows the user to create  IAM entity type. Includes support for validating user exists and policy matches . This module has a dependency on python-boto.
version_added: "1.1"
options:
  aws_access_key:
    description:
      - AWS access key id. If not set then the value of the AWS_ACCESS_KEY environment variable is used.
    required: false
    default: null
    aliases: [ 'ec2_access_key', 'access_key' ]
  aws_secret_key:
    description:
      - AWS secret key. If not set then the value of the AWS_SECRET_KEY environment variable is used.
    required: false
    default: null
    aliases: ['ec2_secret_key', 'secret_key']
  name:
    description:
      - name of User/Role/Group.
    required: false
    default: null
    aliases: []
  iam_type:
    description:
      - type of User/Role/Group.
    required: true
    default: null
    choices: ['user','role','group']
  trust_policy:
    description:
      - policy for entity.
    required: false
    default: null
    type: 'dict'
  trust_policy_filepath:
    description:
      - policy file.
    required: false
    default: null
'''

EXAMPLES = '''
- name: check IAM user exists
  cr_iam_facts:
    name: swilliams
    iam_type: user
    trust_policy_filepath: filepath/file.json
    aws_access_key: "{{ access }}"
    aws_secret_key: "{{ secret }}"
    security_token: "{{ token }}"
    region: "{{project.region}}"
- name: list IAM users
  cr_iam_facts:
    iam_type: role
    aws_access_key: "{{ access }}"
    aws_secret_key: "{{ secret }}"
    security_token: "{{ token }}"
    region: "{{project.region}}"
- name: list IAM groups
  cr_iam_facts:
    iam_type: group
    aws_access_key: "{{ access }}"
    aws_secret_key: "{{ secret }}"
    security_token: "{{ token }}"
    region: "{{project.region}}"
'''

from collections import defaultdict

try:
  import boto3
  from botocore.exceptions import ClientError, MissingParametersError, ParamValidationError
  HAS_BOTO3 = True

  from botocore.client import Config
except ImportError:
  import boto
  HAS_BOTO3 = False

def isPolicyManaged(attachedPolicies, policygiven):
  pass


def cr_iam_role(state,module,client,name=None, resource=None,policy=None, actionPolicyNames=[], description=''):
  pName = name
  found=True
  try:
    irole = client.create_role(RoleName=pName, AssumeRolePolicyDocument=policy)['Role']
    found=False
  except ClientError as e:
    if "already exists" in e.response['Error']['Message']:
      found=True
    else:
      module.fail_json(msg=" [E] Role CREATION failed for [cr_iam_role] - {0}".format(e.response['Error']['Message']))
    

  policy_list = client.list_role_policies(RoleName=pName)['PolicyNames']
  if not actionPolicyNames in policy_list and len(actionPolicyNames) >0:
    for ap in actionPolicyNames:
      cr_iam_attach_policy(module,client, pName, resource, ap, 'role')
    found=False

  return [pName], False if found else True



#create a policy given actionPolicy object
def cr_iam_policy(state,module,client,name=None, resource=None, actionPolicy=None, description=None):
  pName = name
  found=True
  try:
    ipolicy = client.create_policy(PolicyName=pName,  PolicyDocument=actionPolicy, Description=description)
    found=False
  except ClientError as e:
    if "already exists" in e.response['Error']['Message']:
      found=True
    else:
      module.fail_json(msg=" [E] Role CREATION failed for [cr_iam_role] - {0}".format(e.response['Error']['Message']))
  
  return [pName], False if found else True







def cr_iam_attach_policy(module,client,name=None, resource=None, policyName=None, type_iam='role'):
  pName=name
  allPolicies = listPolicies(client)
  if 'role' in type_iam:
    policyARN=None #LOOP to find policy name that matches
    for plcy in allPolicies:
      if policyName == plcy['PolicyName']:
        policyARN = plcy['Arn']
        break
    if policyARN is None:
      module.fail_json(msg=" [E] Given Policy Not found [cr_iam_attach_policy] check the name - {0}".format(policyName))
    client.attach_role_policy(RoleName=pName, PolicyArn= policyARN)

def listPolicies(client, marker=None):
  if marker is None:
    response = client.list_policies()
  else:
    response = client.list_policies(Marker=marker)
  allPolicies=response['Policies']
  if response['IsTruncated']:
    nMarker=response['Marker']
    allPolicies=allPolicies+listPolicies(client,nMarker)
  return allPolicies


def cr_iam_profile(state,module,client,name=None,resource=None, roleUsed=None):
  #pName = 'tagger_profile-dcs-tagger001'
  pName = name
  lroles=[]
  try:
    iprofile = resource.create_instance_profile(InstanceProfileName=pName)
  except:
    iprofile = client.get_instance_profile(InstanceProfileName=pName)
    lroles = iprofile['InstanceProfile']['Roles']
  #module.fail_json(msg=" cr_iam_profileo - {0}".format(iprofile))
  found = False
  for rIn in lroles:
    if roleUsed in rIn['RoleName']:
      found = True
      break
  if not found:
    client.add_role_to_instance_profile(InstanceProfileName=pName, RoleName=roleUsed)

  #module.fail_json(msg=" cr_iam_profileo - {0}".format(iprofile))
  return [pName], False if found else True

def cr_iam_user(module,client,name=None,policy=None, role=None):
  pass

def cr_iam_group(module,client,name=None,policy=None, role=None):
  pass

def main():
  argument_spec = ec2_argument_spec()
  argument_spec.update(dict(
    name=dict(required=True, default=None),
    iam_type=dict(required=True,  choices=['group','user','role','profile','policy']),
    state=dict(required=True,  choices=['present','absent']),
    description=dict(default=None, required=False),  
    action_policy_labels=dict(required=False, default=None,type='list'),
    action_policy_filepath=dict(default=None, required=False),
    action_policy=dict(type='dict', default=None, required=False),
    trust_policy_filepath=dict(default=None, required=False),
    trust_policy=dict(type='dict', default=None, required=False)
    )
  )

  module = AnsibleModule(
    argument_spec=argument_spec,
    supports_check_mode=True,
    mutually_exclusive=[['trust_policy', 'trust_policy_filepath'],['action_policy','action_policy_filepath']],
    required_together=[]
  )

  # validate dependencies
  if not HAS_BOTO3:
    module.fail_json(msg='boto3 is required for this module.')
  try:
    region, endpoint, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
    aws_connect_kwargs.update(dict(region=region,
                                   endpoint=endpoint,
                                   conn_type='both',
                                   resource='iam'
                              ))
    choice_map = {
        "group": cr_iam_group,
        "user": cr_iam_user,
        "role": cr_iam_role,
        "profile": cr_iam_profile
    }


    #ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=endpoint, **aws_connect_kwargs)
    #module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
    client, resource = boto3_conn(module, **aws_connect_kwargs)
    #resource=None
    #module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
  except botocore.exceptions.ClientError as e:
    module.fail_json(msg="Can't authorize connection - {0}".format(e))
  except Exception as e:
    module.fail_json(msg="Connection Error - {0}".format(e))
# check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

  iam_type = module.params.get('iam_type').lower()
  iam_role=None


  description = module.params.get('description')
  state = module.params.get('state')

  action_policy_labels = module.params.get('action_policy_labels')
  name = module.params.get('name')
  
  action_policy = module.params.get('action_policy')
  action_policy_filepath = module.params.get('action_policy_filepath')
  if action_policy_filepath:
    try:
      with open(action_policy_filepath, 'r') as json_data:
        action_policy_doc = json.dumps(json.load(json_data))
    except Exception as e:
      module.fail_json(msg=str(e) + ': ' + action_policy_filepath)
  elif action_policy:
    try:
      action_policy_doc = json.dumps(action_policy)
    except Exception as e:
      module.fail_json(msg=str(e) + ': ' + action_policy)
  else:
    action_policy_doc = None


  trust_policy = module.params.get('trust_policy')
  trust_policy_filepath = module.params.get('trust_policy_filepath')
  if trust_policy_filepath:
    try:
      with open(trust_policy_filepath, 'r') as json_data:
        trust_policy_doc = json.dumps(json.load(json_data))
    except Exception as e:
      module.fail_json(msg=str(e) + ': ' + trust_policy_filepath)
  elif trust_policy:
    try:
      trust_policy_doc = json.dumps(trust_policy)
    except Exception as e:
      module.fail_json(msg=str(e) + ': ' + trust_policy)
  else:
    trust_policy_doc = None

  #module.fail_json(msg="what is name - {0}".format(name))

  if 'profile' in iam_type:
    iam_role = module.params.get('role')
    typeList, changed = cr_iam_profile(state,module, client, name, resource, iam_role)
  elif 'role' in iam_type:
    typeList, changed=cr_iam_role(state,module,client,name,resource,trust_policy_doc,  action_policy_labels, description  )
  elif 'policy' in iam_type: 
    typeList, changed=cr_iam_policy(state,module,client,name,resource,action_policy_doc, description)

  else:
    module.fail_json(msg="Sorry  {0} not yet implemented".format(iam_type))
    typeList, changed = choice_map.get( iam_type )(module, client, name, trust_policy_doc, iam_role)

  #has_changed, result = choice_map.get(module.params['state'])(module.params)
  has_changed=changed

  module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

