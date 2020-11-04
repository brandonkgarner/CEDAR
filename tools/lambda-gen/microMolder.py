# This code is used to create Ansible files for deploying Lambda's
# all that is needed is a target Lambda, tests, and it will do the rest.
# finds associate roles and policies
# creates Ansible modules based on those policies and roles
# defines the Lambdas and creates them with tests
# finds api-gateways or other events
# if api found defines the security needed. creates modules for deployment with templates
# import re
# from time import sleep
import os
import sys
import time
# import random
# import shutil
from datetime import datetime, date
# import boto3
from botocore.exceptions import ClientError
# import json
from shutil import copyfile
# import fileinput
import logging
import urllib

import distutils
# from distutils import dir_util

import awsconnect

from awsconnect import awsConnect
import traceback

# from context import FormatContext
# import pyaml
# pip install pyyaml
from microUtils import writeYaml, writeJSON, account_replace, loadServicesMap, loadConfig, ansibleSetup
from microUtils import describe_role
from microFront import CloudFrontMolder
from microGateway import ApiGatewayMolder
# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(__file__)


class LambdaMolder():
    origin = None
    directory = None

    temp = None

    def __init__(self, directory):
        global dir_path
        self.directory = directory
        temp = "%s/%s" % (dir_path, directory)
        self.temp = temp
        if not os.path.exists(temp):
            os.makedirs(temp)
        else:
            print(" directory %s already exists... remove or change name." % temp)

    def Cooker(self, target):
        lambda_describe(target)

    def layer_describe(self, layers, aconnect):
        # client = boto3.client('lambda')
        outLayers = []
        if layers:
            client = aconnect.__get_client__('lambda')
            for lyr in layers:
                splits = lyr['Arn'].split(":layer:")[1]
                target, version = splits.split(":")
                layer = client.get_layer_version(
                    LayerName=target, VersionNumber=version)
                cpath = layer['Content']['Location']
                code = urllib.URLopener()
                zipName = "layer_%s_%s.zip" % (target, version)
                code.retrieve(cpath, zipName)
                lObj = type('obj', (object,), {
                    'name': target,
                    'version': version,
                    'LayerArn': layer['LayerArn'],
                    'LayerVersionArn': layer['LayerVersionArn'],
                    'description': layer['Description'],
                    'CreatedDate': layer['CreatedDate'],
                    'Version': layer['Version'],
                    'LicenseInfo': layer['LicenseInfo'],
                    'CompatibleRuntimes': layer['CompatibleRuntimes']
                }
                )
                outLayers.append((lObj, zipName))
        return outLayers

    ###
    def method_describe(self, target, aconnect):
        # client = boto3.client('lambda')
        client = aconnect.__get_client__('lambda')
        lmda = client.get_function(FunctionName=target)
        cpath = lmda['Code']['Location']
        #code = urllib.URLopener()
        zipName = "code_%s.zip" % (target)
        #code.retrieve(cpath, zipName)
        urllib.request.urlretrieve(cpath, zipName)
        # RevisionId
        # print (cpath)
        # print(' ZIP DOWNLOADED??')
        config = lmda['Configuration']
        vpcs = envars = layers = alias = None
        if 'VpcConfig' in config:
            vpcs = config['VpcConfig']
        if "Layers" in config:
            layers = config["Layers"]
        if 'Environment' in config:
            envars = config['Environment']
        if 'RevisionId' in config:
            alias = config['RevisionId']
        return type('obj', (object,), {
                    'memory': config['MemorySize'],
                    'farn': config['FunctionArn'],
                    'vpcs': vpcs,
                    'envars': envars,
                    'handler': config['Handler'],
                    'lrole': config['Role'],
                    'timeout': config['Timeout'],
                    'runtime': config['Runtime'],
                    'description': config['Description'],
                    'alias': alias,
                    'layers': layers
                    }
                    ), zipName

    def lambda_describe(self, target, aconnect, accountOrigin, accounts=[], types=[], sendto=None, targetAPI=None, isFullUpdate=False):
        if len(types) == 0:
            types = ['apigw']
        else:
            if 's3' in types:
                print(
                    '[W] warning buckets will not be created only updated with triggers found')
        sts = None

        acctTitle = None
        self.origin = accountOrigin
        acctID = accountOrigin['account']
        assumeRole = accountOrigin['assume_role']
        lambdaM, zipName = self.method_describe(target, aconnect)
        NETWORK_MAP = loadServicesMap(accountOrigin['services_map'], 'RDS')
        TOKEN_MAP = loadServicesMap(accountOrigin['services_map'], 'token')
        COGNITO_MAP = loadServicesMap(accountOrigin['services_map'], 'cognito')
        XACT_MAP = loadServicesMap(accountOrigin['services_map'], 'xact')
        BUCKET_MAP = loadServicesMap(accountOrigin['services_map'], 'S3')
        SLACK_MAP = loadServicesMap(accountOrigin['services_map'], 'slack')
        SIGNER_MAP = loadServicesMap(accountOrigin['services_map'], 'signer')
        DOMAIN_MAP = loadServicesMap(accountOrigin['services_map'], 'domains')
        CFRONT_MAP = loadServicesMap(
            accountOrigin['services_map'], 'cloudfront')

        skipping = error_path = None
        if 'error_path' in accountOrigin:
            error_path = accountOrigin['error_path']
        if 'skipping' in accountOrigin:
            skipping = accountOrigin['skipping']
        # error_path: /Users/astro_sk/Documents/TFS/Ansible_Deployer
        if not skipping:
            skipping = {
                "methods": False,
                "options": False,
                "models": False,
                "stage": False,
                "resources": False
            }

        roles, resourceRole = describe_role(
            lambdaM.lrole, aconnect, self.origin['account'], True if 'api' in types else False)
        layers = self.layer_describe(lambdaM.layers, aconnect)
        if "python" not in lambdaM.runtime:
            print("   #####    WARNING   #####")
            print("   [W] runtime using [%s] is depreciated please use [Python 3]!!!" % (
                lambdaM.runtime))
            print("      ##### END WARNING. #####")
        print(" [W] ROLE being used for API(s) %s" % resourceRole)

        apis = models = authorizeDict = authorizers = authLambdas = None
        if 'api' in types:
            try:
                if targetAPI:
                    apis, stages, models, authorizeDict = self.describe_gateway(
                        target, 'lambda', aconnect, resourceRole, targetAPI)
                    # apis, stages, models, authorizeDict = self.describe_gateway('*','lambda', aconnect, resourceRole, targetAPI)
            except Exception as e:
                msg = "%s  ::  :: %s" % (e, traceback.format_exc())
                print(msg)
                print(" COULD it be a different API tree %s" % (targetAPI))
                raise e
        # print (authorizeDict)
        # raise
        events = None
        buckets = None
        test = True
        if not test:
            if 'cloudwatch' in types:
                events = self.describe_cloudevents(
                    target, lambdaM.farn, aconnect)
            if 's3' in types:
                buckets = self.describe_s3events(target, aconnect)
                raise
        dynoTriggers = None
        if 'dynamodb' in types:
            dynoTriggers = self.describe_dynoTriggers(target, aconnect)
            # print(dynoTriggers)
            # raise

        taskMain, rootFolder, targetLabel = ansibleSetup(
            self.temp, target, isFullUpdate)
        if layers:
            print("Layer functions currently not supported!!")
            # taskMain.insert(2, {"import_tasks":  "../aws/layers.yml", "vars": {"project": '{{ project }}'}})
        ###########################
        # AUTH LAMBDAS
        ###########################
        if authorizeDict:
            authorizers = authorizeDict
            authLambdas = []
            print(authorizeDict)
            for authIN in authorizeDict:
                if authIN['authType'] in 'custom':
                    l_arn = authIN['authorizerUri'].split(":function:")[1]
                    authTARGET = l_arn.split("/invocations")[0]
                    authLam, authZipName = self.method_describe(
                        authTARGET, aconnect)
                    authRoles, authResourceRole = describe_role(
                        authLam.lrole, aconnect, self.origin['account'], True)
                    zipFile = "%s.zip" % authTARGET
                    zipLambda = "%s/%s/%s" % (rootFolder, 'files', zipFile)
                    copyfile(authZipName, zipLambda)
                    rolename = authLam.lrole.split(":role/")[1]
                    aLambda = {
                        "name": authTARGET,
                        "state": "present",
                        "runtime": authLam.runtime,
                        "timeout": authLam.timeout,
                        "description": authLam.description,
                        "role": rolename,
                        "handler": authLam.handler,
                        "memory_size": authLam.memory,
                        "alias": authLam.alias,
                        # "code_location": "",  ### this is needed to prevent issues with the bundled lambda
                        "zip_file": "{{ role_path }}/files/%s" % zipFile
                    }
                    if not authLam.envars is None:
                        aLambda.update(
                            {"environment_variables": authLam.envars['Variables']})
                    authLambdas.append(aLambda)

        ###########################
        # AUTH LAMBDAS
        ###########################

        if apis:
            if authorizeDict:
                taskMain.append(
                    {"import_tasks": "../aws/agw_authorizer.yml", "vars": {"project": '{{ project }}'}})
            taskMain.append({"import_tasks": "../aws/agw_model.yml",
                             "vars": {"project": '{{ project }}'}})
            taskMain.append({"import_tasks": "../aws/_agw.yml",
                             "vars": {"project": '{{ project }}'}})
        if events:
            taskMain.append({"import_tasks": "../aws/cldwatch_rule.yml",
                             "vars": {"project": '{{ project }}'}})
        if buckets:
            taskMain.append({"import_tasks": "../aws/s3.yml",
                             "vars": {"project": '{{ project }}'}})
        if dynoTriggers:
            print("in triggers for dynamo")
            taskMain.append({"import_tasks": "../aws/lambda_dyno_triggers.yml",
                             "vars": {"project": '{{ project }}'}})
            # raise
        #############################################
        #############################################
        # ####### write YAML to file in tasks  #######
        #############################################
        #############################################
        option = "main"
        mainIn = "%s/%s/%s" % (rootFolder, 'tasks', option)
        writeYaml(taskMain, mainIn)

        #############################################
        # ##########   END WRITE  ####################
        #############################################
        #############################################
        # print(NETWORK_MAP)
        # raise ValueError(" stopping now for check...")
        # CREATE DEFAULT in "defaults" VARS
        for akey, account in accounts.items():
            networkObj = NETWORK_MAP[akey]
            bucketObj = BUCKET_MAP[akey]
            cfrontObj = CFRONT_MAP[akey]
            domainObj = DOMAIN_MAP[akey]
            cognitoObj = COGNITO_MAP[akey]
            xactObj = XACT_MAP[akey]
            tokenObj = TOKEN_MAP[akey]
            slackObj = SLACK_MAP[akey]
            signerObj = SIGNER_MAP[akey]
            if akey == acctID:
                acctTitle = account['title']

            accDetail = {
                "account_id": akey,
                "error_path": error_path,
                "skipping": skipping,
                "env": account['title'],
                "role_duration": 3600,
                "region": "us-east-1",
                "eid": account['eID'],
                "roles": [],
                "policies": []
            }
            if assumeRole:
                accDetail.update({"cross_acct_role": account['role']})
            defaultVar = {targetLabel: accDetail}
            # add Policies
            role_list = []
            role_policies = []

            for role in roles:
                rName = role['name']
                rData = role['data']
                rDescribe = "CR-Default no description found"
                if 'Description' in rData:
                    rDescribe = rData['Description']
                rNamePlcy = "%s_%s" % (rName, "trust")
                trustIn = "%s/%s/%s" % (rootFolder, 'files', rNamePlcy)
                # print ".... dude.....look up......"
                rfile = writeJSON(rData['AssumeRolePolicyDocument'], trustIn)
                #print (role)
                # exit()
                roleIn = {
                    "name": rName,
                    "trust_policy_filepath": "{{ role_path }}/files/%s" % rfile,
                    "type": "role",
                    "state": "present",
                    "path": rData['Path'],
                    "description": rDescribe
                }
                # polices are in seperate list!!!!!
                plcies = role['policies']
                plcyNames = []
                for rp in plcies:
                    rpName = rp['PolicyName']
                    rpDoc = rp['PolicyDocument']
                    rpDescription = rp['Description']
                    rpPath = rp['Path']
                    fpIn = "%s/%s/%s" % (rootFolder, 'files', rpName)
                    pfile = writeJSON(rpDoc, fpIn)
                    plcyNames.append(rpName)
                    rPolicy = {
                        "name": rpName,
                        "state": "present",
                        "type": "policy",
                        "policy_document": "{{ role_path }}/files/%s" % pfile
                    }
                    role_policies.append(rPolicy)
                roleIn.update({"action_policy_labels": plcyNames})
                role_list.append(roleIn)
                # CREATE POLICIES

            defaultVar[targetLabel].update({"policies": role_policies})
            defaultVar[targetLabel].update({"roles": role_list})

            ########################################################
            ####################  LAMBDAS   ########################
            ########################################################

            tempRname = role_list[0]['name']

            # move zip file
            zipFile = "%s.zip" % target
            zipLambda = "%s/%s/%s" % (rootFolder, 'files', zipFile)
            #os.rename("code.zip", zipLambda)
            copyfile(zipName, zipLambda)
            layer_list = []
            for listLayer in layers:
                lObj, zipLayer = listLayer
                layerIn = {
                    "name": lObj.name,
                    "state": "present",
                    "version": lObj.version,
                    "arn": lObj.LayerArn,
                    "version_arn": lObj.LayerVersionArn,
                    "runtimes": lObj.CompatibleRuntimes,
                    "license": lObj.LicenseInfo,
                    "description": lObj.description,
                    "zip_file": "{{ role_path }}/files/%s" % zipLayer
                }
                layer_list.append(layerIn)

            defaultVar[targetLabel].update({"lambda_layers": layer_list})

            if not tempRname in lambdaM.lrole:
                print("[E] role doesn't match %s with %s" %
                      (tempRname, lambdaM.lrole))
            oLambda = {
                "name": target,
                "state": "present",
                "runtime": lambdaM.runtime,
                "timeout": lambdaM.timeout,
                "description": lambdaM.description,
                "role": tempRname,
                "handler": lambdaM.handler,
                "memory_size": lambdaM.memory,
                "alias": lambdaM.alias,
                # "code_location": "",  ### this is needed to prevent issues with the bundled lambda
                "zip_file": "{{ role_path }}/files/%s" % zipFile
            }

            if lambdaM.layers is not None:
                oLambda.update({"layers": lambdaM.alias})
            if lambdaM.envars is not None:
                oLambda.update(
                    {"environment_variables": lambdaM.envars['Variables']})
            if lambdaM.vpcs is not None:
                if len(lambdaM.vpcs['SecurityGroupIds']) != 0:
                    #oLambda.update({"vpc_security_group_ids": lambdaM.vpcs['SecurityGroupIds']})
                    oLambda.update(
                        {"vpc_security_group_ids": networkObj['vpc_security_group_ids']})
                if len(lambdaM.vpcs['SubnetIds']) != 0:
                    #oLambda.update({"vpc_subnet_ids": lambdaM.vpcs['SubnetIds']})
                    oLambda.update(
                        {"vpc_subnet_ids": networkObj['vpc_subnet_ids']})
                if 'VpcId' in lambdaM.vpcs:
                    if len(lambdaM.vpcs['VpcId']) != 0:
                        #oLambda.update({"vpc": lambdaM.vpcs['VpcId']})
                        oLambda.update({"vpc": networkObj['vpc']})

            lambdas = [oLambda]

            if authorizers:
                lambdas = lambdas + authLambdas

            defaultVar[targetLabel].update({"lambdas": lambdas})

            ########################################################
            ####################  EVENTS   ########################
            ########################################################

            if not events is None:  # NEW
                crules = []
                for rule in events:
                    description = "%s - Description by microMolder" % (
                        rule['Name'])
                    if 'Description' in rule:
                        description = rule['Description']
                    crules.append({
                        "name": rule['Name'],
                        "schedule_expression": rule['ScheduleExpression'],
                        "description": description,
                        "state": rule['State'],
                        "targets": rule['targets']
                    })
                defaultVar[targetLabel].update({"cloud_rules": crules})

            ########################################################
            ##############  S3 bucket Triggers   ###################
            ########################################################
            # print (".   ---->>> BUCKETS. &^*&^*&^^&*^*&^&*%^&%^^")
            bucket_list = []
            if buckets:  # bucketObj
                for bkt in buckets:
                    # print (bkt)
                    # print ("     .... #@@@#")
                    s3Trigger = {
                        'Id': bkt['config']['Id'],
                        # 'bucket': bkt['bucket'],
                        'bucket': bucketObj['bucket'],
                        'lambdaArn': bkt['config']['LambdaFunctionArn'],
                        'state': 'present',
                        # 'alias':bkt
                        'events': bkt['config']['Events']
                    }

                    if 'Filter' in bkt['config']:
                        s3Filter = bkt['config']['Filter']['Key']['FilterRules']
                        s3dict = {n['Name']: n['Value'] for n in s3Filter}
                        s3Trigger.update({'filter': s3dict})
                    bucket_list.append(s3Trigger)

                defaultVar[targetLabel].update({"buckets": bucket_list})
            ########################################################
            # #############  Dynamo DB Triggers   ###################
            ########################################################
            dyno_list = []
            if dynoTriggers:  # bucketObj
                for trigger in dynoTriggers:
                    dyno_list.append(trigger)

                defaultVar[targetLabel].update({"triggers_dynamo": dyno_list})

            ########################################################
            #############  API GATEWAY METHODS   ###################
            ########################################################
            #print (" A P I. see below. ......===---->>>")
            api_list = []
            stage_list = []  #
            model_list = models  # []  #
            auth_list = authorizers  # []  #
            # stages.update({apiStage:{'stage':stageLabel,'api':apiName}})
            if not apis is None:
                # for mk,mv in models.items():
                #    model_list.append(mv)
                for sk, sv in stages.items():
                    stage_list.append(sv)
                for api in apis:
                    oApi = {
                        'name': api['name'],
                        'id': api['id'],
                        'credentials': "%s" % api['credentials'],
                        'authorizationType': api['authorizationType'],
                        'apiKeyRequired': api['apiKeyRequired'],
                        'type': api['type'],
                        'path': api['path'],
                        'operational_name': api['operationlabel'],
                        'request_valid': api['requestvalidator'],
                        'request_params': api['requestparameters'],
                        'auth_scope': api['authscope'],
                        'authName': api['authName'],
                        'request_models': api['requestmodels'],
                        'response_models': api['responsemodels'],
                        'httpMethod': api['httpMethod'],
                        'parentid': api['parentid'],
                        'method_response': api['methodResponse'],
                        'method_integration': api['methodIn'],
                        'state': api['state']

                    }

                    api_list.append(oApi)
                defaultVar[targetLabel].update({"api_gw": api_list})
                defaultVar[targetLabel].update({"api_stages": stage_list})
                defaultVar[targetLabel].update({"api_models": model_list})
                if auth_list:
                    defaultVar[targetLabel].update(
                        {"api_authorizers": auth_list})
                #defaultVar[targetLabel].update({ "api_domains": stage_list })
                #defaultVar[targetLabel].update({ "api_usage": stage_list })

            option = "main_%s" % account['all']
            mainIn = "%s/%s/%s" % (rootFolder, 'defaults', option)
            writeYaml(defaultVar, mainIn)
            account_replace("%s.yaml" % mainIn, str(acctID), str(akey))

            for key, value in DOMAIN_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(domainObj[key]))

            for key, value in BUCKET_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(bucketObj[key]))

            for key, value in TOKEN_MAP[acctID].items():
                account_replace("%s.yaml" %
                                mainIn, str(value), str(tokenObj[key]))

            for key, value in NETWORK_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(networkObj[key]))

            for key, value in COGNITO_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(cognitoObj[key]))

            for key, value in XACT_MAP[acctID].items():
                account_replace("%s.yaml" %
                                mainIn, str(value), str(xactObj[key]))

            for key, value in SLACK_MAP[acctID].items():
                account_replace("%s.yaml" %
                                mainIn, str(value), str(slackObj[key]))

            for key, value in SIGNER_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(signerObj[key]))

            for key, value in CFRONT_MAP[acctID].items():
                account_replace("%s.yaml" % mainIn, str(
                    value), str(cfrontObj[key]))

        print(" .... creating a main.yaml for ansible using dev")
        opt = "main_%s.yaml" % accountOrigin['all']
        src = "%s/%s/%s" % (rootFolder, 'defaults', opt)
        opt2 = "main.yaml"
        dst = "%s/%s/%s" % (rootFolder, 'defaults', opt2)
        copyfile(src, dst)
        print(" -------==------===---- COPY START....")
        print(" sending to %s. from %s" % (sendto, rootFolder))
        distutils.dir_util.copy_tree(rootFolder, sendto)
        print(" -------==------===---- FINAL YAML file....")
        ansibleRoot = sendto.split('roles/')[0]
        targets = ['%s' % target]
        rootYML = [{"name": "micro modler for lambda-%s" % target,
                    "hosts": "dev",
                    "remote_user": "root",
                    "roles": targets}]
        # ansibleRoot
        writeYaml(rootYML, ansibleRoot, target)
        return acctID, target, acctTitle, True

    # def describe_role(self, name, aconnect, apiTRigger=False):
    #   client = aconnect.__get_client__('iam')
    #   #client = boto3.client('iam')
    #   if "/" in name:
    #       name=name.split("/")[1]
    #   #print(name)
    #   #print(". oo kkk  ooo k kok")
    #   roleData = client.get_role(RoleName=name)['Role']
    #   del roleData['CreateDate']
    #   arn = roleData['Arn']
    #   roles=[]
    #   aplcy = client.list_attached_role_policies(RoleName=name)
    #   policies=[]
    #   givenPolicies=aplcy['AttachedPolicies']
    #   if apiTRigger:
    #       print (" #########################################################")
    #       print (" ########### ADDING Policy : CR-Lambda-APIGW. ############")
    #       print (" #########################################################")
    #       acct=self.origin['account']
    #       pname="CR-Lambda-APIGW"
    #       p_arn="arn:aws:iam::%s:policy/%s"%(acct, pname)
    #       pDefinition =self.describe_policy(p_arn, pname, aconnect)
    #       policies.append(pDefinition)
    #   if len(givenPolicies) !=0:
    #       for plcy in givenPolicies:
    #           polName = plcy['PolicyName']
    #           polARN = plcy['PolicyArn']
    #           pDefinition =self.describe_policy(polARN, polName, aconnect)
    #           policies.append(pDefinition)
    #   roles.append({'name':name, 'data':roleData, 'policies':policies})
    #   return roles, arn

    # def describe_policy(self, arn, name, aconnect):
    #   client = aconnect.__get_client__('iam')
    #   #client = boto3.client('iam')
    #   polMeta=client.get_policy(PolicyArn=arn)['Policy']
    #   polDefined=client.get_policy_version(PolicyArn=arn, VersionId=polMeta['DefaultVersionId'])
    #   #polDefined = client.get_role_policy(RoleName=name,PolicyName=polName)
    #   print(" POLICY. %s...."%name)
    #   print (polDefined)
    #   doc=polDefined['PolicyVersion']['Document']
    #   # print("------==polMeta=--------")
    #   # print (polMeta)
    #   description='CR-Default no description found'
    #   if 'Description'in polMeta:
    #       description=polMeta['Description']
    #   path= polMeta['Path']
    #   print ("  -->"+path)
    #   return {'PolicyName':name,
    #           'Path':path,
    #           'PolicyDocument':doc,
    #           'Description':description     }

    # def describe_apiKey(self, resourceNname, resourceType):
    #   pass

    # def describe_apiUsage(self, resourceNname, resourceType):
    #   pass

    # def describe_stages(self, apiID, apiName, stages):
    #   client = aconnect.__get_client__('apigateway')
    #   #client = boto3.client('apigateway')
    #   usage = client.get_usage_plans()['items']
    #   for use in usage:
    #       for stage in use['apiStages']:
    #           if apiID in stage['apiId']:
    #               stageLabel = stage['stage']
    #               apiStage = "%s_%s"%(apiName,stageLabel)
    #               if apiStage in stages:
    #                   continue
    #               stages.update({apiStage:{'stage':stageLabel,'api':apiName, 'state':'present'}})
    #   return stages

    # def getAllResources(self,client,restApiId, position=None):
    #   rlist=[]
    #   if position is None:
    #       response = client.get_resources( restApiId=restApiId, limit=500)
    #   else:
    #       response = client.get_resources( restApiId=restApiId,position=position, limit=500)
    #   baseList=response['items']
    #   if "position" in response :
    #       rlist=self.getAllResources(client,restApiId, response['position'])
    #   final = baseList+rlist
    #   return final

    # def getAll_rest_apis(self,client, position=None):
    #   rlist=[]
    #   if position is None:
    #       response = client.get_rest_apis(  limit=500)
    #   else:
    #       response = client.get_rest_apis( position=position, limit=500)
    #   baseList=response['items']
    #   if "position" in response :
    #       rlist=self.getAll_rest_apis(client, response['position'])
    #   final = baseList+rlist
    #   return final

        # get api, resource, method, integration and responses, models

    def describe_gateway(self, resourceNname, resourceType, aconnect, resourceRole=None, targetAPI=None):
        agw = ApiGatewayMolder("ansible")

        return agw.describe_gateway(resourceNname, resourceType, aconnect, resourceRole, targetAPI)

    # def describe_gateway(self, resourceNname, resourceType, aconnect , resourceRole=None,targetAPI=None):

    #   client = aconnect.__get_client__('apigateway')
    #   #client = boto3.client('apigateway')
    #   #apis=client.get_rest_apis()
    #   apis=self.getAll_rest_apis(client)
    #   integratedAPIs = []
    #   stages={}
    #   addedResource={}
    #   possibleOptions={}
    #   print ("*********************************************************************")

    #   print ("                  API GATEWAY                                              ")
    #   print ("*********************************************************************")
    #   print ( apis)

    #   print ("*********************************************************************")
    #   print (targetAPI)
    #   #for api in apis['items']:
    #   for api in apis:
    #       id = api['id']
    #       name= api['name']
    #       if targetAPI is not None:
    #           if name.lower() != targetAPI.lower():
    #               continue

    #       #resources = client.get_resources( restApiId=id,limit=500)
    #       resources = self.getAllResources(client,restApiId=id)

    #       print ("                            API GATEWAY       resources                                       ")
    #       print ("     resources    %s     "%resources)
    #       #for rest in resources['items']:
    #       for rest in resources:
    #           path= rest['path']
    #           mId=rest['id']
    #           parentId = None
    #           if 'parentId' in rest:
    #               parentId=rest['parentId']
    #           if not 'resourceMethods' in rest:
    #               parent =rest
    #               continue
    #           for key,value in rest['resourceMethods'].items():

    #       ### ONLY FOR TESTINNG
    #               # if not 'GET' in key:
    #               #     continue
    #       ### DELETE ABOVE !!!!!!!!!

    #               print ("      *API*     ")
    #               print ("   @#@#. 002. #@#@ %s %s  client.get_method(restApiId=%s,resourceId=%s,httpMethod=%s)"%(name, path, id, mId, key) )
    #               integrated = None
    #               mInfo=value
    #               print value
    #               # try:
    #               #     integrated = client.get_integration(restApiId=id, resourceId=mId, httpMethod=key)
    #               #     del integrated['ResponseMetadata']
    #               # except ClientError as e:
    #               #     print(e.response['Error']['Message'])

    #               #print integrated
    #               method = client.get_method( restApiId=id,resourceId=mId,httpMethod=key)
    #               del method['ResponseMetadata']
    #               authType = method['authorizationType']
    #               keyRequired=method['apiKeyRequired']
    #               integratedType=None
    #               if not 'methodIntegration' in method:
    #                   continue
    #               methodIntegration = method['methodIntegration']
    #               print (" method:")
    #               print (method)
    #               #method = client.get_method( restApiId='20iv84vxh9',resourceId='i8b9of',httpMethod='GET')
    #               # if not 'uri' in methodIntegration:
    #               #     # print(".    - -- - 002-- -   ?")
    #               #     # print ( methodIntegration )
    #               #     continue
    #               operationName=rModels=sModels=authName=requestParameters=authScope=None
    #               methodResponse=None
    #               if 'methodResponses' in method:
    #                   methodResponse =method['methodResponses']
    #                   # print("~~~~~1")
    #                   # print (methodResponse)
    #                   # print("~~~~~1bb")
    #                   if '200' in methodResponse:
    #                       if 'responseModels' in methodResponse['200']:
    #                           mm = methodResponse['200']['responseModels']
    #                           sModels={}
    #                           for mkey , mvalue in mm.items():
    #                               sModels.update({mkey:mvalue})

    #               if 'requestModels' in method:
    #                   sm = method['requestModels']
    #                   rModels={}
    #                   # print("~~~~~2")
    #                   # print(sm)
    #                   # print("~~~~~2bb")
    #                   for rkey , rvalue in sm.items():
    #                       rModels.update({rkey:rvalue})
    #               integration=None
    #               if 'uri' in methodIntegration:
    #                   integration = methodIntegration['uri']
    #               if rModels is None:
    #                   rModels={}
    #               if sModels is None:
    #                   sModels={}
    #               if requestParameters is None:
    #                   requestParameters={}
    #               if methodResponse is None:
    #                   methodResponse={}
    #               if integration is None:
    #                   integration={}

    #               if 'requestParameters' in method:
    #                   requestParameters=method['requestParameters']
    #               if 'authorizerId' in method:
    #                   auth = client.get_authorizer(restApiId=id,  authorizerId=method['authorizerId'] )
    #                   authName = auth['name']
    #               if 'authorizationScopes' in method:
    #                   authscope = method['authorizationScopes']
    #               # api id, stage id.
    #               stages=self.describe_stages(id, name, stages)
    #               add =False
    #               if resourceType in integration and resourceNname in integration:
    #                   add=True
    #               elif key == "OPTIONS":
    #                   possibleOptions.update( {path:{'name':name,
    #                       'parentid':parentId,
    #                       'credentials': None,
    #                       'state': 'present',
    #                       'id':mId,
    #                       'operationlabel':operationName ,
    #                       'requestparameters': requestParameters,
    #                       'authscope': authScope,
    #                       'requestmodels': rModels,
    #                       'responsemodels': sModels,
    #                       'authorizationType': authType,
    #                       'authName': authName,
    #                       'apiKeyRequired': keyRequired,
    #                       'type': integratedType,
    #                       'path': path,
    #                       'httpMethod':method['httpMethod'],
    #                       'methodIn': methodIntegration,
    #                       'methodResponse': methodResponse } })
    #                   # if 'COGNITO' in authType:
    #                   # print ("  . . .1 . .  ")
    #                   # print (method)
    #                   # print ("  . . .2 . .  ")
    #               if add:
    #                   addedResource.update({path:mId})
    #                   if not 'credentials' in methodIntegration:
    #                       methodIntegration.update({'credentials':resourceRole})
    #                   integratedAPIs.append(
    #                       {'name':name,
    #                       'parentid':parentId,
    #                       'credentials': resourceRole,
    #                       'state': 'present',
    #                       'id':mId,
    #                       'operationlabel':operationName ,
    #                       'requestparameters': requestParameters,
    #                       'authscope': authScope,
    #                       'requestmodels': rModels,
    #                       'responsemodels': sModels,
    #                       'authorizationType': authType,
    #                       'authName': authName,
    #                       'apiKeyRequired': keyRequired,
    #                       'type': integratedType,
    #                       'path': path,
    #                       'httpMethod':method['httpMethod'],
    #                       'methodIn': methodIntegration,
    #                       'methodResponse': methodResponse }    )

    #   for rK,rV in addedResource.items():  #Ensure OPTIONS picked up for Methods gathered
    #       if rK in possibleOptions:
    #           integratedAPIs.append(possibleOptions[rK])

    #   #raise ValueError(" stopping now for check...")
    #   if len(integratedAPIs) ==0:
    #       return None
    #   return integratedAPIs, stages

    def describe_cloudevents(self, target, functionArn, aconnect):
        events = []
        client = aconnect.__get_client__('events')
        #client = boto3.client('events')
        print("------CLOUD EVENT--------ok---------")
        print(functionArn)
        rnames = client.list_rule_names_by_target(
            TargetArn=functionArn)['RuleNames']
        for name in rnames:
            event = client.describe_rule(Name=name)
            eventTarget = client.list_targets_by_rule(Rule=name)
            event.update(
                {"targets": [{k.lower(): v for k, v in x.items()} for x in eventTarget['Targets']]})
            event['State'] = "present" if event['State'] == 'ENABLED' else 'disabled'
            del event['ResponseMetadata']
            events.append(event)
        if len(events) == 0:
            return None
        return events

    def describe_s3events(self, target, aconnect):
        # get_bucket_notification_configuration
        buckets = []

        client = aconnect.__get_client__('s3')
        #client(service_name, region_name=None, api_version=None, use_ssl=True, verify=None, endpoint_url=None, aws_access_key_id=None, aws_secret_access_key=None, aws_session_token=None, config=None)
        allS3 = client.list_buckets()['Buckets']

        for bucket in allS3:
            bname = bucket['Name']
            response = client.get_bucket_notification_configuration(
                Bucket=bname)
            if 'LambdaFunctionConfigurations' in response:
                for config in response['LambdaFunctionConfigurations']:
                    if target in config['LambdaFunctionArn'] or '*' == target:
                        buckets.append({'bucket': bname, 'config': config})
        if len(buckets) == 0:
            return None
        return buckets

    def describe_dynoTriggers(self, target, aconnect):
        client = aconnect.__get_client__('lambda')
        eventMaps = client.list_event_source_mappings(
            FunctionName=target)['EventSourceMappings']
        # lambdas = self.get_LambdaDynamos(target, aconnect)
        triggers = []
        # print("-------")
        # print(eventMaps)
        # print("-------")
        # raise
        for lb in eventMaps:
            # print(lb)
            event_source = lb['EventSourceArn'].split('/')[:2]
            event_source = "/".join(event_source)
            # print(event_source)
            print(". -->%s" % event_source)
            if ':table/' not in event_source and ':dynamodb:' not in event_source:
                continue
            # print(event_source)
            table = event_source.split("/")[-1]
            obj = {"function_name": target, "state": "present", "event_source": event_source,
                   "function_arn": lb['FunctionArn'], "source_params": None}
            state = True if lb['State'] == 'Enabled' else False
            source_params = {"source_arn": event_source, "enabled": state,
                             "starting_position": "LATEST", "batch_size": lb['BatchSize']}
            additionalParams = ["MaximumBatchingWindowInSeconds", "ParallelizationFactor", "DestinationConfig",
                                "MaximumRecordAgeInSeconds", "BisectBatchOnFunctionError", "MaximumRetryAttempts"]
            print(lb)
            for add in additionalParams:
                if add in lb:
                    source_params.update({add: lb[add]})
                    print("ADDED")
            obj.update({"source_params": source_params})
            obj['TableName'] = table
            triggers.append(obj)
            # print("-------")
            # print(obj)
            # raise
        # print("========>> >  >   > #@##@@!&*")
        # print(target)
        # print(triggers)
        # raise
        if len(triggers) == 0:
            return None
        return triggers


# AWS4-HMAC-SHA256\n20150830T123600Z\n20150830/us-east-1/apigateway/aws4_request\n

        def api_documentation(self):
            print(time.strftime('%Y%m%d'))


# python microMolder.py -G API_Name true ENVR.yaml '/Users/astro_sk/Documents/TFS/Ansible_Deployer/ansible/roles/API_Name' API_Name true
# python microMolder.py -G API_Name true ENVR.yaml '/Users/astro_sk/Documents/TFS/Ansible_Deployer/ansible/roles/API_Name' API_Name true


if __name__ == "__main__":
    found = None
    length = 0
    start_time = time.time()
    try:
        sys.argv[1]
        found = sys.argv
        length = len(found)
    except:
        found = "help"
        # ansible-playbook -i windows-servers xx-LambdaName -vvvv
# python microMolder.py -L xx-LambdaName true ENVR.yaml '/path/to/Ansible_Deployer/ansible/roles/xx-LambdaName' API_Name true
# python microMolder.py -L xx-LambdaName true ENVR.yaml '/path/to/Ansible_Deployer/ansible/roles/xx-LambdaName' API_Name true
# python microMolder.py -L xx-LambdaName true ENVR.yaml '/path/to/Ansible_Deployer/ansible/roles/xx-LambdaName' '*' true
# python microMolder.py -L xx-LambdaName true ENVR.yaml '/path/to/Ansible_Deployer/ansible/roles/xx-LambdaName' API_Name true
# python microMolder.py -L xx-LambdaName true ENVR.yaml '/path/to/Ansible_Deployer/ansible/roles/xx-LambdaName' API_Name true
    if "help" in found and length < 3:
        print(" ************************************************************")
        print("      Try using the following PSUEDO after *CONFIG.yaml is correct :")
        print("           python microMolder.py -L lambda useRoleDeployer configYaml sendto targetAPI isFullUpdate")
        print(
            "         -[NOTE]--> 'useRoleDeployer' and 'sendto' and 'targetAPI' can be passed as null  for all ")
        print("      REAL example when using STS (cross deploy role):")
        print("      TODO  -CF -S3 -DN -SQ ")
        print("           python microMolder.py -L xx-LambdaName true ENVR.yaml '/path/to/Ansible_Deployer/ansible/roles/xx-LambdaName' RELM false")
        print(" ************************************************************")
        exit()
    else:
        print("  ..... INIT..... 0001 ")
        type_in = str(sys.argv[1]).strip()
        svc_in = str(sys.argv[2]).strip()
        useRoleDeployer = str(sys.argv[3]).strip()
        if useRoleDeployer.lower() == "none" or useRoleDeployer.lower() == "null" or useRoleDeployer.lower() == "false":
            useRoleDeployer = None
        config = str(sys.argv[4]).strip()
        # config='ENVR.yaml'
        sendto = str(sys.argv[5]).strip()
        if sendto.lower() == "none" or sendto.lower() == "null":
            sendto = None
        if len(sys.argv) > 6:
            targetAPI = str(sys.argv[6]).strip()
            print(sys.argv[6])
            print("7 is %s" % sys.argv[7])
            if targetAPI.lower() == "none" or targetAPI.lower() == "null" or targetAPI == "*":
                targetAPI = None
        if len(sys.argv) > 8:
            raise ValueError(
                " * should be in quotes '*' or use specific API target name")
        if length > 7:
            fullUpdate = str(sys.argv[7]).strip().lower()
            if fullUpdate == "none" or fullUpdate == "null" or fullUpdate == "false":
                fullUpdate = False
            else:
                fullUpdate = True
        else:
            fullUpdate = False

        logging.basicConfig(format='%(asctime)-15s %(message)s')
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        logger.info("Started")
        print("  ..... INIT..... 0002. %s ,   %s" % (dir_path, config))

        fullpath = "%s/%s" % (dir_path, config)
        env = 'dev'
        origin, global_accts = loadConfig(fullpath, env)
        triggers = origin['triggers']
        if triggers is None:
            raise ValueError(
                "[E] config file [ %s ] did not load correctly.. PLEASE check / fix and try again" % (fullpath))
        accID = origin['account']
        region = origin['region']
        accountRole = global_accts[accID]['role']
        print(" ## USING ## %s--> %s, role %s, account originDefinition %s, config %s, copyAnsible to %s" %
              (type_in, svc_in, accountRole, accID, config, sendto))
        print(" !!! !! to assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVR.yaml' to True or False as needed")
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        aconnect = awsConnect(
            accID, origin['eID'], origin['role_definer'], sts_client, region)
        aconnect.connect()

        if type_in == "-CF":
            cm = CloudFrontMolder("ansible")
            cm.cfront_describe(svc_in, aconnect, origin, global_accts, sendto)
            print("CF here")
        elif type_in == "-L":
            lm = LambdaMolder("ansible")
            lm.lambda_describe(svc_in, aconnect, origin, global_accts,
                               triggers, sendto, targetAPI, fullUpdate)
        elif type_in == "-G":
            lm = ApiGatewayMolder("ansible")
            lm.describe_GatewayALL(
                svc_in, aconnect, origin, global_accts, triggers, sendto, targetAPI, fullUpdate)

        logger.info("Finished")
        print("--- %s seconds ---" % (time.time() - start_time))
