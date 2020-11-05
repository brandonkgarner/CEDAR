
# import re
# import ValueError
import os
# import time
# import random
# from time import sleep
# from datetime import datetime, date
# import json
# import shutil
from shutil import copyfile
import distutils
# from distutils import dir_util
# import boto3
# from botocore.exceptions import ClientError
# import sys

# from microUtils import writeYaml,loadServicesMap, loadConfig, ansibleSetup
from microUtils import ansibleSetup
from microUtils import writeYaml, serviceID, loadServicesMap
# from microUtils import writeJSON
# from microUtils import loadServicesMap
from microUtils import account_replace
# from microUtils import describe_role

# sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(__file__)


class DynamoMolder():
    origin = None

    def __init__(self, directory):
        global dir_path
        temp = "%s/%s" % (dir_path, directory)
        self.temp = temp
        if not os.path.exists(temp):
            os.makedirs(temp)
        else:
            print(" directory %s already exists... remove or change name." % temp)

    def get_Dynamolambdas(self, table, aconnect, nextMarker=None):
        client = aconnect.__get_client__('lambda')
        if nextMarker:
            functions = client.list_functions(Marker=nextMarker)
        else:
            functions = client.list_functions()
        all_Lambdas = functions['Functions']
        if 'NextMarker' in functions:
            nextMarker = functions['NextMarker']
            lambdas = self.get_Dynamolambdas(table, aconnect, nextMarker)
            all_Lambdas = lambdas + all_Lambdas

        filtered = []
        for ls in all_Lambdas:
            lname = ls['FunctionName']
            eventMaps = client.list_event_source_mappings(
                FunctionName=lname)['EventSourceMappings']

            for event in eventMaps:
                source = event['EventSourceArn']
                if 'dynamodb' in source and table in source:
                    ls.update(event)
                    filtered.append(ls)
                    break
        return filtered

    def scan_lambdaTriggers(self, target, aconnect, arn):
        lambdas = self.get_Dynamolambdas(target, aconnect)
        triggers = []
        for lb in lambdas:
            print(lb)
            # namein = lb['functionArn'].split('function:')[1]
            namein = lb['FunctionName']
            event_source = lb['EventSourceArn'].split('/')[:2]
            event_source = "/".join(event_source)
            obj = {"function_name": namein, "state": "present", "event_source": event_source,
                   "function_arn": lb['FunctionArn'], "source_params": None}
            state = True if lb['State'] == 'Enabled' else False
            source_params = {"source_arn": event_source, "enabled": state,
                             "starting_position": "LATEST", "batch_size": lb['BatchSize']}
            additionalParams = ["MaximumBatchingWindowInSeconds", "ParallelizationFactor", "DestinationConfig",
                                "MaximumRecordAgeInSeconds", "BisectBatchOnFunctionError", "MaximumRetryAttempts"]
            for add in additionalParams:
                if add in lb:
                    source_params.update({add: lb[add]})
            obj.update({"source_params": source_params})
            obj['TableName'] = target
            triggers.append(obj)
        return triggers


# - name: DynamoDB stream event mapping
#   lambda_event:
#     state: "{{ state | default('present') }}"
#     event_source: stream
#     function_name: "{{ function_name }}"
#     alias: Dev
#     source_params:
#       source_arn: arn:aws:dynamodb:us-east-1:123456789012:table/tableName/stream/2016-03-19T19:51:37.457
#       enabled: True
#       batch_size: 100
#       starting_position: TRIM_HORIZON
#   with_items: "{{ project.dynamodbs }}"
#   when: '{{ item.hash_key_name is not defined and item.read_capacity is defined and not (item.state=="absent")}}'


    def dynamoSimpleTypes(self, type):
        if "s" in type.lower():
            return "STRING"
        if "n" in type.lower():
            return "NUMBER"
        if "b" in type.lower():
            return "BINARY"
        return "STRING"

    def behavior_describe(self, target, aconnect):
        #client = boto3.client('lambda')
        client = aconnect.__get_client__('dynamodb')
        originID = None
        triggers = []
        dTable = client.describe_table(TableName=target)['Table']
        indexes = []
        TableArn = dTable['TableArn']
        TableId = dTable['TableId']
        TableStatus = dTable['TableStatus']

        keysIn = {}
        attDefined = {item['AttributeName']: self.dynamoSimpleTypes(
            item['AttributeType']) for item in dTable['AttributeDefinitions']}
        for ks in dTable['KeySchema']:
            namein = ks['AttributeName']
            if 'HASH' in ks['KeyType']:
                keysIn.update({"hash_key_name": namein,
                               "hash_key_type": attDefined[namein]})
            else:
                keysIn.update({"range_key_name": namein,
                               "range_key_type": attDefined[namein]})

        pr = dTable['ProvisionedThroughput']
        read_capacity = pr['ReadCapacityUnits']
        write_capacity = pr['WriteCapacityUnits']

        if 'LocalSecondaryIndexes' in dTable:
            for kl in dTable['LocalSecondaryIndexes']:  # all , include, keys_only
                lso = {"name": kl['IndexName'], "type": None,
                       "hash_key_name": None, "range_key_name": None}
                for ks in kl['KeySchema']:
                    LSI_namein = ks['AttributeName']
                    if 'HASH' in ks['KeyType']:
                        lso.update({"hash_key_name": LSI_namein,
                                    "hash_key_type": attDefined[LSI_namein]})
                    else:
                        lso.update({"range_key_name": LSI_namein,
                                    "range_key_type": attDefined[LSI_namein]})
                # print(dTable)
                lpj = kl['Projection']
                lpj_type = lpj['ProjectionType']
                lso['type'] = lpj_type.lower()
                if 'NonKeyAttributes' in lpj:
                    lso_keys = lpj['NonKeyAttributes']
                    if lso_keys:  # projections selected
                        lso.update({"includes": lso_keys})
                indexes.append(lso)
        if 'GlobalSecondaryIndexes' in dTable:
            for gl in dTable['GlobalSecondaryIndexes']:
                gso = {"name": gl['IndexName'], "type": None,
                       "hash_key_name": None, "range_key_name": None}
                for ks in gl['KeySchema']:
                    namein = ks['AttributeName']
                    if 'HASH' in ks['KeyType']:
                        gso.update(
                            {"hash_key_name": ks['AttributeName'], "hash_key_type": attDefined[namein]})
                    else:
                        gso.update(
                            {"range_key_name": ks['AttributeName'], "range_key_type": attDefined[namein]})
                lpj = gl['Projection']
                lpj_type = lpj['ProjectionType']
                gso['type'] = "global_%s" % (lpj_type.lower())
                if 'NonKeyAttributes' in lpj:
                    gso_keys = lpj['NonKeyAttributes']
                    if gso_keys:  # projections selected
                        gso.update({"includes": gso_keys})
                indexes.append(gso)
        if 'StreamSpecification' in dTable:
            streamSepcs = dTable['StreamSpecification']
            LatestStreamArn = dTable['LatestStreamArn']
            print(" ... getting all triggers for Table:%s" % (target))
            triggers = self.scan_lambdaTriggers(target, aconnect, TableArn)

        else:
            print(" ...[W] No triggers for Table:%s" % (target))
        if 'SSEDescription' in dTable:
            SSEDescription = dTable['SSEDescription']
        obj = {
            'name': target,
            'id': TableId,

            'status': TableStatus,
            'state': 'present',
            'arn': TableArn,
            'read_capacity': read_capacity,
            'write_capacity': write_capacity,
            # 'triggers': triggers
        }
        if 'StreamSpecification' in dTable:
            obj.update({'streamspec': streamSepcs})

        if keysIn:
            obj.update(keysIn)
        if indexes:
            obj.update({"indexes": indexes})
        return obj, triggers

    # if lambda triggers found deploy and then attach after deployment.

      # - name: NamedIndex
      #   type: 'all', 'global_all', 'global_include', 'global_keys_only', 'include', 'keys_only'
      #   hash_key_name: PK
      #   range_key_name: create_time
      #   includes:
      #     - other_field
      #     - other_field2
      #   read_capacity: 10
      #   write_capacity: 10
# ['hash_key_type', 'range_key_name', 'range_key_type',

    def define(self, target, aconnect, accountOrigin, accounts=[], sendto=None):
        self.origin = accountOrigin
        acctID = accountOrigin['account']
        assumeRole = accountOrigin['assume_role']
        tableObj, triggers = self.behavior_describe(target, aconnect)
        # for trigger in triggers:
        #     trigger
        # acctTitle = None
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

        taskMain, rootFolder, targetLabel = ansibleSetup(
            self.temp, target, True)
        taskWithFiles = [
            {"import_tasks": "../aws/sts.yml", "vars": {"project": '{{ project }}'}},
            {"import_tasks": "../aws/cr_dynamodb.yml",
                "vars": {"project": '{{ project }}'}}
        ]
        taskRaw = taskMain[0]
        taskMain = [taskRaw] + taskWithFiles
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
        if 'services_map' in accountOrigin:
            mapfile = accountOrigin['services_map']
            serviceMap = loadServicesMap(mapfile, None)
        for akey, account in accounts.items():
            if acctID == akey:
                acctTitle = account['title']
            eID = serviceID(akey, None, account['all'], serviceMap)
            accDetail = {
                "account_id": akey,
                "env": account['title'],
                "error_path": error_path,
                "skipping": skipping,
                "role_duration": 3600,
                "region": "us-east-1",
                "eid": eID
            }
            if assumeRole:
                accDetail.update({"cross_acct_role": account['role']})
            defaultVar = {targetLabel: accDetail}

            defaultVar[targetLabel].update({"dynamodbs": [tableObj]})
            if triggers:
                defaultVar[targetLabel].update({"dynamo_triggers": triggers})

            option = "main_%s" % account['all']
            mainIn = "%s/%s/%s" % (rootFolder, 'defaults', option)
            writeYaml(defaultVar, mainIn)
            account_replace("%s.yaml" % mainIn, str(acctID), str(akey))

        if sendto:
            print(" .... creating a main.yaml for ansible using dev")
            opt = "main_%s.yaml" % accountOrigin['all']
            src = "%s/%s/%s" % (rootFolder, 'defaults', opt)
            opt2 = "main.yaml"
            dst = "%s/%s/%s" % (rootFolder, 'defaults', opt2)
            copyfile(src, dst)
            print(" -------==------===---- COPY START....")
            print(" sending to %s. from %s" % (sendto, rootFolder))
            distutils.dir_util.copy_tree(rootFolder, sendto)
            ansibleRoot = sendto.split('roles/')[0]
            targets = ['%s' % target]
            rootYML = [{"name": "micro modler for lambda-%s" % target,
                        "hosts": "dev",
                        "remote_user": "root",
                        "roles": targets}]
            # ansibleRoot
            writeYaml(rootYML, ansibleRoot, target)
        return acctID, target, acctTitle, True


if __name__ == "__main__":
    dm = DynamoMolder()
    dm.define()
