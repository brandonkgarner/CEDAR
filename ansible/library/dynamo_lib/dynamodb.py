from context import ProviderContext

import botocore
from boto3.dynamodb import types
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import string
import copy
import time

import multiprocessing as mp
import multiprocessing.dummy as mpd

from auditMeth import rs_3
from auditMeth import namingCrud
from auditMeth import nameCheck
from auditMeth import convertTypes
from auditMeth import generateHeader
from auditMeth import generateRow
from auditMeth import convertAcceptedRowValue

CREATE = 1
UPDATE = 2
DELETE = 3
IGNORE = 4
ERROR = 5
MATCH = 6
ACTION_KEY = 'A C T I O N'

dynamo_resource=None
provider_name=None

moduleIN=None
def printer(msg):
    moduleIN.printer(msg)
def printColor(msg):
    moduleIN.printcolor(msg)


#Class used during the EXPORT of data READ ONLY!!!
class DB_dynamo(ProviderContext):
    _provider_name = 'dynamodb'
    def __init__(self, session, account_id,mthread, ansible):
        global moduleIN
        super(DB_dynamo, self).__init__(session, account_id,mthread, ansible)
        #self._provider_name = 'dynamodb'
        self.services = {
            'dynamo': {'rx': rs_3, 'owner': 'Ralph', 'ref': self}
        }
        self._regx=self.services['dynamo']['rx']
        self._owner=self.services['dynamo']['owner']
        moduleIN = self

    def _setBoth(self, region, acct, client, resource):
        super(DB_dynamo, self).__set_both__(region, acct,client,resource)
    # @staticmethod
    # def getServices():
    #     c = DBdynamo()
    #     return c.services

    def Lists(self):
        global provider_name, dynamo_resource
        rsrc = self.__get_client__()

        self._report_items = rsrc.list_tables()['TableNames']

        provider_name = self._provider_name
        dynamo_resource=self.__get_resource__()
        return self._report_items
    def Missing(self):
        pass


    def ItemDoc(self,tableName,keys,valueDict):
        printColor(['_____LISTING DynamoDB [] now....in .%s'%(self._region)])
        client = self.__get_client__()
        resource = self.__get_resource__()
        self._setRecursive(False)
        objs = []
        objs.append(['Name[%s]'%(self._provider_name), 'Audit', 'Owner', 'Status', 'Partition Key', 'indexes', 'totalReads', 'totalWrites','Columns'])
        pyObj={}

        table_present = client.describe_table(TableName = tableName)
        table = table_present['Table']
        tvalue = resource.Table(tableName)

        name, objd, pyd = dynamoDefine(None,table,self._owner,self._regx, self._env, self._recursive)
        self._lfound.append(name)
        pyObj[name]=pyd
        objs = objs +objd

        config = pyd['config']
        #MAKE SURE KEYS ARE FOUND!!
        keyFound = True
        for ckey in config['Partition Key']:
            if ckey not in keys:
                keyFound=False
                break

        #keyFound = False if ckey['AttributeName'] not in keys for ckey in config['Partition Key'] else True
        if not keyFound:
            return None,None,None
        #keys=['user','phone','email']
        #valueDict = {'user':'daniel','phone','984.256.2231','email':'aaa@sbc.edu'}
        results = self.tableConditionQuery(tvalue,keys,valueDict)

        recs, precs=RecordRows(results)
        pyObj.update({'rows': precs})
        objs = objs + recs
        return (self._lfound, objs, pyObj)


    def ItemTable(self,tableName):
        printColor(['_____LISTING DynamoDB [] now....in .%s'%(self._region)])
        client = self.__get_client__()

        objs = []
        objs.append(['Name[%s]'%(self._provider_name), 'Audit', 'Owner', 'Status', 'Partition Key', 'indexes', 'totalReads', 'totalWrites','Columns'])
        pyObj={}

        table = client.describe_table(TableName=tableName)['Table']
        name, objd, pyd=dynamoDefine(None,table,self._owner,self._regx, self._env, self._recursive)
        self._lfound.append(name)
        pyObj[name]=pyd
        objs = objs +objd
        return (self._lfound, objs, pyObj)

    def Item(self):
        printColor(['_____LISTING DynamoDB [] now....in .%s'%(self._region)])
        client = self.__get_client__()

        objs = []
        objs.append(['Name[%s]'%(self._provider_name), 'Audit', 'Owner', 'Status', 'Partition Key', 'indexes', 'totalReads', 'totalWrites','Columns'])
        pyObj={}

        p = mp.Pool()
        m = mp.Manager()
        q = m.Queue()

        for name in self._report_items:
            table=client.describe_table(TableName=name)['Table']
            if self._env in name or self._env.isdigit():
                self._lfound.append(name)
                #objd,pyd =dynamoDefine(table)
                getp=p.apply_async(dynamoDefine, (q, table, self._owner,self._regx, self._env, self._recursive))

                #objs= objs+objd
                #pyObj[name]=pyd

        p.close()
        p.join()
        while not q.empty():
            name, objd, pyd = q.get()
            printer('lll lll ll ===>%s'%name)
            objs = objs + objd
            pyObj[name]=pyd

        return (self._lfound,objs,pyObj)


    # find similar records
    def tableConditionQuery(self, tresource, sortKeys, record):
        results = None
        totkeys = len(sortKeys)

        if totkeys == 1:
            results = tresource.query(KeyConditionExpression=Key(sortKeys[0]).eq(record[sortKeys[0]]))
        elif totkeys == 2:
            results = tresource.query(KeyConditionExpression=Key(sortKeys[0]).eq(record[sortKeys[0]]) \
                                                             & Key(sortKeys[1]).eq(record[sortKeys[1]]))
        elif totkeys == 3:
            results = tresource.query(KeyConditionExpression=Key(sortKeys[0]).eq(record[sortKeys[0]]) \
                                                             & Key(sortKeys[1]).eq(record[sortKeys[1]]) \
                                                             & Key(sortKeys[2]).eq(record[sortKeys[2]]))
        elif totkeys == 4:
            results = tresource.query(KeyConditionExpression=Key(sortKeys[0]).eq(record[sortKeys[0]]) \
                                                             & Key(sortKeys[1]).eq(record[sortKeys[1]]) \
                                                             & Key(sortKeys[2]).eq(record[sortKeys[2]]) \
                                                             & Key(sortKeys[3]).eq(record[sortKeys[3]]))
        # results = tresource.query(KeyConditionExpression)
        # KeyConditionExpression = Key('year').eq(1992) & Key('title').between('A', 'L')
        return results





def dynamoDefine(que, item, _owner,_regx, _env,_recurse):
    name = item['TableName']
    #print ' ..'
    printer('   ===>dd defined for GSI %s'%name)
    audit, owner = nameCheck(_owner, name, _regx, _env)
    attributes = item['AttributeDefinitions']
    keys = item['KeySchema']
    clmns = '.'.join('%s:%s' % (aa['AttributeName'], aa['AttributeType']) for aa in attributes)
    pkey = '.'.join('%s:%s' % (t['AttributeName'], t['KeyType']) for t in keys)
    stat = item['TableStatus']
    indexes = reads = writes = 0
    obj = []
    pygdetail =pyldetail= None


    if 'LocalSecondaryIndexes' in item:
        lsi = item['LocalSecondaryIndexes']
        ldetail, pyldetail = globalSecondaryDetail(lsi,True)

    if 'GlobalSecondaryIndexes' in item:
        gsi = item['GlobalSecondaryIndexes']
        gdetail, pygdetail = globalSecondaryDetail(gsi)

        indexes = len(gsi)
        #reads, writes = getDynamoRU(item['GlobalSecondaryIndexes'])
    reads = item['ProvisionedThroughput']['ReadCapacityUnits']
    writes = item['ProvisionedThroughput']['WriteCapacityUnits']
    obj.append([name, audit, owner, stat, pkey, indexes, reads, writes, clmns])
    if pygdetail is not None or pyldetail is not None:
        objh=gsiHeader()
        obj = obj + objh
    if pyldetail is not None:
        obj=obj+ldetail
    if pygdetail is not None:
        obj = obj + gdetail
    printer( ' bbb')
    # obj.append(recs)
    # pyObj={}
    pyObj = {'gsi': pygdetail,'lsi':pyldetail,
             'config': {'audit': audit, 'owner': owner, 'status': stat, 'Partition Key': keys, 'indexes': indexes,
                        'totalReads': reads, 'totalWrites': writes, 'Columns': attributes}}
    if _recurse:
        recs, precs = Records(item)
        pyObj.update({'rows':precs})
        obj = obj + recs
    #print name
    #print pyObj
    if que:
        que.put((name, obj, pyObj))
    return (name, obj, pyObj)



def getDynamoRU( aUnits):
    writes = 0
    reads = 0
    for a in aUnits:
        writes += a['ProvisionedThroughput']['WriteCapacityUnits']
        reads += a['ProvisionedThroughput']['ReadCapacityUnits']
    return (reads, writes)


def Records( item):
    resource = dynamo_resource
    table = resource.Table(item['TableName'])
    records = table.scan(Limit=5)
    printColor(['_____....in .%s' % (item['TableName'])])
    # tot = records['Count']
    return RecordRows(records)

def RecordRows(rows):
    header = []
    pyObj = [{'keys': None, 'records': []}]
    objs = []
    objs.append(['DATA_HEADER[%s]' % (provider_name)])
    for row in rows['Items']:
        nh = generateHeader(row, header)
        pyObj[0]['records'].append(row)
        if nh:
            header = nh
            pyObj[0]['keys'] = nh
            objs.append(nh)
        objs.append(generateRow(row))
    if pyObj[0]['keys'] is None:
        pyObj = []
    objs.append(['NOTES[%s]' % (provider_name), 'other relevant info here'])
    return objs, pyObj

def gsiHeader():
    objs=[]
    GSINAME = 'Name[GSI]'
    objs.append(
            [GSINAME, 'Projected', 'ProjectionType', 'KeySchema', 'Status','Type', 'indexes', 'totalReads',
                'totalWrites'])

    return objs

def globalSecondaryDetail( aGsi, isLSI=False):
    # GHEAD = ['DATA_GSI']
    pyObj = {}
    objs = []
    # objs.append(GHEAD)
    #print '   2-====> GSI '
    #print aGsi
    indexType='GSI'
    for gi in aGsi:
        name = gi['IndexName']
        #print '   3-->gsi indexname::',name
        ptype = gi['Projection']['ProjectionType']
        indexes = 0
        projected = None
        pAttributes=None
        if ptype == 'INCLUDE':  ##LOOP THROUGH INDEXES TO INCLUDE
            pAttributes = gi['Projection']['NonKeyAttributes']
            indexes = len(pAttributes)
            projected = '.'.join('%s' % (t) for t in pAttributes)

        stat = gi.get('IndexStatus', None)
        #print '    4-->gsi  indexes::',stat

        keys = gi['KeySchema']
        pkey = '.'.join('%s:%s' % (t['AttributeName'], t['KeyType']) for t in keys)
        indexes = len(keys) + indexes
        rawGsi = {'KeySchema': keys, 'IndexName': name,
                  'Projection': {'ProjectionType': ptype, 'NonKeyAttributes': pAttributes}}

        if pAttributes is None:
            del rawGsi['Projection']['NonKeyAttributes']
            printer('  [W]-- gsi removing NonKeyAttributes %s'% name)
        #print '       5-->gsi again:::',rawGsi
        if not isLSI:
            _writes = {'ProvisionedThroughput':{'ReadCapacityUnits':gi['ProvisionedThroughput']['ReadCapacityUnits'],'WriteCapacityUnits':gi['ProvisionedThroughput']['WriteCapacityUnits']}}
            #del _writes['ProvisionedThroughput']['NumberOfDecreasesToday']
            rawGsi.update(_writes)
            writes = gi['ProvisionedThroughput']['WriteCapacityUnits']
            reads = gi['ProvisionedThroughput']['ReadCapacityUnits']
        else:
            indexType='LSI'
            writes=reads=None
        #print '               6--===>gsi reads',reads
        objs.append([name, projected, ptype, pkey, stat,indexType, indexes, reads, writes])
        pyObj[name] = {'Status': stat, 'Type':indexType,
                       'indexes': indexes, 'raw': rawGsi }
    return (objs, pyObj)
