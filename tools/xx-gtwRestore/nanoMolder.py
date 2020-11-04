#!/usr/bin/python
import os
import boto3
#import ansible.runner
from datetime import datetime, timedelta
import time
import math
from ansible import utils
from ansible import callbacks
from microUtils import writeYaml

import distutils
from distutils import dir_util


from collections import namedtuple

#import ansible.inventory
#import ansible.playbook
##
from ansible.parsing.dataloader import DataLoader
from ansible.vars import VariableManager
from ansible.inventory import Inventory
from ansible.executor.playbook_executor import PlaybookExecutor

# def convertTime(dtime):
#     return dtime.strftime('%s')
# def unix_time_millis(dt):
#     return (dt - epoch).total_seconds() * 1000.0

# def unix_aws_epoch(timeString):
#     utc_time = time.strptime(timeString, "%Y-%m-%dT%H:%M:%S.%fZ")
#     return timegm(utc_time) 
Main_method=None
Main_bucket=None
threadEvent=None
mRegion = None
configPath='auditCONFIG.yaml'
configName='auditCONFIG'
configFolder='ansible_deploy'
inLambda=True
accountID=None
Threaded_S3=None
Main_folder='process-tagging'

def ec2Enabled(current, code_zip, event, envs):
    ##create ecs and push code to run in ecs
    if not event.has_key('s3'):
        return ['[W] possible S3 call IGNORING...']
    ec2 = boto3.resource('ec2')
    client=boto3.client('ec2')
    iam = boto3.resource('iam')
    iam_client = boto3.client('iam')
    lbda = boto3.client('lambda')
    role_method = lbda.get_function(FunctionName=Main_method)['Configuration']['Role']
    roleUsed = role_method.split('/')[1]
    # print 'role above....'
    # roleIN= iam.Role(roleUsed)
    pName = 'CR_profile-Ansible'
    try:
        iprofile = iam.create_instance_profile(InstanceProfileName=pName)
    except:
        iprofile = iam_client.get_instance_profile(InstanceProfileName=pName)
    lroles = iprofile['InstanceProfile']['Roles']
    found = False
    for rIn in lroles:
        if roleUsed in rIn['RoleName']:
            found = True
            break
    if not found:
        iam_client.add_role_to_instance_profile(InstanceProfileName=pName, RoleName=roleUsed)

    ec2_ami = current.ec2_ami
    ec2_SubnetId = current.ec2_SubnetId
    ec2_SecurityGroupIds = current.ec2_SecurityGroupIds
    ec2_spot_price = current.ec2_spot_price
    ec2_type=current.ec2_type
    keep_servers= current.keep_servers
    zone = current.zone
    zones=current.zone_list
    ec2_disksize=current.ec2_disksize

    if zone==0:
        zone=random.choice(zones)
    if ec2_SubnetId:
        subnet = ec2.Subnet(ec2_SubnetId)
        zone = subnet.availability_zone

    keyFolder=current.s3_keyFolder



    lacct=[]

#for aID, e in envs.items():  WE ONLY DO ONE REGION AT A TIME!!!!!!!!
    account=aID
    ec2_Name = "CR-Ansible-%s-%s"%(account, mRegion)
    filters = [{'Name':'tag:Name', 'Values':[ec2_Name]},{'Name':'instance-state-name','Values':['running','pending']}]
    eC2backs=list(ec2.instances.filter(Filters=filters))
    if len(eC2backs)>0:

        if keep_servers:  # clear out all servers now
            print 'skipping %s as still found'%(aID)
            continue
        else:
            for et in eC2backs:
                et.terminate()

    try:
        key = current.s3_key % (account)
        s3 = boto3.resource('s3')
        s3.Object(Main_bucket, '%s/%s' % (keyFolder, key)).load()
        print ('[W] STOP EC2 CHILD redundant %s', account)
        continue
    except ClientError as e:
        if e.response['Error']['Code'] != "404":
            continue




    lacct.append(aID)
    #is there a server for this already?
    print '...starting ec2 instance...%s'%ec2_type
    blockMap=[]
    if ec2_disksize>0:
        print '....spot requested at price: %s'% ec2_spot_price
        blockMap=[ {
                    'Ebs': {
                        'VolumeSize': ec2_disksize,
                        'DeleteOnTermination': True,
                    },
                },
            ]
    userDATA = "#!/bin/bash \n aws s3 rm s3://%s/logs_%s_%s.txt\n yum install aws-cli -y \n aws s3 cp s3://%s/ansible_deploy/%s ~/nanoAnsible.zip \n yum install zip -y \n mkdir -p ~/nanoAnsible \n ls -la ~/ \n unzip ~/nanoAnsible.zip -d ~/nanoAnsible \n cd ~/nanoAnsible \n INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)\n \n aws ec2 create-tags --region %s  --resources $INSTANCE_ID --tags Key=%s,Value=%s Key=Name,Value=%s \n python -c 'import awsKHE_tags as aws; aws.ecsMASTER(\"%s\",\"%s\",\"%s\")' >> logs.txt 2>&1\n aws s3 cp logs.txt s3://%s/logs_%s_%s.txt \n echo '...terminating ec2 $INSTANCE_ID' \n echo $INSTANCE_ID \n %s ec2 --region %s terminate-instances --instance-ids $INSTANCE_ID" % (
            Main_bucket, account, mRegion,
            Main_bucket, code_zip,
            mRegion, 'DIVISION', 'CR',ec2_Name,
            account,event['s3']['bucket'], event['s3']['config'],
            Main_bucket, account, mRegion,
            'awsNO' if keep_servers else 'aws',
            mRegion)
    if ec2_spot_price >0:
        launchSpec={
                        'ImageId': ec2_ami,
                        'InstanceType': ec2_type,
                        'UserData': base64.b64encode(userDATA),
                        'Placement': {
                            'AvailabilityZone': '%s%s'%(mRegion,zone),
                        },


                        #'EbsOptimized': True,
                        'Monitoring': {
                            'Enabled': True
                        },
                        'SubnetId': ec2_SubnetId,
                        'IamInstanceProfile': {
                            'Name': pName
                        },
                        'SecurityGroupIds': [
                            ec2_SecurityGroupIds,
                        ]
                    }
        if len(blockMap) >0:
            launchSpec.update({ 'BlockDeviceMappings': blockMap })

        ec2in = client.request_spot_instances(
                    DryRun=False,
                    SpotPrice=str(ec2_spot_price),
                    ClientToken='string',
                    InstanceCount=1,
                    Type='one-time',
                    LaunchSpecification=launchSpec
                )

    else:
        print '....standard ec2 ondemand tyep: %s'% ec2_type
        ec2in = ec2.create_instances(
            # Use the official ECS image
            ImageId=ec2_ami,
            MinCount=1,
            MaxCount=1,
            BlockDeviceMappings=blockMap,
            SubnetId=ec2_SubnetId,
            SecurityGroupIds=[
                ec2_SecurityGroupIds,
            ],
            InstanceType=ec2_type,
            IamInstanceProfile={
                "Name": pName
            },
            UserData=userDATA
        # UserData="#!/bin/bash \n echo ECS_CLUSTER=" + cluster_name + " >> /etc/ecs/ecs.config"
        )
    # python -c 'import awsKHE_tags as aws; aws.ecsMASTER(acct,bucket,configpath)
    #python -c 'import awsKHE_tags as aws; aws.ecsMASTER("791949374647","kaplan-khe-dcs-tagging","dcs-config/auditCONFIG.yaml")'

    # UserData = "#!/bin/bash \n export AWS_ACCESS_KEY_ID=AKIAJRRU5AJT52UOG54Q\n export AWS_SECRET_ACCESS_KEY=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\n export AWS_DEFAULT_REGION=us-east-1\n yum install aws-cli -y \n aws s3 cp s3://%s/dcs-config/%s ~/tagger.zip \n yum install zip -y \n mkdir -p ~/tagger \n ls -la ~/ \n unzip ~/tagger.zip -d ~/tagger \n cd ~/tagger \n python -c 'import awsKHE_tags as aws; aws.ecsMaster(%s,%s,%s)' > logs.txt \n aws s3 cp file://logs.txt s3://%s/logs_%s_%s.txt \n INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)\n \n aws ec2 create-tags --resources $INSTANCE_ID --tags Key=Name,Value=%s \n echo '...terminating ec2 $INSTANCE_ID' \n echo $INSTANCE_ID \n aws2 ec2 terminate-instances --instance-ids $INSTANCE_ID" % (
    # Main_bucket, code_zip, accountID, event['s3']['bucket'], event['s3']['config'], Main_bucket, accountID, mRegion,
    # ec2_Name)

    return lacct


def ecsMASTER(account,bucket=None,config=None):
    #subprocess
    #die
    pass


def ansibleFinalSetup(rootFolder,target ):
    ansible_folders=["defaults","files","handlers","tasks","templates"]
    ############ COPY FILES TO TEMP FIRST  ##########
    for folder in ansible_folders:
            newFolder="%s/root_ansible/%s/%s"%(rootFolder,target,folder)
            if not os.path.exists( newFolder):
                os.makedirs(newFolder)

def move_resources(rootFolder,sendto):
    #### MOVING ROLES FILES
    crFrom=rootFolder
    Crsendto = "%s/%s"%(sendto,rootFolder)
    print (" sending to %s. from %s"%(Crsendto,crfolder))
    distutils.dir_util.copy_tree(crfolder, Crsendto)
    #### MOVING ASIBLE FILES
    print("moving ansible down to /tmp")
    distutils.dir_util.copy_tree('ansible', '%s/ansible'%sendto)



def load_playbook(bucket,rootkey,time, target,output):
    s3 = boto3.resource('s3')
    tasks = '%s/%s/%s/tasks_main.yaml'%(rootkey,target,time)
    defaults = '%s/%s/%s/defaults_main.yaml'%(rootkey,target,time)
    ansibleRoot='/tmp/root_ansible/'
    move_resources('root_ansible','/tmp')
    print("============ WRITTING TO TEMP -=[%s]========="%(ansibleRoot))
    s3.meta.client.download_file(bucket, key, '%sroles/%s/defaults/main.yaml'%(ansibleRoot,target) )
    s3.meta.client.download_file(bucket, key, '%sroles/%s/tasks/main.yaml'%(ansibleRoot,target)    )

    targets=['%s'%target]
    rootYML = [{"name": "nano modler for gateway-%s"%target, 
            "hosts":"dev", 
            "remote_user":"root",
                "roles":targets}]
    #ansibleRoot
    writeYaml(rootYML, ansibleRoot,"CR-%s"%target )
    print("============ WRITTING ROOT FILE -==========")

def lambda_handler(event, context):
    # TODO implement  
    if "restore" in event["action"]:
        api="ClaimRuler"    
        now=datetime.utcnow()
        timeRequested=now.strftime("%s")
        if 'api' in event:   #coming from apiGateway
            api =event['api']
        if "epoch" in event:
            timeRequested=event['epoch']
        main(api,timeRequested)#cr-lambda-dev
        # dtime=datetime.fromtimestamp(time)
        # old_timezone = pytz.timezone("US/Eastern")
        # old_timezone.localize(dtime)
        return {"success":True, "message":" recreated api %s based on time:%s "%(api,time)}
    elif "list" in event["action"]:
        return {"success":False, "message":" USE S3 API instead"}


def main(api,timeRequested):
    bucket=os.environ['bucket']
    rootkey=os.environ['initKey']
    rootTemp='/tmp'
    ansibleFinalSetup(rootTemp,api)
    load_playbook(bucket, rootkey,timeRequested, api, '/tmp')
    os.chdir('/tmp/root_ansible')
    out = run_playbook( playbook='CR-%s.yaml'%api, inventory=ansible.inventory.Inventory(['localhost']) )
    return(out)


if __name__ == '__main__':
    main()