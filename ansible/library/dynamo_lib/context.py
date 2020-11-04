import boto3

from auditMeth import printColor

from auditMeth import setAnsible

class ProviderContext(object):

    _provider_name = ''



    def __init__(self, session, account_id,mthread, ansible):

        """

        :type session: boto3.Session
        """
        self._report_items = []
        self._session = session
        self._resources = {}
        self._clients = {}
        self._region = session.region_name if session != None else None
        self._env = account_id
        self._lfound = []
        self._recursive=True
        self._multiThread=mthread
        self._ansible=ansible
        setAnsible(ansible)

    @staticmethod
    def assumedCredentials(stsClient, externalID, accountID):
        assumedRoleObject = stsClient.assume_role(
            RoleArn="arn:aws:iam::%s:role/Cross_Deployer" % (str(accountID)),
            RoleSessionName="AssumeAdministratorRole",
            ExternalId=externalID)
        # ExternalId=global_accounts[(accountID)]['eID'])
        return assumedRoleObject['Credentials']

    def printer(self, msg):
        if not self._ansible:
            print (msg)

    def printcolor(self, msg):
        if not self._ansible:
            printColor (msg)
    def lists(self):
        pass

    def missing(self):
        pass

    def item(self):
        pass

    def define(self, item):
        pass

    def getRecords(self, item):
        pass


    def UpdateTables(self, dynoObj, aconnect, targetEnv, applyChanges=False, override=False):
        pass

    def getHeader(self, item):
        pass
    def updateMain(self,item):
        pass
    def tableUpdate(self,item):
        pass
    def tableGetAbsent(self, item):
        pass
    def tableDelete(self,item):
        pass
    def tableDefine(self,item):
        pass
    def rowAdd(self,item):
        pass
    def rowsBatchAdd(self,item):
        pass
    def getAbsentColumns(self,item):
        pass

    def incrementCount(self,account):
        account['count']+=1
        return account['count']
    def _setRecursive(self,recurse):
        self._recursive=recurse
    def __set_both__(self, region,acct, client,resource,service=""):
        self._region=region
        self._env = acct
        if service =="":
            service = self._provider_name
        if service not in self._resources:
            self._resources[service]= resource
        if service not in self._clients:
            self._clients[service]=client


    def __get_resource__(self, service=""):
        if service == "":
          service = self._provider_name
        if service not in self._resources:
          self._resources[service] = self._session.resource(service)
        return self._resources[service]

    def __get_client__(self, service=""):
        if service == "":
          service = self._provider_name
        if service not in self._clients:
          self._clients[service] = self._session.client(service)
        return self._clients[service]

    def __str__(self):
        return '%s Provider Context' % self._provider_name

class FormatContext(object):
    _extension=''


    def __init__(self, filepath,ansible):

        self._filepath = filepath
        self._formats = {}
        self._ansible = ansible
        setAnsible(ansible)

    def fileRead(self, item):
        pass
    def dbRead(self, item):
        pass
    def loadDeltas(self,section,envs,target,index):
        pass
    def load(self,section,envs,target,index):
        pass

    def write(self, item, option=''):
        pass
    def dump(self, item):
        pass

    def printer(self, msg):
        if not self._ansible:
            print (msg)

    def printcolor(self, msg):
        if not self._ansible:
            printColor (msg)

    def __get_formater__(self, formater=""):
        if formater == "":
            formater = self._extension
        if formater not in self._formats:
          self._formats[formater] = self._session.resource(formater)
        return self._formats[formater]

    def __str__(self):
        return '%s Format Context' % self._extension