from context import ProviderContext
from pipeline_define import SetupPipelineDefinition
import botocore
from boto3.dynamodb import types
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import string
import copy

import time


CREATE = 1
UPDATE = 2
DELETE = 3
IGNORE = 4
ERROR = 5
MATCH = 6

dynamo_resource=None
provider_name=None


class DB_pipeline(ProviderContext):
    _provider_name = 'datapipeline'
    def __init__(self, session, account_id, pathSetup):
        super(DB_pipeline, self).__init__(session, account_id)
        self._pipelineID=None
        self._name="manage large dynamo dataSets"
        self._pipelineDefinition={}
        self._pipelineDefinition = SetupPipelineDefinition(pathSetup)

    def list(self,marker=''):
        client = self.__get_client__(self._provider_name)
        response = client.list_pipelines(
            marker=marker
        )
        return response

    def pipeExists(self,pipe_name,marker=''):
        apipes = self.list(marker)
        found = False
        for p in apipes['pipelineIdList']:
            pname = apipes['name']
            if pipe_name == pname:
                found = True
                return True
        if not found and apipes['hasMoreResults']:
            found =self.pipeExists(pipe_name,apipes['marker'])
        return found

    def define(self,ids):
        client = self.__get_client__(self._provider_name)
        response = client.describe_pipelines(
            pipelineIds = ids
        )
        return response['pipelineDescriptionList']

    def getPipeline(self, name):
        exists = self.pipeExists(name)
        if not exists:
            self.create(name)

    def create(self,name):
        client = self.__get_client__(self._provider_name)

        pipeline_name = 'dynamo-setup-' + str(int(time.time()))
        response = client.create_pipeline(  name=self._name, uniqueId= pipeline_name )
        self._pipelineID = response['pipelineId']


        #client.get_waiter('pipeline_exists').wait(uniqueId=uID)
        print ('pipeline created ', name)
        return response['pipelineId']

    def setDefinition(self, name):
        client = self.__get_client__(self._provider_name)
        parameter_values = self.pipeline_definition.get_setup_pipeline_parameter_values()
        # for param in parameter_values:
        #     if param['id'] == 'myRdsEndpoint':
        #         param['stringValue'] = self.rds_endpoint

        client.put_pipeline_definition(pipelineId=self.pipeline_id,
                                       pipelineObjects=self.pipeline_definition.get_setup_pipeline_objects(),
                                       parameterValues=parameter_values)

    def getDefinition(self, name):
        client = self.__get_client__(self._provider_name)
        response = client.get_pipeline_definition(
            pipelineId = self._pipelineID )
        for obj in response['pipelineObjects']:
            if obj['name'] == name:
                return obj
        return None

    def activate(self):
        client = self.__get_client__(self._provider_name)
        client.activate_pipeline(pipelineId=self.pipeline_id)

    def status(self):
        client = self.__get_client__(self._provider_name)
        # check pipeline status
        return self._check_pipeline_state(client)

    def run(self, name):
        self.create(name)
        self.setDefinition(name)
        self.activate()
        self.status()

        # TODO: added for each dynamo table to import  AND EMRActivitY ==
        #
        # {
        #     "writeThroughputPercent": "#{myDDBWriteThroughputRatio}",
        #     "name": "DDBDestinationTable",
        #     "id": "DDBDestinationTable",
        #     "type": "DynamoDBDataNode",
        #     "tableName": "#{myDDBTableName}"
        # },

        ######  TODO: AND EMR ACTIVITY

        # {
        #     "output": {
        #         "ref": "DDBDestinationTable"
        #     },
        #     "input": {
        #         "ref": "S3InputDataNode"
        #     },
        #     "maximumRetries": "2",
        #     "name": "TableLoadActivity",
        #     "step": "s3://dynamodb-emr-#{myDDBRegion}/emr-ddb-storage-handler/2.1.0/emr-ddb-2.1.0.jar,org.apache.hadoop.dynamodb.tools.DynamoDbImport,#{input.directoryPath},#{output.tableName},#{output.writeThroughputPercent}",
        #     "runsOn": {
        #         "ref": "EmrClusterForLoad"
        #     },
        #     "id": "TableLoadActivity",
        #     "type": "EmrActivity",
        #     "resizeClusterBeforeRunning": "true"
        # },