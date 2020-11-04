#!/usr/bin/python


DOCUMENTATION = '''
---
module: cr_dynamo_stream_facts
short_description: updates dynamo table to have stream data.
description:
    - This module allows the user to create  API GW entity type. Includes support for validating user exists and policy matches . This module has a dependency on python-boto.
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

  triggers:
    description:
      -  all triggers without real event ARN's.
    required: true
    default: null

'''

EXAMPLES = '''
- name: delete Model
  xx_dynamo_event:
    TableName: xx_tablename
    status: absent
    aws_access_key: "{{ access }}"
    aws_secret_key: "{{ secret }}"
    security_token: "{{ token }}"
    region: "{{project.region}}"
- name: add/update Model
  xx_dynamo_event:
    TableName: xx_tablename
    status: present
    StreamViewType: NEW_AND_OLD_IMAGES
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


def cr_define(module, client, triggers, service='dynamodb'):
  for tt in triggers:
    # module.fail_json(msg="[E] {0} :<_>: {1}".format(tt, triggers))

    table = tt['TableName']
    try:
      tdef = client.describe_table(TableName=table)['Table']
      source = tt["source_params"]
      # module.fail_json(msg="[E]  :<_>: {0}".format(tdef))
      source['source_arn'] = tdef['LatestStreamArn']
    except ClientError as e:
      msg = e.response['Error']['Message']
      module.fail_json(msg="[E] cr_define [{1}] map streams failed - {0} ::: {2}".format(msg, name, tt))

  return triggers, True


def main():
  argument_spec = ec2_argument_spec()
  argument_spec.update(dict(
      state=dict(required=False, choices=['present', 'absent']),
      target=dict(required=True, default=None),
      triggers=dict(required=True, default=None, type='list'),

      # Deployment
  )
  )

  module = AnsibleModule(argument_spec=argument_spec,
                         supports_check_mode=True,
                         mutually_exclusive=[],
                         )

  # validate dependencies
  if not HAS_BOTO3:
    module.fail_json(msg='boto3 is required for this module.')
  try:
    region, endpoint, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
    aws_connect_kwargs.update(dict(region=region,
                                   endpoint=endpoint,
                                   conn_type='client',
                                   resource='dynamodb'
                                   ))
    # choice_map = {
    #     "deployment": cr_deploy,
    #     "stage": cr_stage,
    #     "domain": cr_domain,
    #     "usage": cr_usage
    # }

    resource = None
    #ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=endpoint, **aws_connect_kwargs)
    #module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
    client = boto3_conn(module, **aws_connect_kwargs)
    # resource=None
    #module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
  except botocore.exceptions.ClientError as e:
    module.fail_json(msg="Can't authorize connection - {0}".format(e))
  except Exception as e:
    module.fail_json(msg="Connection Error - {0}".format(e))
# check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

  triggers = module.params.get('triggers')
  target = module.params.get('target')

  typeList, changed = cr_define(module, client, triggers, target)

  #has_changed, result = choice_map.get(module.params['state'])(module.params)
  has_changed = changed

  module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
  main()
