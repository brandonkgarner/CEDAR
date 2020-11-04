#!/usr/bin/python


DOCUMENTATION = '''
---
module: cr_cloudevent_set
short_description: set cloudwatch trigger for lambdas.
description:
    - This module allows the user to create a lambda trigger from a cloudwatch event. This module has a dependency on python-boto.
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
      - name of cloudwatch event.
    required: true
    default: null
    aliases: []
  state:
    description:
      - Create or remove cloudwatch event
    required: false
    default: present
    choices: [ 'present', 'absent' ]
  target:
    description:
      - encrypt or decrypt, decrypt can only occur if key already exists and was used previously.
    required: false
    default: null
    choices: [ 'encrypt', 'decrypt' ]
  target_data:
    description:
      - data that needs to be encrypted or decrypted. field requires action
    required: false
    default: null
'''

EXAMPLES = '''
- name: list KMS keys
  kms_cd:
    github_auth_key: "..."
    name: "Hello-World"
    description: "This is your first repository"
    private: yes
    has_issues: no
    has_wiki: no
    has_downloads: no
  register: result
- name: Delete that repo 
  github_repo:
    github_auth_key: "..."
    name: "Hello-World"
    state: absent
  register: result
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



def main():
  argument_spec = ec2_argument_spec()
  argument_spec.update(dict(
      name=dict(required=False, default=None),
      region=dict(required=True, default=None),
      aws_access_key=dict(required=True, default=None),
      security_token=dict(required=True, default=None)
      )
  )

  module = AnsibleModule(argument_spec=argument_spec)

  # validate dependencies
  if not HAS_BOTO3:
      module.fail_json(msg='boto3 is required for this module.')
  try:
      region, endpoint, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
      aws_connect_kwargs.update(dict(region=region,
                                     endpoint=endpoint,
                                     conn_type='client',
                                     resource='kms'
                                     ))

      if not region:
          module.fail_json(
              msg="Region must be specified as a parameter, in EC2_REGION or AWS_REGION environment variables or in boto configuration file")
      #ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=endpoint, **aws_connect_kwargs)
      client = boto3_conn(module, **aws_connect_kwargs)
  except (ClientError, e):
      module.fail_json(msg="Can't authorize connection - {0}".format(e))
  except (Exception, e):
      module.fail_json(msg="Connection Error - {0}".format(e))



  #has_changed, result = choice_map.get(module.params['state'])(module.params)
  has_changed=False
  result = client.list_keys()

  module.exit_json(changed=has_changed, meta=result)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

