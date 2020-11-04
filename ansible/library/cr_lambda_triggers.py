#!/usr/bin/python
# from collections import defaultdict
import os
import datetime
from datetime import datetime as dtime
# import time

DOCUMENTATION = '''
---
module: cr_lambda_triggers
short_description: Creates, updates or deletes AWS Lambda function event mappings.
description:
    - This module allows the management of AWS Lambda function event source mappings such as S3 bucket
      events, DynamoDB and Kinesis streaming events via the Ansible framework.
      It is idempotent and supports "Check" mode.  Use module M(lambda) to manage the lambda
      function itself and M(lambda_alias) to manage function aliases.
version_added: "2.1"
author: Robert Colvin (@rcolvin)
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
    lambda_function_arn:
        description:
          - The name or ARN of the lambda function.
        required: true
        aliases: ['function_name', 'function_arn']
    state:
        description:
          - Describes the desired state and defaults to "present".
        required: true
        default: "present"
        choices: ["present", "absent"]
    alias:
        description:
          - Name of the function alias. Mutually exclusive with C(version).
        required: true
        version:
        description:
          -  Version of the Lambda function. Mutually exclusive with C(alias).
        required: false
    event_source:
        description:
          -  Source of the event that triggers the lambda function.
        required: true
        choices: ['s3', 'Kinesis', 'DynamoDB', 'SNS']
    source_params:
        description:
          -  Sub-parameters required for event source.
          -  I(== S3 event source ==)
          -  C(id) Unique ID for this source event.
          -  C(bucket) Name of source bucket.
          -  C(prefix) Bucket prefix (e.g. images/)
          -  C(suffix) Bucket suffix (e.g. log)
          -  C(events) List of events (e.g. ['s3:ObjectCreated:Put'])
          -  I(== stream event source ==)
          -  C(source_arn) The Amazon Resource Name (ARN) of the Kinesis or DynamoDB stream that is the event source.
          -  C(enabled) Indicates whether AWS Lambda should begin polling the event source. Default is True.
          -  C(batch_size) The largest number of records that AWS Lambda will retrieve from your event source at the
             time of invoking your function. Default is 100.
          -  C(starting_position) The position in the stream where AWS Lambda should start reading.
             Choices are TRIM_HORIZON or LATEST.
          -  I(== SNS event source ==)
          -  C(id) Unique ID for this source event.
          -  C(topic_arn) The ARN of the topic to which you want to subscribe the lambda function.
        required: true
    requirements:
        - boto3
    extends_documentation_fragment:
        - aws

'''

EXAMPLES = '''
- name: update/EXISTS [API RESOURCE] 
    cr_apigw_set:
        apigw_type: "resource"
        name: "{{ item.name }}"                 ##name of the API
        path: "{{ item.path }}"                 ##FULL PATH of resource. use "/" for root
        state: "{{ item.state }}"
    with_items: "{{ project.api_gw }}"
- name: update [API RESOURCE] [METHOD]
    cr_apigw_set:
        apigw_type: "method"
        name: "{{ item.name }}"                 ##name of the API
        path: "{{ item.path }}"
        operationName: "{{ item.operational_name }}"
        requestParameters: "{{ item.request_params }}"
        requestModels: "{{ item.request_models }}"
        responseModels: "{{ item.response_models }}"
        authorizationScopes: "{{ item.auth_scope }}"
        authName: "{{item.authName}}"
        apiKeyRequired: "{{ item.apiKeyRequired }}"
        authorizationType: "{{ item.authorizationType }}"
        httpMethod: "{{ item.httpMethod }}"      ##GET, POST, other...
        state: "{{ item.state }}"
        integration: "{{ item.method_integration }}"
        response: "{{ item.method_response }}"
    with_items: "{{ project.api_gw }}"
'''


try:
    import boto3
    from botocore.exceptions import ClientError, MissingParametersError, ParamValidationError
    HAS_BOTO3 = True

    from botocore.client import Config
except ImportError:
    import boto
    HAS_BOTO3 = False
dir_path = os.path.dirname(__file__)
#


def file_append(path, filename, msg):
    with open("%s/LOG-%s.txt" % (path, filename), "a") as file:
        file.write("\n%s" % (msg))
# create a policy given actionPolicy object


def cr_apigw(state, module, client, name=None, resource=None, actionPolicy=None, description=None):
    pName = name
    found = True

    return [pName], False if found else True


def resource_gen(module, client, pathPart, apiId, pId):
    try:
        resource = client.create_resource(restApiId=apiId, parentId=pId, pathPart=pathPart)
    except ClientError as e:
        module.fail_json(msg="[E] resource_gen failed - {0}".format(e.response['Error']['Message']))
    return resource


def getAllResources(client, restApiId, position=None):
    rlist = []
    if position is None:
        response = client.get_resources(restApiId=restApiId, limit=500)
    else:
        response = client.get_resources(restApiId=restApiId, position=position, limit=500)
    baseList = response['items']
    if "position" in response:
        rlist = getAllResources(client, restApiId, response['position'], prevlist=[])
    final = baseList + rlist
    return final


def cr_dynamo_event(state, module, client, clientstreams, event_source, function_name, source_params):
    found = True
    streams = client.list_event_source_mappings(FunctionName=function_name)['EventSourceMappings']
    targetStream = None
    UUID = None
    eventObj = None
    for stream in streams:
        streamSource = stream['EventSourceArn']
        if event_source in streamSource:
            targetStream = streamSource
            UUID = stream['UUID']
            eventObj = stream
            break

    if state == 'absent':  # delete
        if targetStream:  # already missing  skip
            try:
                client.delete_event_source_mapping(UUID=UUID)
            except ClientError as e:
                module.fail_json(msg="[E] dynamo trigger DELETE failed {0} - {1}".format(event_source, e.response['Error']['Message']))

    else:  # add
        params = eventObjConform(module, source_params)
        enabled = params['enabled']
        batch_size = params['batch_size']
        starting_position = params['starting_position']
        MaximumBatchingWindowInSeconds = params['MaximumBatchingWindowInSeconds']

        ParallelizationFactor = params['ParallelizationFactor']
        DestinationConfig = params['DestinationConfig']

        MaximumRecordAgeInSeconds = params['MaximumRecordAgeInSeconds']
        BisectBatchOnFunctionError = params['BisectBatchOnFunctionError']
        MaximumRetryAttempts = params['MaximumRetryAttempts']

        if not targetStream:
            table = event_source.split("/")[-1]
            targetStream = getTableStream(state, module, clientstreams, table)
        if eventObj:
            if MaximumBatchingWindowInSeconds != eventObj['MaximumBatchingWindowInSeconds']:
                eventObj.update({"MaximumBatchingWindowInSeconds": MaximumBatchingWindowInSeconds})
                found = False
            if BisectBatchOnFunctionError != eventObj['BisectBatchOnFunctionError']:
                eventObj.update({"BisectBatchOnFunctionError": BisectBatchOnFunctionError})
                found = False
            if not found:
                try:
                    client.update_event_source_mapping(**eventObj)
                except ClientError as e:
                    module.fail_json(msg="[E] dynamo trigger DELETE failed {0} - {1}".format(event_source, e.response['Error']['Message']))
        else:
            try:
                if 'StartingPositionTimestamp' in params:
                    StartingPositionTimestamp = params['StartingPositionTimestamp']
                    if StartingPositionTimestamp == 0 or StartingPositionTimestamp == '0':
                        year = dtime.today().year
                        StartingPositionTimestamp = dtime(year, 1, 1)
                    else:
                        StartingPositionTimestamp = dtime.utcfromtimestamp(StartingPositionTimestamp)
                else:
                    year = dtime.today().year
                    StartingPositionTimestamp = dtime(year, 1, 1)
                params_obj = {"EventSourceArn": targetStream, "FunctionName": function_name,
                              "Enabled": enabled, "BatchSize": batch_size,
                              "MaximumBatchingWindowInSeconds": MaximumBatchingWindowInSeconds,
                              "ParallelizationFactor": ParallelizationFactor,
                              "StartingPosition": starting_position,
                              "DestinationConfig": DestinationConfig,
                              "MaximumRecordAgeInSeconds": MaximumRecordAgeInSeconds,
                              "BisectBatchOnFunctionError": BisectBatchOnFunctionError,
                              "MaximumRetryAttempts": MaximumRetryAttempts

                              }
                if starting_position == "AT_TIMESTAMP":
                    params_obj.update({"StartingPositionTimestamp": StartingPositionTimestamp})

                client.create_event_source_mapping(**params_obj)
                found = False
            except ClientError as e:
                module.fail_json(msg="[E] dynamo trigger DELETE failed {0} - {1}".format(event_source, e.response['Error']['Message']))

    return [event_source], False if found else True


def getTableStream(state, module, clientstreams, table):
    # dynoClient = boto3.client("dynamodbstreams")
    streams = clientstreams.list_streams(TableName=table)['Streams']
    for stream in streams:
        return stream['StreamArn']


def eventObjConform(module, source_params):
    params = source_params

    enabled = params['enabled']
    # module.fail_json(msg="[E] dynamo trigger DELETE failed {0} - {1}".format(enabled, params))

    batch_size = int(params['batch_size'])
    starting_position = params['starting_position']
    MaximumBatchingWindowInSeconds = int(params['MaximumBatchingWindowInSeconds'])

    ParallelizationFactor = int(params['ParallelizationFactor'])
    if ParallelizationFactor == 0:
        ParallelizationFactor = 1
    DestinationConfig = params['DestinationConfig']
    if isinstance(DestinationConfig, str):
        DestinationConfig = params['DestinationConfig']
    onfailure = False
    onsuccess = False
    if 'OnFailure' in DestinationConfig:
        if DestinationConfig['OnFailure']:
            onfailure = True
    if 'OnSuccess' in DestinationConfig:
        if DestinationConfig['OnSuccess']:
            onsuccess = True
    if not onsuccess and not onfailure:
        DestinationConfig = {}

    MaximumRecordAgeInSeconds = int(params['MaximumRecordAgeInSeconds'])
    if MaximumRecordAgeInSeconds == 0:
        MaximumRecordAgeInSeconds = 60000
    BisectBatchOnFunctionError = params['BisectBatchOnFunctionError']
    if BisectBatchOnFunctionError == 0 or BisectBatchOnFunctionError == '0':
        BisectBatchOnFunctionError = False
    else:
        BisectBatchOnFunctionError = True
    # module.fail_json(msg="[E] dynamo trigger DELETE failed {0} - {1}".format(BisectBatchOnFunctionError, params))
    MaximumRetryAttempts = int(params['MaximumRetryAttempts'])

    obj = {
        "enabled": enabled,
        "batch_size": batch_size,
        "starting_position": starting_position,
        "MaximumBatchingWindowInSeconds": MaximumBatchingWindowInSeconds,
        "ParallelizationFactor": ParallelizationFactor,
        "DestinationConfig": DestinationConfig,
        "MaximumRecordAgeInSeconds": MaximumRecordAgeInSeconds,
        "BisectBatchOnFunctionError": BisectBatchOnFunctionError,
        "MaximumRetryAttempts": MaximumRetryAttempts
    }
    return obj


def cr_resource(state, module, client, name, path, description):
    found = True
    apiFound = api_exists(module, name, client)
    if apiFound is None:
        module.fail_json(msg="[E] cr_resource API name - {0} not found".format(name))
    restApiId = apiFound["id"]
    # rlist = client.get_resources( restApiId=restApiId, limit=500)['items']
    rlist = getAllResources(client, restApiId)
    # pId = None
    pathPart = path.rsplit('/', 1)[-1]  # users
    parentPath = path.rsplit('/', 1)[-2]
    dictPath = {}
    for rs in rlist:
        parentID = pPart = None
        if 'parentId' in rs:
            parentID = rs['parentId']
        if 'pathPart' in rs:
            pPart = rs['pathPart']
        dictPath.update({rs['path']: {'pid': parentID, 'pathPart': pPart, 'id': rs['id']}})

    if pathPart == "" and pathPart == parentPath:  # root update here so nothing required
        return [path], False if found else True
    if path in dictPath:  # already exists. return without change
        return [path], False if found else True
    if parentPath == "":  # root level so no update as needed
        for k, v in dictPath.items():
            rootPath = k.rsplit('/', 1)[-2]
            if path == rootPath:  # root level CONFIRMED so no update as needed
                # # module.fail_json(msg="[T] cr_resource API - {0} set as".format(found))
                return [path], False if found else True

    # module.fail_json(msg="[T] cr_resource API - {0}===={1}===={2}===={3} {4}".format(dictPath,pathPart,parentPath,restApiId, path))

    sPath = path.split("/")
    lastpath = ""
    lastId = dictPath['/']['id']
    attempts = len(sPath)
    found = False
    for n in range(attempts):
        if not sPath[n] == "":
            lastpath = lastpath + "/" + sPath[n]
            if lastpath in dictPath:  # found ..update lastID and continue
                lastId = dictPath[lastpath]['id']
                continue
            rPart = lastpath.rsplit('/', 1)[-1]
            rsrc = resource_gen(module, client, rPart, restApiId, lastId)
            dictPath.update({lastpath: {'pid': lastId, 'pathPart': rPart, 'id': rsrc['id']}})
            lastId = rsrc['id']

    return [path], False if found else True


def getAll_rest_apis(client, position=None):
    rlist = []
    if position is None:
        response = client.get_rest_apis(limit=500)
    else:
        response = client.get_rest_apis(limit=500)
    baseList = response['items']
    if "position" in response:
        rlist = getAll_rest_apis(client, response['position'], prevlist=[])
    final = baseList + rlist
    return final


def api_exists(module, name, client):
    # client = boto3.client('apigateway')
    api = None
    # response = client.get_rest_apis( limit=450 )['items']
    response = getAll_rest_apis(client)
    for item in response:
        if item['name'].lower() == name.lower():
            #module.fail_json(msg="[T] name:'{0}' - '{1}' not found".format(name,item['name']))
            api = item
            break
    return api


def resource_exists(module, path, apiId, client):
    resource = None
    # response = client.get_resources(restApiId=apiId, limit=450 )['items']
    response = getAllResources(client, apiId)
    # comparing=[]
    for item in response:
        # comparing.append("%s == %s"%(path,item['path']))
        if item['path'].lower() == path.lower():
            resource = item
            break
    # module.fail_json(msg="[E] resource_exists API resource[{0}] - {1} ".format(resource, comparing ))
    return resource


def method_exists(module, method, apiId, rId, client):
    oMethod = None
    resource = client.get_resource(restApiId=apiId, resourceId=rId)
    if 'resourceMethods' in resource:
        for key, value in resource['resourceMethods'].items():
            if method.lower() == key.lower():
                # module.fail_json(msg="[E] method_exists API resource[{0}] - {1} ".format(key, resource ))
                oMethod = client.get_method(restApiId=apiId, resourceId=rId, httpMethod=key)
                del oMethod['ResponseMetadata']
                break
    # module.fail_json(msg="[T] method_exists API resource[{0}] {1}".format( method, oMethod))
    return oMethod


def getAll_validators(client, restApiId, position=None):
    rlist = []
    if position is None:
        response = client.get_request_validators(restApiId=restApiId, limit=500)
    else:
        response = client.get_request_validators(restApiId=restApiId, limit=500, position=position)
    baseList = response['items']
    if "position" in response:
        rlist = getAll_validators(client, response['position'], prevlist=[])
    final = baseList + rlist
    return final


def validator_match(client, module, validator, restApiId):
    description = validator['name']
    validBody = validator['validateRequestBody']
    validReqParam = validator['validateRequestParameters']
    items = getAll_validators(client, restApiId)
    # module.fail_json(msg="[T]    validator_match    - {0}  [{1}] {2}".format( items, restApiId , validator))
    Found = None
    if items:
        for item in items:
            if validBody == item['validateRequestBody'] and validReqParam == item['validateRequestParameters'] and description == item['name']:
                return item
    response = client.create_request_validator(restApiId=restApiId,
                                               name=description,
                                               validateRequestBody=validBody,
                                               validateRequestParameters=validReqParam
                                               )
    return response


def getAll_authorizers(client, restApiId, position=None):
    rlist = []
    if position is None:
        response = client.get_authorizers(restApiId=restApiId, limit=500)
    else:
        response = client.get_authorizers(restApiId=restApiId, limit=500, position=position)
    baseList = response['items']
    if "position" in response:
        rlist = getAll_authorizers(client, response['position'], prevlist=[])
    final = baseList + rlist
    return final


def auth_present(client, module, authorizationName, restApiId):
    # items = client.get_authorizers(restApiId=restApiId)['items']
    items = getAll_authorizers(client, restApiId)
    for item in items:
        if authorizationName == item['name']:
            return item
    # module.fail_json(msg="[T]    auth_present    - {0}  [{1}]".format( items, restApiId ))
    # not found so fail
    return None


def model_present(client, module, model, apiId, update=True):
    old = None
    if model is None or not model:
        return old
    for mk, mv in model.items():
        if mv:
            if mv.lower() == "empty":
                return old

    modelName = None
    if 'name' in model:
        modelName = model['name']
    # module.fail_json(msg="[T] model_present models  >>-> {0} ".format( model ) )
    if modelName is None:
        return None
    try:
        old = client.get_model(restApiId=apiId, modelName=modelName, flatten=True)
        if not old['schema'] in model['schema']:
            update = True
        else:
            nModel = old
    except ClientError as e:
        update = True
    if update:
        try:
            if not old is None:
                client.delete_model(restApiId=apiId, modelName=modelName)
            response = client.create_model(restApiId=apiId, name=modelName,
                                           description=model['description'],
                                           schema=model['schema'], contentType=model['contentType']
                                           )
            nModel = response
        except ClientError as e:
            module.fail_json(msg="[E] model_present failed - {0}".format(e.response['Error']['Message']))
    return nModel


def cr_model(state, module, client, name, resource, description, apiId, schema, contentType):
    pName = name
    found = True
    try:
        obj = {'schema': schema, 'name': name, 'description': description, 'contentType': contentType}
        nModel = model_present(client, module, obj, apiId, True)
        found = False
    except ClientError as e:
        module.fail_json(msg="[E] model_present failed - {0}".format(e.response['Error']['Message']))

    return [pName], False if found else True
# isTest is not for Testing but to validate params are correct before CHANGE is made!!!!!
# OTHERWISE YOU WILL LOOSE THE API FOREVER!!!!


def object_Method(name, description, httpMethod, integration, response, path, keyRequired, requestparameters, requestvalidator, authorizationType, authorizationName, requestModels, responseModels, operationName, authScopes, credentials):
    return type('obj', (object,), {
        "name": name,
        "description": description,
        "httpMethod": httpMethod,
        "integration": integration,
        "response": response,
        "path": path,
        "keyRequired": keyRequired,
        "requestparameters": requestparameters,
        "requestvalidator": requestvalidator,
        "authorizationType": authorizationType,
        "authorizationName": authorizationName,
        "requestModels": requestModels,
        "responseModels": responseModels,
        "operationName": operationName,
        "authScopes": authScopes,
        "credentials": credentials
    })


# GET RESOURCE

# CREATE RESOURCE
# CREATE METHOD
# CREATE USAGE PLAN
# CREATE AUTHORIZER
# CREATE DEPLOYMENT
# CREATE MODEL
# CREATE REQUEST VALIDATOR

# .  create_base_path_mapping

# update_gateway_response()
# update_integration()
# update_integration_response()
# update_method()
# update_method_response()

# ADD METHOD. put_method

# WHAT LIMITS ARE ON TOTAL NUMBER OF STAGES
# CREATE STAGE. (*CREATE ONLY ONE annd multiple usage plans PER customer)
# CREATE API KEY (*requires stage to be deployed)

# UPDATE AUTHORIZOR

# TEST INVOKE METHOD


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        # name=dict(required=True, default=None),  # name of the API
        # apigw_type=dict(required=True, choices=['resource', 'method', 'method_response', 'integration', 'integration_response', 'model']),
        state=dict(required=True, choices=['present', 'absent']),
        # type_event=dict(required=True, choices=['s3', 'dynamodb', 'api', 'cloudwatch', 'sns', 'sqs', 'cloudfont', 'cognito', 'kinesis']),
        # description=dict(default=None, required=False),
        # api_key=dict(required=False, default=None, type='bool'),#Specifies whether the ApiKey can be used by callers
        # #########################
        # CREATE RESOURCE
        # #########################
        event_source=dict(required=True, default=None, type='str'),
        function_name=dict(required=True, default=None, type='str'),

        # stages=dict(default=None, required=False),
        source_params=dict(default=None, required=True, type='dict')


    )
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True,
                           mutually_exclusive=[], required_together=[]
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

        resource = None
        # ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=endpoint, **aws_connect_kwargs)
        # module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
        client = boto3_conn(module, **aws_connect_kwargs)
        aws_connect_kwargs.update(dict(region=region,
                                       endpoint=endpoint,
                                       conn_type='client',
                                       resource='dynamodbstreams'
                                       ))
        dynamodbstreams = boto3_conn(module, **aws_connect_kwargs)
        # resource=None
        # module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg="Can't authorize connection - {0}".format(e))
    except Exception as e:
        module.fail_json(msg="Connection Error - {0}".format(e))
# check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

    state = module.params.get('state')
    type_event = module.params.get('type_event')
    event_source = module.params.get('event_source')
    if ":table/" in event_source:
        type_event = 'dynamodb'

    # path = module.params.get('path').lower()
    function_name = module.params.get('function_name')
    source_params = module.params.get('source_params')

    choice_map = {
        "dynamodb": cr_dynamo_event,
        "s3": cr_dynamo_event,
        "cloudwatch": cr_dynamo_event
    }
# [api','resource','method','method_response','integration','integration_response','stage','deployment','key','authorizer','model']
    # module.fail_json(msg="what is name - {0}".format(name))

    if 'dynamodb' in type_event:  # ** "name" ** is API name. (each env may have diff id)
        typeList, changed = choice_map.get(type_event)(state, module, client, dynamodbstreams, event_source, function_name, source_params)
    else:
        module.fail_json(msg="Sorry  {0} not yet implemented".format(delta_type))
        # typeList, changed = choice_map.get(delta_type)(module, client, name, trust_policy_doc, iam_role)

    # has_changed, result = choice_map.get(module.params['state'])(module.params)
    has_changed = changed

    module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
