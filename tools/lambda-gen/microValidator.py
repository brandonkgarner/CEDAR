import logging
import re
#import ValueError
import os,time, random
from time import sleep
from datetime import datetime, date
import json
import shutil
from shutil import copyfile
import distutils
from distutils import dir_util
import boto3
from botocore.exceptions import ClientError
import sys

from microUtils import writeYaml, writeJSON, account_replace, loadServicesMap, loadConfig, ansibleSetup
from microUtils import  describe_role

from hashlib import md5

#sudo ansible-playbook -i windows-servers CR-Admin-Users.yml -vvvv
dir_path = os.path.dirname(__file__)


class ValidationMolder():
    origin = None

    def __init__(self, directory):
        global dir_path
        temp="%s/%s"%(dir_path,directory)
        self.temp=temp
        if not os.path.exists(temp):
            os.makedirs(temp)
        else:
            print (" directory %s already exists... remove or change name."%temp)

    def lambda_compare(self, lambdas, aconnect ):
        #client = boto3.client('lambda')
        client = aconnect.__get_client__('lambda')
        lamdas = client.list_functions(
            MaxItems=49
        )['Functions']

        ll = {}
        for fnt in lamdas:
            target=fnt['FunctionName']
            obj={
            'Role':fnt['Role'],
            'CodeSize':fnt['CodeSize'],
            'Timeout':fnt['Timeout'],
            'MemorySize':fnt['MemorySize'],
            'LastModified':fnt['LastModified'],
            'CodeSha256':fnt['CodeSha256'],
            'Environment':fnt['Environment']
            }
            ll.append({target: obj})


            # m = md5()
            # hexIn=None
            # with open(zipName, "rb") as f:
            #     data = f.read() #read file in chunk and call update on each chunk if file is large.
            #     m.update(data)
            #     hexIn=m.hexdigest()
            lams.update({target:hexIn})
    def api_compare(self):
        #resource
        #method
        #model
        #
        pass
    def dynamo_compare(self):
        pass
        #table
        #LSI
        #GSI









if __name__ == "__main__":
    found=None
    length=0
    start_time = time.time()
    try:
        sys.argv[1]
        found=sys.argv
        length=len(found)
    except:
        found = "help"

#python microValidator.py dev "test,stage" ENVR.yaml
#
    if "help" in found and length<3:
        print(" ************************************************************")
        print("      Try using the following PSUEDO after *CONFIG.yaml is correct :")
        print("           python microValidator.py dev 'test,stage' ENVR.yaml")
        print(" ************************************************************")
        exit()
    else:
        print ("  ..... INIT..... 0001 ")

        source_environment = str(sys.argv[1]).strip()
        target_environments = str(sys.argv[2]).strip().split(",")
        config = str(sys.argv[3]).strip()
        #config='ENVR.yaml'


        logging.basicConfig(format='%(asctime)-15s %(message)s')
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        logger.info("Started")
        print ("  ..... INIT..... 0002")

        fullpath="%s/%s"%(dir_path,config)
        origin, global_accts=loadConfig(fullpath)
        triggers = origin['triggers']
        if triggers is None:
            raise ValueError("[E] config file [ %s ] did not load correctly.. PLEASE check / fix and try again"%(fullpath))
        accID=origin['account']
        region =  origin['region']
        accountRole=global_accts[accID]['role']
        print (" ## USING ## %s--> %s, role %s, account originDefinition %s, config %s, copyAnsible to %s"%(type_in,svc_in, accountRole, accID,  config, sendto))
        print (" !!! !! to assume <cross_acct_role> ROLE make sure you set 'assume_role' in 'ENVR.yaml' to True or False as needed")
        awsconnect.stsClient_init()
        sts_client = awsconnect.stsClient
    dm=ValidationMolder()
    aconnect = awsConnect( accID, origin['eID'], origin['role_definer'], sts_client, region)
    aconnect.connect()









