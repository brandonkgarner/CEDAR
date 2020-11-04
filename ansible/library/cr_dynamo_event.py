#!/usr/bin/python


DOCUMENTATION = '''
---
module: cr_dynamo_event
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
  TableNaame:
    description:
      - name of dynamo Table.
    required: true
    default: null
    aliases: []
  StreamViewType:
    description:
      - data tied to streams.
    required: true
    default: null
    choices: ["NEW_IMAGE","OLD_IMAGE","NEW_AND_OLD_IMAGES","KEYS_ONLY"]]
  state:
    description:
      -  state of requested result.
    required: true
    default: null
    choices: ['absent','present']]

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

#



def api_exists(module,name, client):
  #client = boto3.client('apigateway')
  api=None
  response = client.get_rest_apis( limit=450 )['items']
  for item in response:
    #module.fail_json(msg="[T] name:'{0}' - '{1}' not found".format(name,item['name']))
    if item['name'].lower() == name.lower():
      api=item
      break
  return api






def cr_update(module, client, table,StreamViewType, Enabled):
    try:
        if Enabled:
            client.update_table(TableName=table,StreamSpecification={ 'StreamEnabled': Enabled,'StreamViewType': StreamViewType})
        else:

            client.update_table(TableName=table,StreamSpecification={ 'StreamEnabled': Enabled})
    except ClientError as e:
        msg=e.response['Error']['Message']
        if 'already' in msg:  # if e.__class__.__name__ == 'ResourceInUseException':
            [table], False
        else:
            module.fail_json(msg="[E] cr_update [{1}] update_table failed - {0}".format(msg,table))

    return [table], True




def main():
  argument_spec = ec2_argument_spec()
  argument_spec.update(dict(
    state=dict(required=True,  choices=['present','absent']),
    TableName=dict(required=True, default=None),
    StreamViewType=dict(required=True,  choices=["NEW_IMAGE","OLD_IMAGE","NEW_AND_OLD_IMAGES","KEYS_ONLY"]),
    Enabled=dict(required=False, default=True, type='bool'),
#Deployment
   
    )
  )

  module = AnsibleModule(  argument_spec=argument_spec,
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
    #resource=None
    #module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
  except botocore.exceptions.ClientError as e:
    module.fail_json(msg="Can't authorize connection - {0}".format(e))
  except Exception as e:
    module.fail_json(msg="Connection Error - {0}".format(e))
# check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

  TableName = module.params.get('TableName')  
  state = module.params.get('state')
  Enabled = module.params.get('Enabled')
  StreamViewType = module.params.get('StreamViewType')

  if isinstance(Enabled, str):
    Enabled = True if Enabled.lower()=="true" else False
  # module.fail_json(msg="[E] [{1}] enabled?? failed - {0}".format(Enabled,StreamViewType))
    
  typeList, changed=cr_update(  module, client, TableName, StreamViewType, Enabled   )

  #has_changed, result = choice_map.get(module.params['state'])(module.params)
  has_changed=changed

  module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

