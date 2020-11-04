#!/usr/bin/python
# from collections import defaultdict
import os
# import time

DOCUMENTATION = '''
---
module: cr_apigw_set
short_description: create/update api resource and methods of existing TREEs.
description:
        - This module allows the user to create  resource and methods. Includes support for validating resource/method exists and  . This module has a dependency on python-boto3.
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
            - name of api gateway to target (*converts to rest_api [ID].
        required: true
        default: null
        aliases: []
    apigw_type:
        description:
            - type of API GW change target.
        required: true
        default: null
        choices: ['resource','method','method_response','integration','integration_response','model']
    path:
        description:
            - name of api gateway "FULL" path  like "/admin/users".
        required: false
        default: null
        aliases: []
    state:
        description:
            - state of change.
        required: false
        default: null
        choices: ['present','absent']

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


def method_add(module, client, main_model, isTest=False):
    errors = []
    authScopes = main_model.authScopes
    if main_model.authorizationType is None or main_model.authorizationType.lower() == "none":
        authScopes = None

    putDict = {"httpMethod": main_model.httpMethod,
               "resourceId": main_model.resourceId,
               "restApiId": main_model.restApiId
               }
    intDict = {
        "resourceId": main_model.resourceId,
        "restApiId": main_model.restApiId
    }

    # if authScopes:
    # module.fail_json(msg="[T] method_add scope  >>-> {0} {1} ".format( authScopes, main_model.authorizationType ) )
    # putDict.update({"authorizationScopes":authScopes})
    if main_model.requestparameters:
        putDict.update({"requestParameters": main_model.requestparameters})
    if main_model.requestvalidator:
        validMatch = validator_match(client, module, main_model.requestvalidator, main_model.restApiId)
        putDict.update({"requestValidatorId": validMatch['id']})
    if main_model.operationName:
        putDict.update({"operationName": main_model.operationName})
    if main_model.requestModels:
        putDict.update({"requestModels": main_model.requestModels})
    try:
        putDict.update({"authorizationType": main_model.authorizationType})
        putDict.update({"apiKeyRequired": main_model.keyRequired})
        authType = None
        if main_model.authorizationType != 'NONE':
            authType = main_model.authorizationType
        if authType:
            authIN = auth_present(client, module, main_model.authorizationName, main_model.restApiId)
            putDict.update({"authorizerId": authIN['id']})
            if authScopes != 'NONE' and authScopes:
                if authScopes[0]:
                    putDict.update({"authorizationScopes": authScopes})

                # putDict.update({"authorizationScopes": ['']})
            # module.fail_json(msg="[T] method_add scope  >>-> {0} {1} ".format( authScopes, main_model.authScopes ) )

            # find ID for autho
        client.put_method(**putDict)

        # module.fail_json(msg="[T1] method_add scope  >>-> {0} {1} ".format( main_model.authorizationType, authIN['id']) )
    except ClientError as e:
        if 'already exists' in e.response['Error']['Message']:
            errors.append(e.response['Error']['Message'])
        if not isTest:
            module.fail_json(msg="[E] 001 cr_method put_method failed - {0}".format(e.response['Error']['Message']))
    passthrough = False
    try:
        intDict.update({"type": main_model.integration['type']})
        intDict.update({"httpMethod": main_model.httpMethod})
        # module.fail_json(msg="[T] //////  put_integration  - {0}  {1}".format(main_model.integration['httpMethod'],main_model.integration['type']))
        if 'integrationHttpMethod' in main_model.integration:
            intDict.update({"integrationHttpMethod": main_model.integration['integrationHttpMethod']})
        elif 'AWS' in main_model.integration['type']:
            intDict.update({"integrationHttpMethod": main_model.integration['httpMethod']})
            if 'AWS_PROXY' in main_model.integration['type']:
                passthrough = True
        if 'uri' in main_model.integration:
            intDict.update({"uri": main_model.integration['uri']})
        if 'connectionType' in main_model.integration:
            intDict.update({"connectionType": main_model.integration['connectionType']})
        if 'connectionId' in main_model.integration:
            intDict.update({"connectionId": main_model.integration['connectionId']})
        if 'credentials' in main_model.integration:
            intDict.update({"credentials": main_model.integration['credentials']})
        if 'requestParameters' in main_model.integration:
            intDict.update({"requestParameters": main_model.integration['requestParameters']})
        if 'requestTemplates' in main_model.integration:
            intDict.update({"requestTemplates": main_model.integration['requestTemplates']})
        if 'passthroughBehavior' in main_model.integration:
            intDict.update({"passthroughBehavior": main_model.integration['passthroughBehavior']})
        if 'cacheNamespace' in main_model.integration:
            intDict.update({"cacheNamespace": main_model.integration['cacheNamespace']})
        if 'cacheKeyParameters' in main_model.integration:
            intDict.update({"cacheKeyParameters": main_model.integration['cacheKeyParameters']})
        if 'contentHandling' in main_model.integration:
            intDict.update({"contentHandling": main_model.integration['contentHandling']})
        if 'timeoutInMillis' in main_model.integration:
            intDict.update({"timeoutInMillis": main_model.integration['timeoutInMillis']})
        if main_model.credentials:
            intDict.update({"credentials": main_model.credentials})
        # module.fail_json(msg="[T] //////  timeoutInMillis  - {0}".format(main_model.integration['timeoutInMillis']))
        # module.fail_json(msg="[T] //////  timeoutInMillis  - {0}".format(intDict)  )
        client.put_integration(**intDict)
    except ClientError as e:
        errors.append(e.response['Error']['Message'])
        if not isTest:
            module.fail_json(msg="[E] method_add put_integration failed - {0} with ".format(e.response['Error']['Message']))

    try:
        # for each status code do below.....


        for rk, rv in main_model.response.items():
            resDict = {
                "resourceId": main_model.resourceId,
                "restApiId": main_model.restApiId,
                "httpMethod": main_model.httpMethod
            }

            code = rv['statusCode']
            resDict.update({"statusCode": code})
            if 'responseModels' in rv:
                rm = rv['responseModels']
                for rmKey, rmValue in rm.items():
                    rm[rmKey] = 'Empty' if rmValue is None or "Empty" else rmValue
                resDict.update({'responseModels': rv['responseModels']})
            if 'responseParameters' in rv:
                resDict.update({'responseParameters': rv['responseParameters']})

            # module.fail_json(msg=" [T] put_method_response .... - {0}".format(resDict))
            client.put_method_response(**resDict)
    except ClientError as e:
        errors.append(e.response['Error']['Message'])
        if not isTest:
            module.fail_json(msg="[E] method_add M. put_method_response failed - {0}{1}".format(e.response['Error']['Message'], resDict))

    try:
        if 'integrationResponses' in main_model.integration:
            for rk, rv in main_model.integration['integrationResponses'].items():
                iresDict = {
                    "restApiId": main_model.restApiId,
                    "resourceId": main_model.resourceId,
                    "httpMethod": main_model.httpMethod,
                    "statusCode": rv['statusCode']
                }
                if 'responseParameters' in rv:
                    iresDict.update({'responseParameters': rv['responseParameters']})
                if 'selectionPattern' in rv:
                    iresDict.update({"selectionPattern": rv['selectionPattern']})
                if 'responseTemplates' in rv:
                    rtemp = rv['responseTemplates']
                    # finalrTemplates=rtemp
                    # module.fail_json(msg=" [TT2] response template check  - {0}".format(rtemp))
                    finalrTemplates = {}
                    for tk, tv in rtemp.items():
                        ttv = '' if (tv is None or tv is"Empty") else tv
                        finalrTemplates.update({tk: ttv})
                    #
                    # WTF=finalrTemplates
                    # if isinstance(finalrTemplates, str):
                    #   WTF="is a string "
                    iresDict.update({"responseTemplates": finalrTemplates})
                    # module.fail_json(msg=" [T] method_add .... - {0}".format(finalrTemplates))
                if 'contentHandling' in rv:
                    iresDict.update({"contentHandling": rv['contentHandling']})

                if not passthrough:  # PROXY ONLY HERE
                    # module.fail_json(msg=" [T] method_add .... - {0}".format(iresDict))
                    # if 'responseParameters' not in iresDict:
                    #     iresDict.update({"responseParameters": {'method.response.header.Access-Control-Allow-Origin': "'*'"}})
                    if 'responseTemplates' not in iresDict:
                        iresDict.update({"responseTemplates": {"application/json": ""}})
                    client.put_integration_response(**iresDict)
        # module.fail_json(msg="[T] method_add put_integration_response GOOD--> - {0}".format( iresDict))
    except ClientError as e:
        errors.append(e.response['Error']['Message'])
        if not isTest:
            module.fail_json(msg="[E] method_add IN .. put_integration_response failed - {0}{1}".format(e.response['Error']['Message'], iresDict))

    if errors and not isTest:
        module.fail_json(msg=" [E] method_add  failed - {0}".format(errors))
    # time.sleep(1)
    if errors:
        found = False
        for error in errors:
            # module.fail_json(msg=" [E] WHAT THE ....HELL....  failed - {0}".format(error))
            if 'already exists for this' in error:
                found = True
                break
        if not found:
            PATH = module.params.get('error_path')
            if PATH:
                errors = [main_model.resourceId] + errors
                file_append(PATH, "_METHODS_%s_%s" % (main_model.httpMethod, isTest), errors)
        # PATH= module.params.get('error_path')
        # if PATH:
        #   file_append(PATH,"_METHODS_%s_%s"%(main_model.httpMethod,isTest), "WHAT IS THIS")
        # module.fail_json(msg=" [E] WHAT THE ....HELL....  failed - {0}".format(PATH))
# dy": false, "validateRequestParameters": true}, "response_models": {}, "state": "present", "type": null}, "msg": "[E] method_add put_integration_response failed - Invalid mapping expression specified: Validation Result: warnings : [], errors : [Invalid mapping expression parameter specified: method.response.header.Access-Control-Allow-Origin]"}


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


def object_Method_Defined(name, main_model, restApiId, resourceId):
    return type('obj', (object,), {
        "name": name,
        "description": main_model.description,
        "httpMethod": main_model.httpMethod,
        "integration": main_model.integration,
        "response": main_model.response,
        "path": main_model.path,
        "keyRequired": main_model.keyRequired,
        "requestparameters": main_model.requestparameters,
        "requestvalidator": main_model.requestvalidator,
        "authorizationType": main_model.authorizationType,
        "authorizationName": main_model.authorizationName,
        "requestModels": main_model.requestModels,
        "responseModels": main_model.responseModels,
        "operationName": main_model.operationName,
        "authScopes": main_model.authScopes,
        "credentials": main_model.credentials,

        "resourceId": resourceId,
        "restApiId": restApiId,

    })


def cr_method(state, module, client, name, resource, main_model):
    Test = False
    pName = name
    found = True
    # module.fail_json(msg="[T] .................001.......MADE IT THIS FAR.........................")
    apiFound = api_exists(module, name, client)
    if apiFound is None:
        module.fail_json(msg="[E] cr_method API name - {0} not found".format(name))
    restApiId = apiFound["id"]
    resourceFound = resource_exists(module, main_model.path, restApiId, client)
    if resourceFound is None:
        module.fail_json(msg="[E] cr_method API resource - {0} not found".format(main_model.path))
    resourceId = resourceFound['id']
    # module.fail_json(msg="[E] cr_method API resource - {0} {1} {2}".format(main_model.path, resourceId,main_model.path  ))
    # does model exist
    # module.fail_json(msg="[T] ........................MADE IT THIS FAR.........................")
    nModel = model_present(client, module, main_model.requestModels, restApiId, False)
    sModel = model_present(client, module, main_model.responseModels, restApiId, False)
    # does  auth exist
    if main_model.authorizationName:
        auth = auth_present(client, module, main_model.authorizationName, restApiId)
        if auth is None:
            msg = "[E] cr_method AUTHORIZER  - {0} not found".format(main_model.authorizationName)
            # module.fail_json(msg=msg)
    # ####################
    # module.fail_json(msg="[T] cr_method METHOD  >>-> {0}> {1}> {2}".format(main_model.httpMethod, restApiId, resourceId))
    methodFound = method_exists(module, main_model.httpMethod, restApiId, resourceId, client)
    # if main_model.authorizationType == 'CUSTOM':
    #   msg="[Q] cr_method AUTHORIZER  - {0} ".format(main_model.authorizationName)
    #   main_model.authorizationType='NONE'  #needs to be fixed in future
    # module.fail_json(msg="[Q!] cr_method  [--A P I--]  authorizerId - {0} not found".format(main_model.authorizationType))

    oDefined = object_Method_Defined(name, main_model, restApiId, resourceId)
    if methodFound is None:  # CREATE it now
        #module.fail_json(msg="[T] 001 cr_method METHOD  >>-> {0}> {1}> {2}".format(main_model.httpMethod, restApiId, resourceId))
        method_add(module, client, oDefined, False)
        found = False
    else:  # update it now
        # methodFound get authorization info it is
        if not Test:
            try:
                # module.fail_json(msg="[T] 002 cr_method METHOD  >>-> {0}> {1}> {2}".format(main_model.httpMethod, restApiId, resourceId))
                method_add(module, client, oDefined, True)
                client.delete_method(restApiId=restApiId, resourceId=resourceId, httpMethod=main_model.httpMethod)
                found = False
            except ClientError as e:
                PATH = module.params.get('error_path')
                if PATH:
                    msg = " %s  %s" % (resourceId, e)
                    file_append(PATH, "_METHODS_%s_%s" % (main_model.httpMethod, isTest), e)
                module.fail_json(msg="[E] cr_method delete_method failed - {0}".format(e.response['Error']['Message']))

        method_add(module, client, oDefined)
    # #### STAGES used to help deploy. #######
    return [pName], False if found else True


def cr_model(state, module, client, name=None, resource=None, actionPolicy=None, description=None):
    pass
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
        name=dict(required=True, default=None),  # name of the API
        apigw_type=dict(required=True, choices=['resource', 'method', 'method_response', 'integration', 'integration_response', 'model']),
        state=dict(required=True, choices=['present', 'absent']),
        description=dict(default=None, required=False),
        # api_key=dict(required=False, default=None, type='bool'),#Specifies whether the ApiKey can be used by callers
        # #########################
        # CREATE RESOURCE
        # #########################
        integration=dict(required=False, default=None, type='dict'),
        response=dict(required=False, default=None, type='dict'),
        # stages=dict(default=None, required=False),
        error_path=dict(default=None, required=False),
        path=dict(default=None, required=False),
        credentials=dict(default=None, required=False),
        apiKeyRequired=dict(required=False, default=None, type='bool'),
        httpMethod=dict(required=False, default=None),
        authorizationType=dict(required=False, default=None, choices=['NONE', 'CUSTOM', 'COGNITO_USER_POOLS']),
        authorizationScopes=dict(required=False, default=None, type='list'),
        authorizerId=dict(required=False, default=None),  # ONLY IF CUSTOM
        operationName=dict(default=None, required=False),  # A human-friendly operation identifier for the method
        resourceId=dict(required=False, default=None),
        requestParameters=dict(default=None, required=False, type='dict'),
        requestValidator=dict(default=None, required=False, type='dict'),
        requestModels=dict(default=None, required=False, type='dict'),
        authName=dict(default=None, required=False),
        responseModels=dict(default=None, required=False, type='dict'),
        # ##############################################
        # CREATE MODEL
        # ##############################################
        schema=dict(default=None, required=False),
        contentType=dict(default=None, required=False)


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
                                       resource='apigateway'
                                       ))
        choice_map = {
            "api": cr_apigw,
            "method": cr_method,
            "model": cr_model
        }

        resource = None
        # ecr = boto3_conn(module, conn_type='client', resource='ecr', region=region, endpoint=endpoint, **aws_connect_kwargs)
        # module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
        client = boto3_conn(module, **aws_connect_kwargs)
        # resource=None
        # module.fail_json(msg=" LOL cr_iam_profileo - {0}".format('iprofile'))
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg="Can't authorize connection - {0}".format(e))
    except Exception as e:
        module.fail_json(msg="Connection Error - {0}".format(e))
# check if trust_policy is present -- it can be inline JSON or a file path to a JSON file

    name = module.params.get('name')
    delta_type = module.params.get('apigw_type')

    # path = module.params.get('path').lower()
    path = module.params.get('path')
    error_path = module.params.get('error_path')

    description = module.params.get('description')
    state = module.params.get('state')

    # if action_policy_filepath:
    #   try:
    #     with open(action_policy_filepath, 'r') as json_data:
    #       action_policy_doc = json.dumps(json.load(json_data))
    #   except Exception as e:
    #     module.fail_json(msg=str(e) + ': ' + action_policy_filepath)
    # elif action_policy:
    #   try:
    #     action_policy_doc = json.dumps(action_policy)
    #   except Exception as e:
    #     module.fail_json(msg=str(e) + ': ' + action_policy)
    # else:
    #   action_policy_doc = None


# [api','resource','method','method_response','integration','integration_response','stage','deployment','key','authorizer','model']
    # module.fail_json(msg="what is name - {0}".format(name))

    if 'resource' in delta_type:  # ** "name" ** is API name. (each env may have diff id)
        typeList, changed = cr_resource(state, module, client, name, path, description)
    elif 'method' in delta_type:
        httpMethod = module.params.get('httpMethod')
        integration = module.params.get('integration')
        keyRequired = module.params.get('apiKeyRequired')
        authorizationType = module.params.get('authorizationType')
        authorizationName = module.params.get('authName')
        if authorizationName == '':
            authorizationName = None
        response = module.params.get('response')
        operationName = module.params.get('operationlabel')
        requestModels = module.params.get('requestModels')
        if isinstance(requestModels, str):
            requestModels = None
        responseModels = module.params.get('responseModels')
        if isinstance(responseModels, str):
            responseModels = None

        credentials = module.params.get('credentials')
        if credentials == "None":
            credentials = None
        # module.fail_json(msg="[T] c r e d e n t i a l s   {0} ".format(authorizationName))
        requestparameters = module.params.get('requestParameters')
        requestvalidator = module.params.get('requestValidator')
        authorizationScopes = module.params.get('authorizationScopes')
        oStructure = object_Method(name, description, httpMethod,
                                   integration, response, path, keyRequired, requestparameters, requestvalidator,
                                   authorizationType, authorizationName, requestModels, responseModels,
                                   operationName, authorizationScopes, credentials)
        typeList, changed = cr_method(state, module, client, name, resource, oStructure)
    elif 'model' in delta_type:
        schema = module.params.get('schema')
        contentType = module.params.get('contentType')
        typeList, changed = cr_model(state, module, client, name, resource, description, apiId, schema, contentType)

    else:
        module.fail_json(msg="Sorry  {0} not yet implemented".format(delta_type))
        typeList, changed = choice_map.get(delta_type)(module, client, name, trust_policy_doc, iam_role)

    # has_changed, result = choice_map.get(module.params['state'])(module.params)
    has_changed = changed

    module.exit_json(changed=has_changed, entities=typeList)


# ansible import module(s) kept at ~eof as recommended

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
