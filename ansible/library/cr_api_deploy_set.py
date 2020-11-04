#!/usr/bin/python


DOCUMENTATION = '''
---
module: cr_apigw_set
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
      - name of User/Role/Group.
    required: false
    default: null
    aliases: []
  apigw_type:
    description:
      - type of User/Role/Group.
    required: true
    default: null
    choices: ['api','resource','method','method_response','integration','integration_response','stage','deployment','key','authorizer','model']]

'''

EXAMPLES = '''
- name: check API exists
  cr_iam_facts:
    name: swilliams
    apigw_type: user
    trust_policy_filepath: filepath/file.json
    aws_access_key: "{{ access }}"
    aws_secret_key: "{{ secret }}"
    security_token: "{{ token }}"
    region: "{{project.region}}"
- name: list API
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



def object_Deploy(name, description, stageDescription, stageName,cacheClusterEnabled, cacheClusterSize, 
  variables, tags, documentationVersion, canarySettings, apiStages, throttle, quota):
  return type('obj', (object,), {
                    "name":name,
                    "description":description,
                    "stageDescription":stageDescription,
                    "stageName":stageName,
                    "cacheClusterEnabled":cacheClusterEnabled,
                    "cacheClusterSize":cacheClusterSize,
                    "variables":variables,
                    "tags":tags,
                    "documentationVersion":documentationVersion,
                    "canarySettings":canarySettings,
                    "resourceId": None,
                    "restApiId": None,
                    "apiStages": apiStages,
                    "throttle": throttle,
                    "quota":quota


                })


def cr_deploy(state,module, client, name, main_dict):
  Test=False
  pName = name
  found=True
  apiFound = api_exists(module,name, client)
  if apiFound is None:
    module.fail_json(msg="[E] cr_deploy API name - {0} not found".format(name))
  restApiId=apiFound["id"]
  deployDict ={
            "restApiId":restApiId,
            "stageName":main_dict.stageName
  }
  if main_dict.stageDescription:
    deployDict.update({'stageDescription': main_dict.stageDescription})
  if main_dict.description:
    deployDict.update({'description': main_dict.description})
  if main_dict.cacheClusterEnabled:
    deployDict.update({'cacheClusterEnabled': main_dict.cacheClusterEnabled})
  if main_dict.cacheClusterSize:
    deployDict.update({'cacheClusterSize': main_dict.cacheClusterSize})
  if main_dict.variables:
    deployDict.update({'variables': main_dict.variables})
  if main_dict.canarySettings:
    deployDict.update({'canarySettings': main_dict.canarySettings})
  try:
    response = client.create_deployment(**deployDict)
    found=False
  except ClientError as e:
    module.fail_json(msg="[E] cr_deploy create_deployment failed - {0}".format(e.response['Error']['Message']))


  return [pName], False if found else True


def cr_domain(state, module, client, name, stageName ):
  pass
def cr_usage(state, module, client, name, stageName ):
  pass
def cr_stage(state, module, client, name, stageName ):
  Test=False
  pName = stageName
  found=True
  apiFound = api_exists(module,name, client)
  if apiFound is None:
    module.fail_json(msg="[E] cr_stage API name - {0} not found".format(name))
  restApiId=apiFound["id"]

  return [pName], False if found else True

def stage_exists(module, stageName ):
  pass



def main():
  argument_spec = ec2_argument_spec()
  argument_spec.update(dict(
    name=dict(required=True, default=None),           ##name of the API
    apigw_type=dict(required=True,  choices=['deployment', 'stage', 'domain', 'usage']),
    state=dict(required=True,  choices=['present','absent']),
    description=dict(default=None, required=False), 
    api_key=dict(required=False, default=None, type='bool'),#Specifies whether the ApiKey can be used by callers
##########################
######### CREATE DEPLOYMENT
##########################
      domain_target=dict(required=False, default=None),
      basePath=dict(required=False, default=None),
#Deployment
    error_path=dict(default=None, required=False),
    restApiId=dict(required=False, default=None),
    stageName=dict(required=True, default=None),
    stageDescription=dict(required=False, default=None),
    cacheClusterEnabled=dict(required=False, default=None, type='bool'),
    cacheClusterSize=dict(required=False,  choices=['0.5','1.6','6.1','13.5','28.4','58.2','118','237']),
    variables=dict(required=False, default=None, type='dict'),
    tags=dict(required=False, default=None, type='dict'),
    canarySettings=dict(required=False, default=None, type='dict'),
    apiStages=dict(required=False, default=None, type='list'),
    throttle=dict(required=False, default=None, type='dict'),
    quota=dict(required=False, default=None, type='dict'),


    deploymentId=dict(required=False, default=None),
    documentationVersion=dict(required=False, default=None),

#Domain configuration
    certificateName=dict(required=False, default=None),
    certificateArn=dict(required=False, default=None),
    regionalCertificateName=dict(required=False, default=None),
    regionalCertificateArn=dict(required=False, default=None),
    endpointConfiguration=dict(required=False, default=None , type='dict'),

     vpc_targetArns=dict(required=False, default=None, type='list'), 




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
                                   resource='apigateway'
                              ))
    choice_map = {
        "deployment": cr_deploy,
        "stage": cr_stage,
        "domain": cr_domain,
        "usage": cr_usage
    }

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
  delta_type = module.params.get('apigw_type')


  description = module.params.get('description')
  state = module.params.get('state')



  if 'stage' in delta_type:                       #** "name" ** is API name. (each env may have diff id)
    typeList, changed = cr_stage(state,module,client,name, description)
  elif 'deployment' in delta_type:
    stageDescription = module.params.get('stageDescription')
    stageName = module.params.get('stageName')
    cacheClusterEnabled = module.params.get('cacheClusterEnabled')
    cacheClusterSize = module.params.get('cacheClusterSize')
    variables = module.params.get('variables')
    tags = module.params.get('tags')
    documentationVersion = module.params.get('documentationVersion')
    canarySettings = module.params.get('canarySettings')
    
    apiStages = module.params.get('apiStages')
    throttle = module.params.get('throttle')
    quota = module.params.get('quota')
    oStructure = object_Deploy(name, description, stageDescription, stageName,cacheClusterEnabled, cacheClusterSize,
                              variables, tags, documentationVersion, canarySettings, apiStages, 
                              throttle, quota)
    typeList, changed=cr_deploy(state,module, client, name, oStructure )
  elif 'usage' in delta_type:
    module.fail_json(msg="Sorry  {0} not yet implemented".format(delta_type))
  else:
    module.fail_json(msg="Sorry  {0} not yet implemented".format(delta_type))
    typeList, changed = choice_map.get( delta_type )(module, client, name, trust_policy_doc, iam_role)

  #has_changed, result = choice_map.get(module.params['state'])(module.params)
  has_changed=changed

  module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()

