#!/usr/bin/python


DOCUMENTATION = '''
---
module: cr_iam_facts
short_description: list of role/user/group.
description:
    - This module allows the user to list out IAM entity type. Includes support for validating user exists and policy matches . This module has a dependency on python-boto.
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
    name: pwilliams
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

def isPolicyManaged(client,attachedPolicies, policygiven):
    for polc in attachedPolicies:
        pARN = polc['PolicyArn']
        version = client.get_policy(PolicyArn=pARN)['DefaultVersionId']
        definition = client.get_policy_version(PolicyArn=pARN, VersionId=version)
        if definition == policygiven:
            return True
    return False


def cr_iam_role(module,client,name=None,policy=None):
    if name:
        try:
            role = client.get_role(RoleName=name)['Role']
            if policy:
                iPolicies = client.list_role_policies(RoleName=name)['PolicyNames']
                found=False
                for polc in iPolicies:
                    definition = client.get_role_policy(RoleName=name,PolicyName=polc)['PolicyDocument']
                    if definition == policy:
                        found=True
                        break
                if not found:
                    mPolicies = client.list_attached_role_policies(RoleName=name)['AttachedPolicies']
                    found=isPolicyManaged(client,mPolicies,policy)
                if not found:
                    module.fail_json(msg="Policy [ROLE] given NOT FOUND - {0}".format(name))
                    return None
        except Exception as e:
            #module.fail_json(msg="Connection Error - {0}".format(e))
            return None
        return [role]
    else:
        role=client.list_roles()['Roles']
        return role

def cr_iam_user(module,client,name=None,policy=None):
    if name:
        try:
            user = client.get_user( UserName=name)['User']
            if policy:
                iPolicies = client.list_user_policies(UserName=name)['PolicyNames']  #list of strings
                found=False
                for policy in iPolicies:
                    definition = client.get_user_policy(UserName=name,PolicyName=policy)['PolicyDocument']
                    if definition == policy:
                        found=True
                if not found:
                    mPolicies = client.list_attached_user_policies(UserName=name)['AttachedPolicies']  # list of dicts 'PolicyName'#
                    found=isPolicyManaged(mPolicies,policy)
                if not found:
                    module.fail_json(msg="Policy [USER] given NOT FOUND - {0}".format(name))
                    return None
        except Exception as e:
            module.fail_json(msg="getUser Error - {0}".format(e))
            module.fail_json(msg=" yo yo what is name - {0}".format(name))
            return None
        return [user]
    else:
        users=client.list_users()['Users']
        return users

def cr_iam_group(module,client,name=None,policy=None):
    if name:
        try:
            group = client.get_group( GroupName=name)['Group']
            if policy:
                iPolicies = client.list_group_policies(GroupName=name)['PolicyNames']
                found=False
                for policy in iPolicies:
                    definition = client.get_group_policy(GroupName=name,PolicyName=policy)['PolicyDocument']
                    if definition == policy:
                        found=True
                if not found:
                    mPolicies = client.list_attached_group_policies(GroupName=name)['AttachedPolicies']
                    found=isPolicyManaged(mPolicies,policy)
                if not found:
                    module.fail_json(msg="Policy [GROUP] given NOT FOUND - {0}".format(name))
                    return None
        except Exception as e:
            #module.fail_json(msg="Connection Error - {0}".format(e))
            return None
        return [group]
    else:
        groups=client.list_groups()['Groups']
        return groups

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
      name=dict(required=False, default=None),
      iam_type=dict(required=False, default='role', choices=['group','user','role']),
      trust_policy_filepath=dict(default=None, required=False),
      trust_policy=dict(type='dict', default=None, required=False)
      )
    )

    module = AnsibleModule(
      argument_spec=argument_spec,
      supports_check_mode=True,
      mutually_exclusive=[['trust_policy', 'trust_policy_filepath']],
      required_together=[]
    )

    # validate dependencies
    if not HAS_BOTO3:
      module.fail_json(msg='boto3 is required for this module.')
    try:
      region, endpoint, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
      aws_connect_kwargs.update(dict(region=region,
                                     endpoint=endpoint,
                                     conn_type='client',
                                     resource='iam'
                                ))
      choice_map = {
          "group": cr_iam_group,
          "user": cr_iam_user,
          "role": cr_iam_role
      }
      #ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=endpoint, **aws_connect_kwargs)
      client = boto3_conn(module, **aws_connect_kwargs)
    except botocore.exceptions.ClientError as e:
      module.fail_json(msg="Can't authorize connection - {0}".format(e))
    except Exception as e:
      module.fail_json(msg="Connection Error - {0}".format(e))
  # check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

    iam_type = module.params.get('iam_type').lower()
    name = module.params.get('name')
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


    typeList = choice_map.get( iam_type )(module, client, name, trust_policy_doc)

    #has_changed, result = choice_map.get(module.params['state'])(module.params)
    has_changed=False

    module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

