#!/usr/bin/python


DOCUMENTATION = '''
---
module: cr_api_model
short_description: create/update api gateway as needed.
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
  name:
    description:
      - name of api gateway Model.
    required: true
    default: null
    aliases: []
  restApiId:
    description:
      - id of api tree in api gateway.
    required: true
    default: null
  state:
    description:
      - id of api tree in api gateway.
    required: true
    default: null
    choices: ['absent','present']]
  apiName:
    description:
      - NAME of api tree in api gateway.
    required: false
    default: null

'''

EXAMPLES = '''
- name: delete Model
  cr_api_model:
    name: X
    status: absent
    restApiId: 0000000000
    aws_access_key: "{{ access }}"
    aws_secret_key: "{{ secret }}"
    security_token: "{{ token }}"
    region: "{{project.region}}"
- name: add/update Model
  cr_api_model:
    name: X
    apiName: xx
    status: present
    restApiId: 0000000000
    schema: '{\n  "type" : "string",\n  "enum" : [ "dog", "cat", "fish", "bird", "gecko" ]\n}'
    contentType: application/json
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

def layer_version_exists(module,client, name, version):
    response = client.list_layer_versions(LayerName=name)['LayerVersions']
    found=False
    for item in response:
        if version == item['Version']:
            found=True
            break
    return found

def layer_exists(module,name,version, client):
  #client = boto3.client('apigateway')
  layer=None
  response = client.list_layers( limit=450 )['Layers']
  for item in response:
    #module.fail_json(msg="[T] name:'{0}' - '{1}' not found".format(name,item['name']))
    if item['LayerName'].lower() == name.lower():
        found = layer_version_exists(module,client,name,version)
        if found:
          layer=item
          break
  return layer


def describe_Allmodels(self, client,restApiId, position=None):
  rlist=[]
  if position is None:
    response = client.get_models( restApiId=restApiId, limit=500)
  else:
    response = client.get_models( restApiId=restApiId,position=position, limit=500)
  baseList=response['items']
  if "position" in response :
    rlist=self.describe_models(client, restApiId, response['position'])
  models = baseList+rlist
  return models

def cr_destroy( module, client, name,version   ):
  if restApiId is None:
    layerValid=layer_exists(module,name, version, client)
  found=False
  try:
    response=client.delete_layer_version(LayerName=name,VersionNumber=version)
  except ClientError as e: 
    found=True
    name="%s, delete not possible "%name
  return [name], False if found else True



def cr_LayerUpdate(  module, client, name, version,runtimes, description, license, zip_file   ):
  found=True
  layerValid=layer_exists(module,name, version, client)
  if not layerValid:
      try:
        # content=
        response = client.publish_layer_version(LayerName=name,  Description=description,  Content=content,  
                         CompatibleRuntimes=runtimes,  LicenseInfo=license )
        found=False
      except ClientError as e:
        msg=e.response['Error']['Message']
        module.fail_json(msg="[E] cr_LayerUpdate [{1}] update_layer failed - {0}".format(msg,name))

  return [name], False if found else True


def cr_model(  module, client, name, contentType,restApiName, restApiId, schema, description   ):
  if restApiId is None:
    restApiId=api_exists(module,restApiName, client)['id']
  #module.fail_json(msg="[YIO] cr_modelllll - {0}".format(restApiId))
  found=True
  try:
    #schemaOld = json.loads(schema)
    #schemaNewer=json.loads(schemaNewer)

    #sTESTing=json.loads(schema)

    #stest='{  "type": "object", "properties": { "firstProperty" : { "type": "object", "properties": { "key": { "type": "string" } } } } }'
    #module.fail_json(msg="[YIO][{0}] -{1}-  OR -- {2}--".format(type,stest, schemaNewer))

    #schemaString = json.dumps(schema)
    schemaString = json.dumps(schema, sort_keys=True, indent=4, separators=(',', ': '))
    toReplace="%s_id"%(restApiName)
    if toReplace in schemaString:
      schemaNewer=schemaString.replace(toReplace, restApiId)
    else:
      schemaNewer=schemaString


    #module.fail_json(msg="[YIO][{0}]".format(schemaNewer))
    #schemaNewer.update({"$schema":"http://json-schema.org/draft-04/schema#"})
    #schemaNewer.update({"title": name})
    intDict={
      "name":name,
      "restApiId":restApiId,
      "schema": schemaNewer,
      "contentType":contentType

    }
    if description:
      intDict.update({"description":description})

    response=client.create_model(**intDict)
    found=False
  except ClientError as e: 
    msg=e.response['Error']['Message']
    if "Invalid model specified" in msg:
      module.fail_json(msg="[E] MISSING model reference in [{1}]  (NOT FOUND) create_model failed - {0}".format( msg,name))
    if "Model name already exists":
      return cr_modelUpdate(  module, client, name, contentType,restApiName, restApiId, schema, description   )
    else:
      module.fail_json(msg="[E] cr_model [{1}] create_model failed - {0}".format( msg,name))

  return [name], False if found else True



def main():
  argument_spec = ec2_argument_spec()
  argument_spec.update(dict(
    name=dict(required=True, default=None),           ##name of the API
    state=dict(required=True,  choices=['present','absent']),
    version=dict(required=False, default=None),
    runtimes=dict(required=True, default=None),
    license=dict(required=True, default=None),
    zip_file=dict(required=True, default=None),
    description=dict(default=None, required=False),
   
    )
  )


  module = AnsibleModule(  argument_spec=argument_spec,
                            supports_check_mode=True,
                            mutually_exclusive=[],  required_together=[]
  )

  # validate dependencies
  if not HAS_BOTO3:
    module.fail_json(msg='boto3 is required for this module.')
  try:
    region, endpoint, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
    aws_connect_kwargs.update(dict(region=region,
                                   endpoint=endpoint,
                                   conn_type='client',
                                   resource='lambda'
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

  name = module.params.get('name')
  version = module.params.get('version') )
  state = module.params.get('state')


  if 'absent' in state:
    typeList, changed=cr_destroy(module, client, name,version  )
  else:
    runtimes = module.params.get('runtimes')
    description = module.params.get('description')
    license = module.params.get('license')
    zip_file = module.params.get('zip_file'
    typeList, changed=cr_LayerUpdate(  module, client, name, version,runtimes, description, license, zip_file    )

  #has_changed, result = choice_map.get(module.params['state'])(module.params)
  has_changed=changed

  module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

