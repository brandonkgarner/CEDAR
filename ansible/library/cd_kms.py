#!/usr/bin/python


DOCUMENTATION = '''
---
module: kms_cd
short_description: manage crypto using KMS.
description:
    - This module allows the user to manage keys in KMS. Includes support for creating and deleting keys, retrieving keys . This module has a dependency on python-boto.
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
      - name of KMS key.
    required: true
    default: null
    aliases: []
  state:
    description:
      - Create or remove keys
    required: false
    default: present
    choices: [ 'present', 'absent' ]
  action:
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
- name: Create a KMS key
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




def kms_present(data):
  client = boto3.client('kms' region_name=data['region'])
  has_changed=False
  meta = {"status": result1}
  return True, False, meta

def kms_decrypt(data):
  kms = boto3.client('kms', region_name=data['region'])
  return kms.decrypt(CiphertextBlob=b64decode(data['cypher_key']))['Plaintext']
  meta ={"status":}

def kms_encrypt(data):
  client = boto3.client('kms' region_name=data['region'])
  has_changed=False
  response = client.encrypt(
      KeyId='alias/efax',
      Plaintext=data['key'],
      EncryptionContext={
          'string': 'string'
      }
    )
  meta = {"status": result1}
  return True, False, meta

def kms_absent(data=None):
  has_changed=False
  meta = {"present": "not yet implemented"}


def main():
  argument_spec = ec2_argument_spec()
  argument_spec.update(dict(
      state=dict(default='present', required=False, choices=['present', 'absent']),
      name=dict(required=True, default=None),
      rest_api_id=dict(required=True,  default=None, aliases=['api_id']),
      swagger_spec=dict(required=True, default=None, aliases=['oai_spec']),
      deploy=dict(type='bool', required=False, default=None),
      stage_name=dict(required=False, default=None),
      api_resource_limit=dict(type='int', required=False, default=300),
      rest_api_limit=dict(type='int', required=False, default=60)
      )
  )


  # fields = {
  # 	"name": {"required": True, "type":"str"},
  # 	"region": {"required": True, "type":"str"},
  # 	"state": {
  # 		"default": "present",
  # 		"choices": ['present', 'absent', 'encrypt'],
  # 		"type": 'str'

  # 	}
  # }
  choice_map={
      "present": kms_present,
      "encrypt": kms_encrypt,
      "absent": kms_absent
  }
  module = AnsibleModule(
      argument_spec=argument_spec,
      supports_check_mode=True,
      mutually_exclusive=[],
      required_together=[['action', 'target_data']]
  )

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

      client = boto3_conn(module, **aws_connect_kwargs)
      boto3_conn(module,)
  except (ClientError, e):
      module.fail_json(msg="Can't authorize connection - {0}".format(e))
  except (Exception, e):
      module.fail_json(msg="Connection Error - {0}".format(e))



  has_changed, result = choice_map.get(module.params['state'])(module.params)
  module.exit_json(changed=has_changed, meta=result)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

