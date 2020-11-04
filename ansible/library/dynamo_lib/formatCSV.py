from context import FormatContext
import csv
import copy


moduleIN=None
def printer(msg):
    moduleIN.printer(msg)
def printColor(msg):
    moduleIN.printcolor(msg)

class CSV(FormatContext):
    def __init__(self, pathfile,ansible):
        global moduleIN
        super(CSV, self).__init__(pathfile, ansible)
        self._extension = 'csv'
        moduleIN = self

    def loadDeltas(self,section,envs,index):
        printer( 'here we go')

    def load(self,section,envs=None,index=None):
        #print 'loader....CSV...'
        fullpath='%s.%s'%(self._filepath,self._extension)

        delimiter=','
        #delimiter=';'
        printer( '..  loading ..%s'%fullpath )
        with open(fullpath, 'rU') as csvfile:
            #reader = csv.reader(csvfile, delimiter=';') #, dialect=csv.excel_tab)
            reader=csv.reader(csvfile,delimiter=delimiter, dialect='excel')

            #reader=csv.reader(csvfile, quoting=csv.QUOTE_ALL,quotechar='"',delimiter=delimiter, dialect='excel')
            #print '....in read file OUT'
            current=type('obj', (object,),{'section':'','env':'','columns':''})
            lastRow=''
            latestRecords=gsiKEYS=None
            tableName=''
            DHEAD='DATA_HEADER[%s]'%(section.lower())
            GSINAME = 'Name[GSI]'
            FOOTER='NOTES[%s]'%(section.lower())
            section = 'Name[%s]'%(section.lower())      # [dynamo]
            gsiRawKeys=['KeySchema','ProjectionType','totalReads','totalWrites', 'Projected']
            ACTION = '[ACTION]'
            empty=""
            actionkey='A C T I O N'
            #print section
            obj = {}
            #reader=[field.strip() for row in csv.reader(csvfile, delimiter=';')  for field in row if field]
            # isQuoted=False
            # for c in csvfile:
            #     if c[0] == '"':
            #         isQuoted=True
            #     break
            # if isQuoted:
            #     return ['use csv that does not contain quoted fields!!']
            action=False
            for row in reader:
                ##rowIN = delimiter.join(row)
                rowIN= row
                #rowIN = rowIN.strip()
                #continue

                printer( '         -- rowIN 00111 -- DONE %s'%rowIN)
                if section in rowIN:
                    current.section = rowIN
                    #print rowIN
                    printer( '   -- rowIN 003 -- DONE %s'%rowIN)
                elif 'GSI' in rowIN:
                    printer('  ^^^^^001^^^^^^^')
                    printer(lastRow)
                    printer(rowIN)
                    printer('  ^^^^^^002^^^^^^')
                elif ACTION in rowIN:
                    printer( '            **&&&**  ACTION MODE  ----------->>')
                    action=True
                if section in current.section:
                    envFound,obj,cenv= self.verifyEnvironment(envs,rowIN,index,obj)
                    if not envFound:
                        if FOOTER in lastRow or section in lastRow:  ####  NEW TABLE
                            printer( '            **&&&**  FOOTER  ----------->>')
                            printer( rowIN)
                            gsiKEYS=None
                            clmns = copy.copy(rowIN)
                            if action:
                                actON=clmns[0]
                            if not current.env:
                                raise ValueError('[E] CSV given does NOT match AWS accounts', envs, index)
                            tableName=self.tableNew(current.section,current.env,clmns, obj,action,delimiter)
                            if tableName is empty:
                                lastRow = rowIN
                                continue
                            elif action:
                                obj[(current.env)]['tables'][tableName].update({actionkey:actON})
                        elif DHEAD in lastRow and FOOTER not in rowIN:     ######      NEW COLUMN HEAD     #########
                            gsiKEYS=None
                            current.columns=rowIN
                            #keys=current.columns.split(delimiter)
                            keys = rowIN
                            actON=empty
                            if ':' in ','.join(current.columns):
                                objKeys=[]
                                if action:
                                    actON=keys[0]
                                    keys=keys[1:]
                                    printer( '   ACT ON ACTION----.><><>>>>%s'% actON)
                                for k in keys:
                                    if k == '' or k.isspace():
                                        continue
                                    #objKeys[k.split(':')[0]] = k.split(':')[1]
                                    #objKeys.append({k.split(':')[0]:k.split(':')[1]})
                                    objKeys.append(k)

                            #keys[0]=keys[0]
                            table =obj[ (current.env) ]['tables'][tableName]
                            if 'gsi' in table:
                                printer( '   004 table replacing with gsi...')
                                #print '  lastrow:',lastRow
                                printer( table['gsi'])
                                #print table
                            latestRecords = {'keys':objKeys,'records':[]}
                            #if action:
                            #    latestRecords['keys'].update({actionkey:actON})
                            table['rows'].append(latestRecords)

                        elif GSINAME in rowIN and DHEAD not in rowIN and FOOTER not in rowIN:
                            if action:
                                actON=rowIN[0]
                                rowIN=rowIN[1:]
                            gsiKEYS=rowIN
                            latestRecords=None
                        elif gsiKEYS and latestRecords is None and GSINAME not in rowIN and DHEAD not in rowIN and FOOTER not in rowIN:
                            table =obj[ (current.env) ]['tables'][tableName]
                            if 'gsi' not in table:
                                table['gsi']={}
                                table['lsi']={}
                            printer( '    AA (005)()() GSI... ')
                            if action:
                                actON=rowIN[0]
                                gsiNameIN=rowIN[1]
                                rowIN=rowIN[1:]
                            cgsi,clsi =self.loadGSI( rowIN, GSINAME, gsiKEYS, gsiRawKeys)
                            if action:
                                if cgsi:
                                    cgsi[gsiNameIN].update({actionkey:actON})
                                if clsi:
                                    clsi[gsiNameIN].update({actionkey:actON})
                            table['gsi'].update(cgsi)
                            table['lsi'].update(clsi)

                            printer( table)
                            printer( '      BB ()()() GSI... ')
                        elif DHEAD not in rowIN and section not in rowIN and FOOTER not in rowIN and GSINAME not in rowIN:  ######      NEW ROW    #########
                            gsiKEYS=None
                            if latestRecords:
                                count=0
                                data_row={}

                                values = copy.copy(rowIN)
                                #if rowIN.split(delimiter)[0].isspace() or rowIN.split(delimiter)[0] is '':
                                if rowIN[0].isspace():
                                    self.tableReset(current,cenv)
                                    latestRecords = None
                                    lastRow = rowIN
                                    continue
                                lastKeys = latestRecords['keys']
                                if action:
                                    actON=values[0]
                                    values = values[1:]
                                if ':' in values[0]:
                                    resetHeader=True
                                    for v in values:
                                        if ':' not in v:
                                            resetHeader=False
                                    if resetHeader:
                                        latestRecords['keys']=values
                                        lastRow = rowIN
                                        continue
                                printer( '  --> lastKeys:006:: ')
                                printer( lastKeys)
                                printer( '     ==> rows:::')
                                printer( values)
                                for key in lastKeys:
                                    vlu = values[count]
                                    #print '--- --- -- ->',key
                                    #print '        ::>',vlu
                                    #k,v = key.items()[0]
                                    #kname=['%s'%ks for ks in key]
                                    kname = key.split(':')[0]
                                    printer( data_row)
                                    printer( kname)
                                    #data_row[kname[0]] = vlu
                                    data_row[kname] = vlu
                                    count +=1
                                #print '           1  *_*_*_*_*_*_*_*_*_*_*_###'
                                #print data_row
                                #print '            2 *_*_*_*_*_*_*_*_*_*_*_###'
                                if action:
                                    data_row.update( {actionkey:actON} )
                                latestRecords['records'].append(data_row)
                                #print data_row
                    else:                                                                 # SUBSEQUENT SETUP HERE
                        self.tableReset(current,cenv)
                        latestRecords =gsiKEYS= None
                else:                                                                     # INITIAL SETUP HERE
                    envFound,obj,cenv= self.verifyEnvironment(envs,rowIN,index,obj)
                    if envFound:
                        self.tableReset(current,cenv)
                    #print '--INIT->',envFound
                   # break
                lastRow = rowIN
        #print obj[o][t]['rows'][0]['keys']
        printer( '    = =008 = &*^*^*^*^*^*')
        #print obj[current.env]['tables']['vos-student-call-data']['lsi']
        #s=100/0
        #print obj
        #print obj
        #s=100/0
        return obj

    def dbRead(self, item):
        pass

    def write(self, item, option=''):
        fullpath='%s%s.%s'%(self._filepath,option,self._extension)
        printer( fullpath)
        delimiter=','
        with open(fullpath, 'wb') as csvfile:
            writer = csv.writer(csvfile, delimiter=delimiter, dialect='excel')
            #writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL, delimiter=delimiter, dialect='excel')
            #writer = csvkit.py2.writer(csvfile, quoting=csv.QUOTE_ALL, delimiter=delimiter)
            writer.writerows(item)
        return fullpath
    def dump(self, item):
        pass

    def verifyEnvironment(self, envs, rowIN, index, obj):
        envFound = False
        currentEnv = None
        for aID, e in envs.items():

            if '%s : [%s]' % (e[index], aID) in rowIN:
                currentEnv = e[index]

                obj[(currentEnv)] = {'account': aID, 'tables': {}}
                envFound = True
                break

        return (envFound, obj, currentEnv)

    def loadGSI(self, rowIN, GSINAME, gsiKEYS, gsiRawKeys ):
        printer( '       (loadGSI) ***ENTERING IN NOW!!')
        count = 0
        alast = rowIN
        printer( '..................--->GSI last 001')
        printer( rowIN)
        printer( '..................--->GSI last 002 %s'%gsiKEYS)
        gsi_group = None
        gsi={}
        lsi={}
        for a in alast:
            indx = gsiKEYS[count]
            vlu = a
            # if ':' in a:
            #     vl = a.split('.')
            #     if 'Partition' in indx:  # {'KeyType:HASH', 'AttributeName':'myname'}
            #         # vlu =  '.'.join('%s:%s'%(t['AttributeName'],t['KeyType']) for t in keys)
            #         # vlu =  {'%s:%s'%(t['AttributeName'],t['KeyType']) for t in vl}
            #         vlu = [{'AttributeName': g.split(':')[0], 'KeyType': g.split(':')[1]} for g in
            #                vl]

            printer( '     -----gsi---%s'%count)
            #print indx
            printer( a)
            # print vlu
            # print gsiRawKeys
            printer( '     -----gsi --END--%s'% GSINAME)
            count += 1

            if GSINAME in indx:  # first item in the row is always the name of the index in question like "InteractionEndDT"
                gsi_group = vlu
                printer( '           new gsi group::%s'%gsi_group)
                if gsi_group in gsi:
                    continue
                gsi[gsi_group] = {}
                gsi[gsi_group]['raw'] = {'IndexName': gsi_group}
                #print '001',gsi_group
                continue
            elif indx == '' and vlu == '':
                continue
            elif vlu == '':
                vlu = None
           # print '002',gsi_group
           # print gsi

            rawG = gsi[gsi_group]['raw']
            if indx in gsiRawKeys:
                #print '  $$$ found in rawKeys ', indx
                #print '  003', gsi[gsi_group]
                if 'total' in indx:
                    # print '       3....---==>> gsi'
                    # print '   4---- >  gsi getting total'
                    printer( ' 5..%s:%s' % (indx, vlu) )
                    if vlu is None:
                        #print '  004', gsi[gsi_group]
                        continue
                    if "ProvisionedThroughput" not in rawG:
                        rawG['ProvisionedThroughput'] = {}
                    if 'totalReads' in indx:
                        if "ReadCapacityUnits" not in rawG['ProvisionedThroughput']:
                            rawG['ProvisionedThroughput']['ReadCapacityUnits'] = int(vlu)
                    elif 'totalWrites' in indx:
                        if "WriteCapacityUnits" not in rawG['ProvisionedThroughput']:
                            rawG['ProvisionedThroughput']['WriteCapacityUnits'] = int(vlu)

                elif 'Project' in indx:
                    if "Projection" not in rawG:
                        rawG['Projection'] = {}
                    if 'Type' in indx and 'ProjectionType' not in rawG['Projection']:
                        rawG['Projection']['ProjectionType'] = vlu
                    elif 'NonKeyAttributes' not in rawG['Projection']:
                        if vlu is None:
                            #print '  005', gsi[gsi_group]
                            continue
                        rawG['Projection']['NonKeyAttributes'] =  vlu.split('.')
                elif 'KeySchema' in indx and 'KeySchema' not in rawG:
                    printer( vlu)
                    if vlu is None:
                        printer ('[W] None found in %s'%indx)
                        continue
                    #print '  &&&*** &&&'
                    #print indx
                    atv = vlu.split('.')
                    rawG['KeySchema'] = [{'KeyType': v.split(':')[1].upper(), 'AttributeName': v.split(':')[0]} for v in atv]
                else:
                    printer( ' [E]  in gsi lookup')


            else:
                printer( '  0006')
                gsi[gsi_group][indx] = vlu
                printer( gsi[gsi_group])
        #print '  ---7-->'
        for a,e in gsi.items():
            # move LSI from GSI dict to own lsi for reference
            if 'LSI' == e['Type']:
                lsi[gsi_group] = copy.copy(e)
                del gsi[a]
        return (gsi,lsi)

######################################
####          !!NEW TABLE!!!   #######
######  ADD TO GIVEN OBJECT    #######
######################################
    def tableNew(self,currentSection, currentEnv,row, obj,action,delimiter):
        #alast = row.split(delimiter)
        alast = row
        #conHead =currentSection.split(delimiter)
        conHead =currentSection
        printer( '   99  99  99  ')
        printer( conHead)
        printer( '   99  99  99  ')
        printer( row)
        printer( '   %%%%%%%%%%%%%%%%% ')
        count=0
        config={}
        if action:
            actON=alast[0]
            alast=alast[1:]
            conHead=conHead[1:]
        if alast[0].isspace() or alast[0] == '':
            return ''
        tableName=alast[0]#.replace('"','')
        for a in alast:
            indx = conHead[count]
            vlu =a

            if ':' in a:
                vl = a.split('.')
                if 'Partition' in indx:  #{'KeyType:HASH', 'AttributeName':'myname'}
                    #vlu =  '.'.join('%s:%s'%(t['AttributeName'],t['KeyType']) for t in keys)
                    #vlu =  {'%s:%s'%(t['AttributeName'],t['KeyType']) for t in vl}
                    vlu = [ {'AttributeName':g.split(':')[0] ,'KeyType':g.split(':')[1].upper()} for g in vl ]
                elif 'Columns' in indx:  #{'AttributeName':'myname','AttributeType':'S'}
                    vlu = [ {'AttributeName':g.split(':')[0] ,'AttributeType':g.split(':')[1]} for g in vl ]
            if indx=='' and indx==vlu:
                count+=1
                continue
            config[indx]=vlu
            count +=1
            ## ADD ATTRIBUTES/COLUMNS HERE
        #print ('  ...tnew 1')
        # print (row)
        # print (currentSection)
        #print (config)
        #print ('  ...tnew 2')
        if action:
            config.update({'A C T I O N':actON})
        table = {'config':config, 'rows':[]}  #{keys:{val1:string,val2:int},records:[{column:value}]}


        ## CURENTENV IS EMPTY FIND OUT WHY!!1

        printer(' say what ::::: %s and %s'%(currentEnv,tableName))
        obj[ (currentEnv) ]['tables'][tableName]=table
        return tableName


    def tableReset(self,currentObj, newEnvironment):
        currentObj.columns=currentObj.section=''
        currentObj.env = newEnvironment