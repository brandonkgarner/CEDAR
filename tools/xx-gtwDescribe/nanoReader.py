#!/usr/bin/python
import awsconnect
from microUtils import writeYaml, writeJSON, account_replace, loadServicesMap, loadConfig, ansibleSetup, serviceID
#from microUtils import writeYaml, writeJSON, account_replace, loadServicesMap, loadConfig, ansibleSetup
#from microFront import CloudFrontMolder
from microGateway import ApiGatewayMolder
import logging
import os
import time
import random
from datetime import datetime
from datetime import timedelta
import yaml

import random
import string
import math

import zipfile
import boto3
#from pygit import init, add, commit, push


class GwyReader():

    def __init__(self, bucket, bucketRoot=None):
        self.bucket = bucket
        self.bucketRoot = ""
        if bucketRoot:
            self.bucketRoot = bucketRoot

    def zipFiles():
        pass

    def s3_send(self, gatewayName, files, aconnect):
        client = aconnect.__get_client__('s3')
        now = datetime.utcnow()
        timeDir = now.strftime("%s")
        if self.bucketRoot:
            fkey = '%s/%s' % (self.bucketRoot, gatewayName)
        else:
            fkey = gatewayName
        key = '%s/%s' % (fkey, timeDir)
        print(key)
        for file in files:
            filename = os.path.basename(file)
            client.upload_file(file, self.bucket, "%s/%s" % (key, filename))

        # get list and if more than 100 delete older ones

        s3 = boto3.resource('s3')
        gBucket = s3.Bucket(self.bucket)
        # if blank prefix is given, return everything)
        # bucket_prefix="/some/prefix/here"

        objs = gBucket.objects.filter(Prefix=fkey)

        # if len(objs)>100:
        windowDays = 2
        now = int(math.ceil(time.time()))
        past = datetime.now() - timedelta(days=int(windowDays))
        spast = past.strftime('%s')
        for obj in objs:
            path, filename = os.path.split(obj.key)
            time2 = path.split("/")[-1:][0]
            if int(time2) < int(spast):
                print("to delete...")
                print(obj.key)
                client.delete_object(Bucket=self.bucket, Key=obj.key)

    def s3_read(self, file):
        BUCKET_NAME = self.bucket  # replace with your bucket name
        KEY = 'my_image_in_s3.jpg'  # replace with your object key
        s3 = boto3.resource('s3')
        try:
            s3.Bucket(BUCKET_NAME).download_file(KEY, 'my_local_image.jpg')
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                print("The object does not exist.")
            else:
                raise

    def map_dynoType(self, typeIn):
        # print("..........")
        # print(typeIn)
        if typeIn in 'string':
            return 'S'
        if typeIn in 'number':
            return 'N'
        if typeIn in 'boolean':
            return 'BOOL'
        if typeIn in 'array':
            return 'L'
        if typeIn in 'object':
            return 'M'

    def randomLetter(self, used='5'):
        randm = random.choice(string.ascii_lowercase)
        if used in randm:
            randm = self.randomLetter(used)
        return randm

    def outMap_Dynamo(self, key, parent, schema, used='5'):
        oType = schema['type']
        oItems = schema['items']
        allItems = ''
        lastIter = key
        allrndm = ''
        for k, v in oItems.items():
            name = k
            values = v
            if len(v) > 1:
                if oType in 'array':
                    start = "["
                    fin = "]"
                else:
                    start = "{"
                    fin = "}"
                randm = self.randomLetter(used)
                nIter = 'elem%s' % (randm)
                allallrndm = allrndm+randm
                #begin='\n "%s":%s'%(name,start)
                init = '\n "%s":%s' % (name, start)
                dynoType = self.map_dynoType(oType)
                bb = " \n #foreach($%s in $%s.%s.%s){\n" % (
                    nIter, parent, name, dynoType)
                m_items = self.outMap_Dynamo(nIter, nIter, values, allallrndm)
                # m_items=''.join(m_item.rsplit(",",1))
                #middle='"%s": %s '%(name, m_items)
                end = "}#if($foreach.hasNext),#end   \n #end"
                ee = "\n%s," % (fin)
                # final="%s%s%s%s%s"%(begin,bb,middle,end,ee)
                final = "%s%s%s%s%s" % (init, bb, m_items, end, ee)
                # lastIter=
            else:
                dynoType = self.map_dynoType(values['type'])
                final = '"%s": "$%s.%s.%s", \n' % (name, key, name, dynoType)
            allItems = allItems+final
        return ''.join(allItems.rsplit(",", 1))

    def output_Template(self, apiName, target):
        kParent = "inputRoot"
        elem = 'elem'
        aItems = ''
        ends = ''
        apiClient = boto3.client('apigateway')
        lm = ApiGatewayMolder("ansible", True)
        schema = lm.describe_modelInTarget(
            apiClient, apiName, target, 'dynamodb')
        #{  "type":"object",   "items":{    "portalid":{"type":"string"}   }      }
        if schema['type'] in 'array':
            aItems = '\n"items": ['
            ends = "\n]"
        begin = "#set($%s = $input.path('$')) \n{ %s \n #foreach($%s in $%s.Items) { \n" % (
            kParent, aItems, elem, kParent)
        mapped = self.outMap_Dynamo(elem, elem, schema)
        end = "\n}#if($foreach.hasNext),#end   \n #end"
        ee = "\n}"
        final = "%s%s%s%s%s" % (begin, mapped, end, ends, ee)
        last = str.replace(final, '\n', '\r\n')
        print("        ")
        print("        ")
        print(last)
        print("        ")
        print("        ")

    def sendtoGit(self, file1, file2):
        repoPath = '/tmp/nu'
        repoPath = 'GatewayBackups/microUtils.py'
        init(repoPath)
        # add(['/tmp/nu/defaults_main.yaml'])
        os.chdir(repoPath)
        add(files)
        commit("time to add from lambda", author="lambdaDev")
        url = "https://github.com/ClaimRuler/GatewayBackups.git"
        push(url, username=uname, password=upass)

        # github info
        # user = 'jeffdonthemic'
        # password = "secrets.password"
        # repo = 'github-pusher'
        # commitMessage = 'Code commited from AWS Lambda!'

        # repo = git.Repo("my_repository")
        # repo.git.add("bla.txt")
        # #repo.git.commit("my commit description")
        # repo.git.commit('-m', 'test commit', author='sunilt@xxx.com')
        # repo.git.pull('origin', new_branch)
        # repo.git.push('origin', new_branch)


def lambda_handler(event, context):
    # TODO implement
    test = False
    if test:
        gy = GwyReader('cr-lambda-dev', 'timemachine')
        aconnect = type('obj', (object,), {'__get_client__': boto3.client})
        gy.s3_send('NU', [], aconnect)
        return 'nada'
    if "action" in event:
        model = event['target']
        ops = event['options']
        api = ops['api']
        # {"action":"template","target":"claims","options":{"api":"ClaimRuler"}}

        gy = GwyReader('', '')
        mapped = gy.output_Template(api, model)
        return mapped

    else:
        api = "ClaimRuler"
        if 'api' in event:  # coming from apiGateway
            api = event['api']
        main(api)  # cr-lambda-dev
    return 'api Saved %s' % api


def main(api=None):
    start_time = time.time()
    isLambda = True
    jumpRole = False
    fullUpdate = False
    dir_path = '/tmp'
    config = 'ENVRFIG.yaml'
    svc_in = targetAPI = api
    sendto = '/tmp/%s' % targetAPI

    bucket = os.environ['bucket']
    bucketRoot = os.environ['initKey']
    g_reader = GwyReader(bucket, bucketRoot)

    logging.basicConfig(format='%(asctime)-15s %(message)s')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    logger.info("Started")
    print("  ..... INIT..... 0002")

    fullpath = config
    origin, global_accts = loadConfig(fullpath)
    triggers = origin['triggers']
    if jumpRole:
        accountRole = global_accts[accID]['role']
        region = origin['region']
        accID = origin['account']
        print(" ## USING ## %s--> %s, role %s, account originDefinition %s, config %s, copyAnsible to %s" %
              (type_in, svc_in, accountRole, accID,  config, sendto))
        print(" !!! !! to assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVRFIG.yaml' to True or False as needed")

        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
        if 'eID' in origin:
            eID = origin['eID']
        if 'services_map' in origin:
            mapfile = origin['services_map']
            eID = serviceID(origin['account'], mapfile, origin['all'])

        aconnect = awsConnect(
            accID, eID, origin['role_definer'], sts_client, region)
        aconnect.connect()
    else:
        aconnect = type('obj', (object,), {'__get_client__': boto3.client})

    lm = ApiGatewayMolder("ansible", isLambda)
    file_tasks, file_defaults = lm.describe_GatewayALL(
        svc_in, aconnect, origin, global_accts, triggers, sendto, targetAPI, fullUpdate)
    #pushFiles(file_tasks, file_defaults)
    g_reader.s3_send(targetAPI, [file_tasks, file_defaults], aconnect)
    logger.info("Finished")

    print("--- %s seconds ---" % (time.time() - start_time))


if __name__ == '__main__':
    main()
