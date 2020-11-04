from context import ProviderContext

import botocore
from boto3.dynamodb import types
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import string
import copy
import time


from auditMeth import printColor
from auditMeth import rs_3
from auditMeth import namingCrud
from auditMeth import nameCheck
from auditMeth import convertTypes
from auditMeth import convertAcceptedRowValue
from auditMeth import convertDynamoType
from auditMeth import generateHeader

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
## Class used during the IMPORT and Contrast/Compare of DATA
class DB_JuxtaDynamo(ProviderContext):

    _provider_name = 'dynamodb'

    def __init__(self, session, account_id, ansible):
        global moduleIN
        super(DB_JuxtaDynamo, self).__init__(session, account_id, ansible)
        #self._provider_name = 'dynamodb'
        self.services = {
            'dynamo': {'rx': rs_3, 'owner': 'Andrey', 'ref': self}
        }
        self._regx=self.services['dynamo']['rx']
        self._owner=self.services['dynamo']['owner']
        moduleIN = self

    def _setBoth(self, region, acct, client, resource):
        super(DB_JuxtaDynamo, self).__set_both__(region,acct, client,resource)
    # @staticmethod
    # def getServices():
    #     c = DBdynamo()
    #     return c.services




    def attributeDefinitions(self,config,xkema,pkeys, gsi,lsi):
        ## FIND ATTRIBUTES BASED ON KEYS in all INDEXES ##
        clmns = config['Columns']
        attributeDef =[]
        printer( '   --attributeDefinitions==-=--=-=+++ {}{}()()')
        for x in xkema:
            attFinal = self.attributeMapper(clmns,pkeys, x['AttributeName'])
            if attFinal is not None:
                attributeDef.append(attFinal)
        mgsi={}
        if gsi is not None:
            mgsi.update(gsi)
        if lsi is not None:
            mgsi.update(lsi)
        printer( mgsi)
        for g,e in mgsi.items():
            printer( '88888  eee 01 %s'%g)
            printer( e)
            printer( '88888  eee 02')
            keys=e['raw']['KeySchema']
            for k in keys:
                found = False
                for a in attributeDef:
                    printer( '    -----****')
                    printer( a)
                    printer( k)
                    printer( '        --------------****')
                    if a is None or k is None:
                        found = True
                        continue
                    if a['AttributeName'] ==k['AttributeName']:
                        found=True
                        break
                if not found:
                    attFinal = self.attributeMapper(clmns,pkeys, k['AttributeName'])
                    if attFinal is not None:
                        attributeDef.append(attFinal)

        return attributeDef

    def attributeMapper(self,columns,pkeys,key):
        for c in columns:
            if c['AttributeName'] == key:
                return c
        printer('  ==============  ============')
        printer( pkeys)
        printer( columns)
        printer('[E]  NONE FOUND in column MAP %s'%key)
        return None


    ###################################################################
    ### CREATES TABLE IF NOT PRESENT  THEN ADDS ALL NEEDED RECORDS ####
    ###################################################################
    ### adds action key if no action property found
    def tableRowModelReform(self,rows,config):
        global ACTION_KEY
        row_insert = []
        records = rows[0]['records']
        for row in records:
            if ACTION_KEY not in row:
                row.update({ACTION_KEY: 'insert'})
            row_insert.append(row)
            # deltas, pydeltas =self.addRow(None, row, nkeys, createit)

        defined = {'config': config, 'rows': rows}
        return (defined,row_insert)


    def tablePresent(self, tablename, config, pkeys, rowsIn, gsi,lsi, createit=False):
        resource = self.__get_resource__()
        client = self.__get_client__()
        tableIsnew = False
        ready =True
        ignore = False
        rows = copy.deepcopy(rowsIn)
        obj=[]
        pyObj = {'config':config,'rows':rows,'deltas':{}}


        #s=100/0

        updatedRows=[]
        addHeaders=[]
        #createit=False
        records = nkeys= None
        audit, owner = nameCheck('', tablename, self.services['dynamo']['rx'], 'None')
        if len(rows) > 0:
            records = rows[0]['records']
            nkeys = rows[0]['keys']
            addHeaders=['#DELTA']

            for key in nkeys:
                kkey = key.split(':')[0]
                addHeaders.append(kkey)
            if not createit:
                printer( "  ---looping 0000 %s"%addHeaders)
                if records is not None:
                    if len(records) > 0:
                        defined,row_insert=self.tableRowModelReform(rows, config)

                        # printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
                        # printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
                        # printer ("---> 003.  table2Update")
                        # printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
                        # printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
                        #deltas, pydeltas = self.table2Update(None, defined,nkeys, None,None, createit)
                        deltas, pydeltas = self.table2Update(None, defined, nkeys, createit)
                        if deltas is not None:
                            updatedRows.append(deltas)
        printer( '     001~~~~~~~~~~~~~~%s'%len(rows)  )
        #print '%s'%(updatedRows)
        printer('     002~~~~~~~~~~~~~~%s'% pkeys )
        printer( nkeys)

        #print rows
        #s = 100/0
        try:
            change = namingCrud(MATCH)
            response = client.describe_table(TableName = tablename)
            obj.append([ change, tablename, audit, owner, pkeys, config['totalReads'],
                                                   config['totalWrites'], config['Columns']])
            obj = obj +[addHeaders]
            obj = obj + updatedRows
            pyObj['deltas']['all']= change
            return (tableIsnew, ready, obj, pyObj, response)
        except botocore.exceptions.ClientError as e:
            #['DELTA', 'Name[%s]' % ('dynamodb'), 'Audit', 'Owner', 'Partition Key', 'totalReads', 'totalWrites']
            ready = False
            printColor(" [W]   DynamoDB table ------ %s ' does not appear to exist, creating...%s"%(tablename, createit) )

            xkema = pkeys
            if xkema[0]['KeyType'] != 'HASH':
                xkema.reverse()

            #print '   --.[[000]]', len(rows)
            #print nkeys
            #print '   B --.[[000]]'
            #print config['Columns']
            #print pkeys
            #print gsi
            #print ('         ************* tablename:: ',tablename)
            attr = self.attributeDefinitions(config, xkema,pkeys, gsi, lsi)
            #print attr
            #print '  [[001]]'

            if createit:
                try:
                    #attr =copy.copy(config['Columns'])




                    ## table, deltas, pydeltas = dynamoTableCreate(resource, tablename, xkema, attr, config, gsi, lsi)
                    table = dynamoTableCreate(resource,tablename,xkema,attr,config,gsi,lsi)

                    printer( ' it was created?')
                except ClientError as e:
                    printer( "[E]  possible issue with HASH and column name conflict, maybe not found. ::%s"%e)
                    s =100/0
                    printer( s)
                    obj.append([ namingCrud(ERROR), tablename, 'creation failed' , e.response['Error']['Message'] ])
                    ready=False
                    return (tableIsnew, ready, obj,pyObj, None)
                # Wait until the table exists.
                printColor('......    CREATING table [%s] please be patient...'%(tablename) )
                table.meta.client.get_waiter('table_exists').wait(TableName=tablename)
                tableIsnew = True
                ready = True

                # if records is not None:
                #     for row in records:
                #         deltas, pydeltas =self.addRow(table, row, nkeys, createit)
                #         if deltas is not None:
                #             updatedRows.append(deltas)

                if records is not None:
                    if len(records) > 0:
                        defined,row_insert=self.tableRowModelReform(rows, config)
                        #deltas, pydeltas = self.table2Update(table, defined,nkeys, None, None, createit)

                        printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
                        printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
                        printer ("---> 004.  table2Update")
                        printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
                        printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
                        deltas, pydeltas = self.table2Update(table, defined, nkeys, createit)
                        if deltas is not None:
                            updatedRows.append(deltas)
                            pyObj['deltas'].update({'items':pydeltas})

                printer("DynamoDB table '%s' created."%(tablename))
            else:
                ignore = True
                #obj.append(['IGNORE', tablename, 'NOT CREATED!!!  ...%s would have been created if create mode was on'%(tablename)])

            # if 'LocalSecondaryIndexes' in table:
            #     lsi = table['LocalSecondaryIndexes']
            #     ldetail, pyldetail = globalSecondaryDetail(lsi, True)
            #
            # if 'GlobalSecondaryIndexes' in table:
            #     gsi = table['GlobalSecondaryIndexes']
            #     gdetail, pygdetail = globalSecondaryDetail(gsi)


            ldetail, pyldetail = globalSecondaryDetail_flat(lsi, True)
            gdetail, pygdetail = globalSecondaryDetail_flat(gsi)


            readableColumns = '.'.join('%s:%s' % (aa['AttributeName'], aa['AttributeType']) for aa in config['Columns'])
            readableKeys = '.'.join('%s:%s' % (t['AttributeName'], t['KeyType']) for t in pkeys)
            change = "%s/%s"%(namingCrud(IGNORE) if ignore else "",namingCrud(CREATE) )
            obj.append([change, tablename, audit, owner, readableKeys,config['totalReads'],config['totalWrites'],readableColumns ])
            if pygdetail is not None or pyldetail is not None:
                objh = gsiHeader()
                obj = obj + objh
            if pyldetail is not None:
                obj = obj + ldetail
            if pygdetail is not None:
                obj = obj + gdetail

            obj= obj+ [addHeaders]
            obj = obj + updatedRows
            pyObj['deltas']['all']= change
            return (tableIsnew, ready, obj,pyObj, None)

### TODO MAKE SURE secondary index is defined
        ## GSI must be filtered in each CSV , JSON , YAML files
        ## on LOAD
        ## then on table create GSI is to be entered correctly
    def UpdateDocument(self, dynoObj, targetEnv,tableName, applyChanges=False, override=False):
        if applyChanges:
            changeTable = True if override else False
        else:
            changeTable = False
        objs=[]
        pyObjs={}
        resource=self.__get_resource__()
        client=self.__get_client__()
        tvalue = resource.Table(tableName)
        env = dynoObj[targetEnv]
        title=targetEnv
        printer('        ******    ****  **** %s' % targetEnv)
        printer('    ..^..>>%s' % tableName)
        acnt = env['account']
        printer('********************')
        printer(acnt)
        printer(title)

        objs.append([acnt, title])
        pyObjs[acnt] = {}
        HEADER = ['DELTA', 'Name[%s]' % ('dynamodb'), 'Audit', 'Owner', 'Partition Key', 'totalReads',
                  'totalWrites', 'Columns']
        objs.append(HEADER)
        #raise ValueError('[E] UpdateTable issue  ::', tableName)
        defined = env['tables'][tableName]

        config = defined['config']
        rows = defined['rows']  # [index]  --> keys and #records


        pyObj = {'config':config,'rows':rows,'deltas':{}}

        table_present = client.describe_table(TableName=tableName)

        objDefine, pyDefine = get_tableInfo(table_present)
        printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
        printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
        printer ("---> 001.  table2Update")
        printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
        printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
        deltas, pydeltas = self.table2Update(tvalue, defined, pyDefine, changeTable)

        if deltas is not None:
            objs.append(deltas)
            pyObj['deltas'].update({'items':pydeltas})

        return (objs, pyObjs)




    def UpdateTable(self, dynoObj, targetEnv,tableName, applyChanges=False, override=False):
        if applyChanges:
            createMissingTables = True
            deleteit = True if override else False
            changeTable = True if override else False
        else:
            createMissingTables = False
            deleteit = False
            changeTable = False
        env = dynoObj[targetEnv]
        title=targetEnv
        printer('        ******    ****  **** %s' % targetEnv)
        printer('    ..^..>>%s' % tableName)
        acnt = env['account']
        printer('********************')
        printer(acnt)
        printer(title)
        objs=[]
        pyObjs={}
        objs.append([acnt, title])
        pyObjs[acnt] = {}
        HEADER = ['DELTA', 'Name[%s]' % ('dynamodb'), 'Audit', 'Owner', 'Partition Key', 'totalReads',
                  'totalWrites', 'Columns']
        objs.append(HEADER)
        #raise ValueError('[E] UpdateTable issue  ::', tableName)
        defined = env['tables'][tableName]

        audit, owner = nameCheck('ansible', tableName, self._regx, env)
        if ACTION_KEY in defined:
            changing=defined[ACTION_KEY]
            if 'delete' in defined[ACTION_KEY]:
                delta="%s/%s" % ("" if changeTable else namingCrud(IGNORE), namingCrud(changing))
                # delete table and all records
                printer('DELETING TABLES')
                if deleteit:
                    self.tablesDrop([tableName])
                objs([delta, tableName, ])
                return
        config = defined['config']
        rows = defined['rows']  # [index]  --> keys and #records
        printer(defined)
        gsi = lsi = None
        if 'gsi' in defined:
            gsi = defined['gsi']
        if 'lsi' in defined:
            lsi = defined['lsi']
        NotesEnd = ['NOTES', tableName]
        printer ("          ")
        printer ("          ")
        printer ("          ")
        # printer ("#########################################################")
        # printer ("#########################################################")
        # printer ("  (00)--> 00 [Z].  tablePresent")
        # printer ("#########################################################")
        # printer ("#########################################################")
        pkeys = config['Partition Key']
        created, ready, updates, pytable, table_present = self.tablePresent(tableName, config, pkeys, rows, gsi, lsi,
                                                                            createMissingTables)
        printer('   results (created:%s, ready:%s)' % (created, ready))
        pyObjs[acnt][tableName] = pytable
        if created and ready:  ## table new and ready
            ##add rows in tableExists()
            objs = objs + updates
            objs = objs
            objs.append(NotesEnd)
            return objs, pyObjs
        elif not ready:
            objs = objs + updates
            objs.append(NotesEnd)
            pyObjs[acnt][tableName]['deltas']['all'] = '[E] ERROR'
            raise ValueError('[E] Table is not ready ', tableName, title)
            return

        objs = objs + updates
        # printer ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        # printer ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        # printer ("---> 00B.  table_Modify")
        # printer ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        # printer ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
        updates, pytable = self.table_Modify(table_present, defined, tableName, config, pkeys, rows, gsi, lsi, changeTable)

        objs = objs + updates  # print table
        pyObjs[acnt][tableName] = pytable
        printer('        ******    ****  **** ')
        objs.append(NotesEnd)
        return (objs, pyObjs)


    def UpdateTables(self, dynoObj, targetEnv, applyChanges=False, override=False):
        global ACTION_KEY
        # print dynoObj[o][t]['rows'][0]['keys']
        # print dynoObj[o][t]['rows'][0]['records']
        #applyChanges=False
        action = False
        if applyChanges:
            createMissingTables = True
            deleteit = False
            changeTable = True if override else False
        else:
            createMissingTables = False
            deleteit = False
            changeTable = False

        printer("...create it?  ((((   %s   )))))"% applyChanges)
        printer('dObject:: %s'%dynoObj)
        deltas = []  ## all changes go here
        loging = []  ## all warnings go here

        changedRows = 0
        changedConfigs = 0
        pyObjs ={}
        objs = []
        client = self.__get_client__()
        resource = self.__get_resource__()
        todelete=[]

        # key changes has change made [UPDATE,NEW, DUP_FOUND, DELETE]
        ## each row adds a CHANGE column  [UPDATE,NEW, DUP_FOUND, DELETE]
        ## {envACCOUNT:{account:'', table1:{isNew:0, rows=[{keys:,records:['change':new, update, waiting] }], table2:, .....table3}

        for title, env in dynoObj.items():
            printer(' :: %s'%(title) )
            printer( targetEnv)
            if targetEnv != 'all' and targetEnv != title:
                printer('  NOT-->%s  skipping...' % (title))
                continue
            acnt = env['account']
            found = False
            tables_review = []
            TABLES_CREATED = []
            TABLES_MODIFIED = []
            currentObjs = []
            objs.append([acnt,title])
            pyObjs[acnt]={}
            HEADER = ['DELTA', 'Name[%s]' % ('dynamodb'), 'Audit', 'Owner', 'Partition Key', 'totalReads',
                      'totalWrites', 'Columns']
            objs.append(HEADER)
            for t,defined in env['tables'].items():
                printer('        ******    ****  **** %s'%targetEnv)
                printer('    ..^..>>%s'%t)
                #print('    ..^..>>', defined)
                if ACTION_KEY in defined:
                    action=True
                    if 'delete' in defined[ACTION_KEY]:
                        # delete table and all records
                        printer('DELETING TABLES')
                        todelete.append(t)
                        continue

                config = defined['config']
                rows = defined['rows']  # [index]  --> keys and #records
                printer(defined)
                gsi=lsi=None
                if 'gsi' in defined:
                    gsi = defined['gsi']
                if 'lsi' in defined:
                    lsi = defined['lsi']
                NotesEnd = ['NOTES', t]
                tables_review.append(t)
                printer( 'ddddddd uuuu  dddd eeeee')
                printer( defined)
                printer( '    --->  ddddddd uuuu  dddd eeeee')
                #s=100/0
                ############################################################
                #### DOES TABLE EXIST??? ## CREATE TABLE AND RECORDS??? ####
                ############################################################

                #pks = config['Partition key'].split('.')
                #pkeys = dict([p.split(':')[0], p.split(':')[1]] for p in pks)

                pkeys =config['Partition Key']
                #print pkeys
                created, ready, updates, pytable, table_present = self.tablePresent(t, config, pkeys, rows, gsi,lsi, createMissingTables)
                printer('  results (created:%s, ready:%s)' % (created, ready)  )

                pyObjs[acnt][t]=pytable
                if created and ready:  ## table new and ready
                    ##add rows in tableExists()
                    TABLES_CREATED.append(t)
                    #tvalue = resource.Table(t)
                    objs = objs + updates
                    objs = objs
                    objs.append(NotesEnd)
                    continue
                elif not ready:
                    objs = objs + updates
                    objs.append(NotesEnd)
                    pyObjs[acnt][t]['deltas']['all']='[E] ERROR'
                    continue
                #else:  # is ready and already exists!!!
                    #tvalue = resource.Table(t)
                    # current object queries current table as it exists!!! this should only be used for comparisons
                    # existingObj = self.tableDefine( auditMeth.namingCrud(2), aconnect, currentObjs, tvalue, t )
                    #objDefine, pyDefine = get_tableInfo(table_present)

                printer('-----> %s'%config)
                printer('  ~~~>%s'%pkeys)

                ############################################################
                ####   DOES RECORDS EXIST??? ## CREATE  RECORDS???   #######
                ############################################################
                objs = objs + updates
                #updates, pytable = self.table2Update(tvalue,pyDefine,config,  pkeys, rows, changeTable)

                # printer ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                # printer ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                # printer ("---> 00A.  table_Modify")
                # printer ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                # printer ("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
                updates, pytable = self.table_Modify(table_present,defined,t, config, pkeys, rows,gsi,lsi, changeTable)

                #updates, pytable = self.table2Update(tvalue, defined, pyDefine, rows[0]['keys'], changeTable)
                objs = objs + updates  # print table
                pyObjs[acnt][t]=pytable
                printer('        ******    ****  **** ')
                objs.append(NotesEnd)
            missing = self.tablesAbsent( tables_review)

            objs.append(['TABLES_CREATED'])
            objs.append(TABLES_CREATED)
            objs.append(['TABLES_UNFOUND'])
            objs.append(missing)
            objs.append(['TABLES_DELETE'])
            objs.append(todelete)
            pyObjs[acnt]['TABLES_CREATED']=TABLES_CREATED
            pyObjs[acnt]['TABLES_UNFOUND']=missing
            pyObjs[acnt]['TABLES_DELETE']=todelete
            if deleteit:
                printer('tables deleted now')
                #self.tablesDrop(todelete)
            else:
                printer('[W]  SKIP TABLE DELETION %s'%todelete)
            # break

        return (objs, pyObjs)





## TODO:  setup ADD in new table to format to table level dict

    ##################################################
    #### EXISTING TABLE NEEDS TO BE UPDATED!!  #######
    ##################################################
    def table_Modify(self,table_present, defined, tablename, config, pkeys, rows, gsi,lsi, changeit=False):
        resource = self.__get_resource__()
        client = self.__get_client__()
        ready =True
        ignore = False
        obj=[]
        #updatedRows=[]
        pyObj = {'config':config,'rows':rows,'deltas':{}}

        xkema = pkeys

        if xkema[0]['KeyType'] != 'HASH':
            xkema.reverse()
        attr = self.attributeDefinitions(config, xkema, pkeys, gsi, lsi)
        tvalue = resource.Table(tablename)
        ####################
        objDefine, pyDefine = get_tableInfo(table_present)
        ###########################################################
        ##### UPDATE TABLE CONFIGURATION/DEFINITION################
        ###########################################################
        if changeit:
            changed = dynamoTableUpdate(client, tablename, xkema,pyDefine, attr, config, gsi, lsi)

        ##obj.append([change, tablename, audit, owner, readableKeys, config['totalReads'], config['totalWrites'],readableColumns])


        # printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
        # printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
        # printer ("---> 002.  table2Update")
        # printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
        # printer (";;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;")
        ##updated rows below  make sure you only get ROW DATA and append to master Obj pyobj for return
        deltas, pydeltas = self.table2Update(tvalue, defined, pyDefine, changeit)
        if deltas is not None:
            obj.append(deltas)
            pyObj['deltas'].update({'items':pydeltas})

        return obj, pyObj


    ### ONLY RESULTS IN ROW CHANGES NOT TABLE CHANGES OR HEADER
    def table2Update(self, resourceTable,  future, keys, changeit=False):
        global ACTION_KEY

        #UPDATE ALL ROWS/RECORDS
        csv_create = True
        row_delete=[]
        row_insert=[]
        row_update=[]
        row_conflict=[]
        row_alter=[]
        ######## BELOW USED TO BUILD CSV RESULTS  ######
        row_CVS=[]


        m_keys = future['config']['Partition Key']
        r_future = future['rows']
        sortKeys = [k['AttributeName']  for k in m_keys]
        header=[]
        totTableRecords = resourceTable.item_count

        for rf in r_future:
            changing = CREATE
            cKeys = { '%s'%v.split(':')[0]:'%s'%v.split(':')[1] for v in rf['keys'] }

            # print("////////////////////////////////////////////////////////////")
            # print("////////////////////////////////////////////////////////////")
            # print(".  START RECORDS. ---1111. %s"%len(r_future))
            # print("////////////////////////////////////////////////////////////")
            # print("////////////////////////////////////////////////////////////")
            print(rf)
            for r in rf['records']:
                rowIN=[]
                if csv_create:
                    #setup tok create CSV file
                    for key in keys:
                        kkey = key.split(':')[0]
                        if kkey not in r:
                            continue
                        vlu = r[kkey]
                        rowIN.append(vlu)
                # rvalue = r.values()[0]
                # if isinstance(rvalue, (basestring)):
                #     rkey = r.keys()[0]
                #     if rkey + ':' in rvalue:  # used to make sure  columns arent' inserted as row
                #         return (None, None)

                #nh = generateHeader(r, header)
                # ACTION to be taken @ ROW level
                print ("  @   -ROW LEVEL--->>>001 %s"%r)
                if not ACTION_KEY in r:
                    raise ValueError("[E] '%s' KEY required with value('update', 'delete', 'new') given:%s"%(ACTION_KEY,r) )
                
                print ("  @   -ROW LEVEL--->>>002")
                action = r[ACTION_KEY]
                item = {'item':r,'crud':action, 'key':sortKeys, 'ignore':False if changeit else True }
                del r[ACTION_KEY]
                r = convertAcceptedRowValue(r)
                if action == 'delete':
                    changing = DELETE
                    item = copy.copy(item)
                    item['item']={ x if i!='' else '':i if i!='' else None for x,i in r.items() }
                    row_delete.append(item)
                    continue
                item.update({'column':cKeys})
                if resourceTable:
                    if totTableRecords>0:  #DON"T BOTHER QUERYING TABLE IF EMPTY!!!!!
                        print('----===-----1 %s'%resourceTable)
                        print(keys)
                        keyTypes= dict([aa['AttributeName'],aa['AttributeType']] for aa in keys['config']['Columns'])
                        print('----===-----2')
                        results = self.tableConditionQuery(resourceTable, sortKeys, r,keyTypes)
                        #if action == 'insert':
                        if results['Count'] >= 1:
                            if action == 'insert':
                                row_conflict.append(item)
                            elif action == 'update':
                                row_update.append(item)
                                changing = UPDATE
                            continue
                        else:
                            row_insert.append(item)
                    else:
                        row_insert.append(item)
                change = "%s/%s" % ("" if changeit else namingCrud(IGNORE), namingCrud(changing))
                if csv_create:
                    rowIN = [change]+rowIN
            row_CVS.append(rowIN)
        #table_change
        #table_drop
        #table_create...wrong FUNCTION
        #future table definition compare to fact/current definition


        row_alter = row_delete + row_insert
        printer( '****  changeit: %s'%changeit)
        printer( '   ****  conflict: %s'%row_conflict)
        if changeit:
            response, warn =self.table_BatchSync(resourceTable, row_alter, keys)
            ## this can cause issues for the update process
            response, warn =self.table_BatchUpdate(resourceTable, row_update)

        #objs.append(['NOTES[%s]' %(provider_name), 'other relevant info here'])

        return row_CVS, row_alter+row_update



    ########################################################################################################
    ## where items['item'] is the Object to put {'item':{'somekey': 'somevalue', ...}, 'crud':'delete', 'key':{}} ####
    ########################################################################################################
    def table_BatchSync(self,table, items, keys):
        warn=[]
        remainingItems=[]
        printer( '     ')
        printer( '     ')
        printer( '     ')
        printer( '     ')
        printer( ' ******** table_BatchSync >> 1 >> ....%s'%items)
        try:
            lastBatch=[]
            completed=[]
            with table.batch_writer() as batch:
                for i in items:
                    printer( ' ********  >> 1 >> ....')
                    printer( 'key %s'%i['key'])
                    printer( 'item %s'%i['item'])
                    printer( ' ********  >> 2 >> ....')
                    unprocessed=False
                    if i['crud'] == 'delete':
                        if '' in i['item']:
                            del i['item']['']
                        printer( i['item'])
                        printer( ' ********  >> 3 >> ....')
                        response =batch.delete_item( Key=i['item'] )
                    else:
                        response =batch.put_item( Item=i['item'] )
                        
                    if response:
                        unprocessed = response.get('UnprocessedItems', None)
                    if not unprocessed:
                        i['status'] = 'success'
                    else:
                        i['status'] = 'fail'
                    #items.remove(i)
                    btot = len(lastBatch)
                    lastBatch.append(i)
                    completed.append(i)
                    if btot>10:
                        diff=btot-10
                        lastBatch=lastBatch[diff:]
        except ClientError as e:
            dups=[]
            add=[]
            for row in lastBatch:
                r=row['item']
                sortKeys = row['key']
                keyTypes= dict([aa['AttributeName'],aa['AttributeType']] for aa in keys['config']['Columns'])
                r = convertAcceptedRowValue(r)
                results=self.tableConditionQuery( table, sortKeys, r, keyTypes)
                if results['Count'] >= 1:
                    dups.append(row)
                else:
                    add.append(row)

            for a in add:
                if a in completed:
                    completed.remove(a)
                for lbl,prop in a['item'].items():
                    for lbl2,prop2 in a['item'].items():
                        if prop2 == prop:
                            randint=andint(1, 100)
                            space=" "
                            for dot in randint:
                                space=space+space
                            a['item'][lbl] = "%s %s."%(prop, space)
            for c in completed:
                if c in items:
                    items.remove(c)
            if "keys contains duplicates" in str(e):
                print ("[E] contains duplicates .... trying again now...")
                remainingItems, rewarn=self.table_BatchSync(table, items, keys)
            else:
            #self.table_BatchSync(table, items, keys)
                raise ValueError("[E] Some other error... table_BatchSync :%s"%(e))
            items=items+remainingItems
            warn=warn+rewarn
        return items, warn


    #### BELOW WORKS as EXPECTED updates each item one at a time SLOWWWWW!!!
    def table_BatchUpdate(self, table, items):
        warn = []
        for i in items:
            # printer( '>>>>>># >>>>>>>>>>   001BB')
            # printer( i)
            # printer( '>>>>>># >>>>>>>>>>   002AA')
            #raise ValueError('[E] updating table_BatchUpdate...{0}'.format(i))
            types = i['column']
            acount = {'count': -1}
            plusCount = {'count': -1}
            keyIN= {x:i['item'][x] for x in i['key']}
            it = i['item']
            item=it
            keysfound=[]
            copied=False
            for k in keyIN:
                printer( k)
                if k in item:
                    if copied is False:
                        item = copy.deepcopy(it)
                        copied=True
                    del item[k]
                    keysfound.append(k)

            #totkeys=len(i['item'])
            totkeys=len(item)
            fake = list( [ '#%s'%s ,   ':%s'%s ] for s in string.lowercase[:totkeys] )
            fakeDic= dict( d for d in fake)
            acount['count'] =-1
            derv = dict( [ (fake[self.incrementCount(acount)][0] ) ,   v ] for v in item.items() )

            xnames= dict([k, v[0] ] for k, v in derv.items())
            acount['count'] =-1
            xpress = "SET " + ", ".join("%s = %s " % (v[0], v[1]) for v in fake)

            xvalues = dict([fakeDic[k], convertTypes(v[1],types[ v[0] ])] for k, v in derv.items())

            response = table.update_item(
                Key=keyIN,
                UpdateExpression= xpress,
                ExpressionAttributeNames = xnames,
                ExpressionAttributeValues= xvalues
            )
            unprocessed = response.get('UnprocessedItems', None)
            if not unprocessed:
                it['status']='success'
            else:
                it['status']='fail'
            if len(keysfound) >0:
                it['warn']=keysfound
            printer( response)

        return items, warn


    # find similar records
    def tableConditionQuery(self, tresource, sortKeys, record, keyTypes):
        results = None
        totkeys = len(sortKeys)

        # print '*(*(*(*(*()))))>>>>002'
        # print tresource
        # print sortKeys
        # print record
        # print keyTypes
        # print '*(*(*(*(*()))))>>>>001'
        for skey in sortKeys:
            strict_key=convertDynamoType(keyTypes[skey],record[skey])
            if strict_key is not None:
                record[skey]=strict_key
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


    def tablesAbsent(self, tables_review):
        client = self.__get_client__()
        missing = []
        rawItems = client.list_tables()['TableNames']
        for name in rawItems:
            if name in tables_review:
                continue
            printColor(['[E] DynamoDB Table [%s] MISSING...' % (name)])
            missing.append( name)
        return missing


    def tablesDrop(self,tables):
        client = self.__get_client__()
        for t in tables:
            response=client.delete_table(TableName=t)
            printer ('[W] ....DELETING TABLE %s'%t)
            client.get_waiter('table_not_exists').wait(TableName=t)
            printer( response )



def dynamoTableUpdate(client,name,xkema,facts,attr,config,ngsi=None, nlsi=None):
    gsi=[]
    lsi=[]
    gsi_main={}
    changed = False
    if ngsi is not None:
        gsi_main.update(ngsi)
    # printer( facts)
    # printer( '()(*()(*()(*()*()*()   ---->  001 a')
    #if nlsi is not None:
    #    gsi_main.update(nlsi)
    if gsi_main is not None:
        gsiUpdates = []
        gsiStates = []
        for g,e in gsi_main.items():
            if 'GSI' in e['Type']:
                if not ACTION_KEY in e:
                    printer("[W]  NO action keys found to change TABLE Definitions.... skiping...")
                    return changed
                action=e[ACTION_KEY]
                gsiValue={}
                if g in facts['gsi']:
                    if action.lower()!='delete':
                        action='Update'
                        gsiValue=copy.deepcopy(e['raw'])
                        del gsiValue['KeySchema']
                        del gsiValue['Projection']
                        # printer('....***__~~~~000001')
                        if facts['gsi'][g]['raw']['ProvisionedThroughput'] == gsiValue['ProvisionedThroughput']:
                            continue  #amounts are same so skip!!

                        # printer('....***__~~~~000002')
                        gsiUpdates.append( { action.title(): gsiValue } )
                        continue
                    else:
                        action='Delete'
                        gsiValue={ 'IndexName': g }
                elif action.lower()=='delete':
                    continue    # key not found so skip
                else:
                    action = 'Create'
                    gsiValue = e['raw']
                gsiStates.append( { action.title(): gsiValue } )
                #gsi.append(e['raw'])
            else: ##requires table deletion... much more entailed... saving records then rebuild/import....YuK!
                lsi.append(e['raw'])
    readUnits = int(config['totalReads']) if int(config['totalReads'])> 0 else 1
    writeUnits = int(config['totalWrites']) if int(config['totalWrites'])> 0 else 1
    try:
        response = client.update_table(TableName=name,
                                      AttributeDefinitions=attr,
                                      ProvisionedThroughput={'ReadCapacityUnits': readUnits,
                                                             'WriteCapacityUnits': writeUnits})
        dynamoTableWait(client,name,response)
        changed = True
    except botocore.exceptions.ClientError as e:
        if 'equals the current value' in e.message:
            printer( '[W] found equivalent %s'%(e))
        else:
            raise ValueError('[E] updating table...%s',e.message)

    # printer( '()(*()(*()(*()*()*()   ---->  001')
    # printer( attr)
    # printer( '()(*()(*()(*()*()*()   ---->  002')

    if len(gsiUpdates) >0:
        response = client.update_table(TableName=name,
                                      AttributeDefinitions=attr,
                                      GlobalSecondaryIndexUpdates=gsiUpdates)
    #[{'Update':{'IndexName':blabla, 'ProvisionedThroughput}},{'Create'}]
        changed = True
        dynamoTableWait(client, name, response)
    if len(gsiStates)>0:
        for g in gsiStates:
            response = client.update_table(TableName=name,
                                           AttributeDefinitions=attr,
                                           GlobalSecondaryIndexUpdates=[g])
            # [{'Update':{'IndexName':blabla, 'ProvisionedThroughput}},{'Create'}]
            changed = True
            dynamoTableWait(client, name, response)

    # response = client.update_table(TableName=name, KeySchema=xkema,  # Partition keys
    #                               AttributeDefinitions=attr,
    #                               ProvisionedThroughput={'ReadCapacityUnits': readUnits,
    #                                                      'WriteCapacityUnits': writeUnits},
    #                               LocalSecondaryIndexes=lsi,
    #                               GlobalSecondaryIndexes=gsi)
    #
    # response = client.update_table(TableName=name, KeySchema=xkema,  # Partition keys
    #                               AttributeDefinitions=attr,
    #                               ProvisionedThroughput={'ReadCapacityUnits': readUnits,
    #                                                      'WriteCapacityUnits': writeUnits},
    #                               LocalSecondaryIndexes=lsi,
    #                               GlobalSecondaryIndexes=gsi)
    return changed

def dynamoTableWait(client,tablename, response=None):
    if response is None:
        response = client.describe_table(TableName=tablename)
    printer( response)
    if 'Table' in response:
        if 'ING' in response['Table']['TableStatus']:
            time.sleep(2)
            dynamoTableWait(client,tablename)


def dynamoTableCreate(resource, name, xkema, attr, config, ngsi=None, nlsi=None, create=True):
    gsi=[]
    lsi=[]
    objs = []
    readUnits = int(config['totalReads']) if int(config['totalReads'])> 0 else 1
    writeUnits = int(config['totalWrites']) if int(config['totalWrites'])> 0 else 1
    gsi_main={}
    if ngsi is not None:
        gsi_main.update(ngsi)
    if nlsi is not None:
        gsi_main.update(nlsi)
    if gsi_main is not None:
        for g,e in gsi_main.items():
            if 'GSI' in e['Type']:
                gsi.append(e['raw'])
            else:
                lsi.append(e['raw'])
    lsiValid=False
    if len(lsi)>0:
        newlsi = copy.copy(lsi[0])
        if 'ProvisionedThroughput' in newlsi:
            del newlsi['ProvisionedThroughput']
        finalLSI=[newlsi]
        lsiValid=lsi_inPrimary(xkema, finalLSI)
        if not lsiValid:
            raise ValueError('[E] LSI given does NOT match PRIMARY HASH', finalLSI, xkema)

    if len(gsi)>0 and lsiValid:
        printer("A")

        table=resource.create_table(TableName = name,KeySchema = xkema, # Partition keys
                                AttributeDefinitions = attr,
                                ProvisionedThroughput = { 'ReadCapacityUnits':readUnits , 'WriteCapacityUnits': writeUnits},
                            LocalSecondaryIndexes=finalLSI,
                            GlobalSecondaryIndexes=gsi     )
    elif len(gsi)>0:
        printer("B")
        table=resource.create_table(TableName = name, KeySchema = xkema, # Partition keys
                                AttributeDefinitions = attr,
                                ProvisionedThroughput = { 'ReadCapacityUnits':readUnits , 'WriteCapacityUnits': writeUnits},
                            GlobalSecondaryIndexes=gsi    )
    elif lsiValid:
        printer("C")
        table=resource.create_table(TableName = name, KeySchema = xkema, # Partition keys
                                AttributeDefinitions = attr,
                                ProvisionedThroughput = { 'ReadCapacityUnits':readUnits , 'WriteCapacityUnits': writeUnits},
                            LocalSecondaryIndexes=finalLSI    )
    else:
        printer("D")
        #s=100/0
        table=resource.create_table(TableName = name, KeySchema = xkema, # Partition keys
                                AttributeDefinitions = attr,
                                ProvisionedThroughput = { 'ReadCapacityUnits':readUnits , 'WriteCapacityUnits': writeUnits}
                            )
    return table

def lsi_inPrimary(xkema,lsi):
    pfound=False
    find='HASH'
    for l in lsi:
        for ks in l['KeySchema']:
            print('....008')
            for k in ks:
                print(ks[k])
                if find in ks[k]:
                    mk = ks['AttributeName']
                    for x in xkema:
                        if find in x['KeyType']:
                            if mk == x['AttributeName']:
                                return True
    return pfound

def get_tableInfo( table_defined):
    printer( '  ==>get_tableInfo  .....')
    table = table_defined['Table']
    printer( table)
    stat = table['TableStatus']
    name = table['TableName']
    owner = "AWS"
    audit = "NONE"
    # pkey = table['KeySchema'][0]['AttributeName']
    objs = []
    attributes = table['AttributeDefinitions']
    clmns = '.'.join('%s:%s' % (aa['AttributeName'], aa['AttributeType']) for aa in attributes)
    keys = table['KeySchema']
    pkey = '.'.join('%s:%s' % (t['AttributeName'], t['KeyType']) for t in keys)
    # print '      ==== keys @@##>>  ',table['KeySchema']
    indexes = 0
    reads = 0
    writes = 0
    gsi = None
    pygdetail = pyldetail = None

    if 'LocalSecondaryIndexes' in table:
        lsi = table['LocalSecondaryIndexes']
        ldetail, pyldetail = globalSecondaryDetail(lsi, True)

    if 'GlobalSecondaryIndexes' in table:
        gsi = table['GlobalSecondaryIndexes']
        gdetail, pygdetail = globalSecondaryDetail(gsi)

        indexes = len(gsi)
        # reads, writes = getDynamoRU(item['GlobalSecondaryIndexes'])
    reads = table['ProvisionedThroughput']['ReadCapacityUnits']
    writes = table['ProvisionedThroughput']['WriteCapacityUnits']
    objs.append([name, audit, owner, stat, pkey, indexes, reads, writes, clmns])
    if pygdetail is not None or pyldetail is not None:
        objh = gsiHeader()
        objs = objs + objh
    if pyldetail is not None:
        objs = objs + ldetail
    if pygdetail is not None:
        objs = objs + gdetail
    printer( ' bbb 22   %s'%pygdetail)

    pyObj = {'rows': [], 'gsi': pygdetail,'lsi':pyldetail,
             'config': {'audit': audit, 'owner': owner, 'status': stat, 'Partition Key': keys, 'indexes': indexes,
                        'totalReads': reads, 'totalWrites': writes, 'Columns': attributes}}
    #objs.append([name, projected, ptype, pkey, stat, indexType, indexes, reads, writes])
    #pyObj[name] = {'Status': stat, 'Type': indexType,
     #              'indexes': indexes, 'raw': rawGsi}
    return (objs, pyObj)







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
    printer( '   2-====> GSI ')
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
            printer( '  [W]-- gsi removing NonKeyAttributes %s'% name)
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


def globalSecondaryDetail_flat( pyObj, isLSI=False):
    objs=[]
    if pyObj is None:
        return None,None
    for name,obj in pyObj.items():
        raw = obj['raw']
        indexType= obj['Type']
        stat= obj['Status']
        keys = raw['KeySchema']

        ptype = raw['Projection']['ProjectionType']
        indexes = 0
        projected = None
        pAttributes=None


        pkey = '.'.join('%s:%s' % (t['AttributeName'], t['KeyType']) for t in keys)
        indexes = len(keys) + indexes

        if ptype == 'INCLUDE':  ##LOOP THROUGH INDEXES TO INCLUDE
            pAttributes = raw['Projection']['NonKeyAttributes']
            indexes = len(pAttributes)
            projected = '.'.join('%s' % (t) for t in pAttributes)


        #if pAttributes is None:
        #    del raw['Projection']['NonKeyAttributes']
        #    print ('  [W]-- gsi removing NonKeyAttributes ', name)
        if not isLSI:
            _writes = {'ProvisionedThroughput':{'ReadCapacityUnits':raw['ProvisionedThroughput']['ReadCapacityUnits'],'WriteCapacityUnits':raw['ProvisionedThroughput']['WriteCapacityUnits']}}
            #del _writes['ProvisionedThroughput']['NumberOfDecreasesToday']
            raw.update(_writes)
            writes = raw['ProvisionedThroughput']['WriteCapacityUnits']
            reads = raw['ProvisionedThroughput']['ReadCapacityUnits']
        else:
            indexType='LSI'
            writes=reads=None

        objs.append([name, projected, ptype, pkey, stat,indexType, indexes, reads, writes])

    return objs, pyObj



