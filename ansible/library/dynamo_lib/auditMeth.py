#!/usr/bin/env python27

import csv
import colorama
from colorama import Fore, Back, Style
import re, string
from decimal import *
from ast import literal_eval
from datetime import datetime
import json
import yaml
import sqlparse
from collections import OrderedDict
from boto3.dynamodb.types import TypeDeserializer,TypeSerializer
deser = TypeDeserializer()
serial=TypeSerializer()
scrubEmails = False
#pickle  not using... not human readable

#used for coloured output  !!not needed in cron
colorama.init()
rs_chr=r'[^\w\d-]'
rs_2=r'(.*)-(.*)-(.*?)$'
rs_3=r'(.*)-(.*)-(.*)-(.*?)$'
rs_4=r'(.*)-(.*)-(.*)-(.*)-(.*?)$'
rs_5=r'(.*)-(.*)-(.*)-(.*)-(.*)-(.*?)$'
rs_ec2=r'(.*)-(.*)-(.*)-\[(.*)\]-(.*)-(.*?)$'
rs_rds=r'(.*)-(.*)-(.*)-\[(.*)\]$'
rs_rgrps=r'(.*)-(.*)-\[(.*)\]-(.*?)$'

isAnsible=False

def printer(msg):
    if not isAnsible:
        print(msg)

def setAnsible(isModule):
    isAnsible=isModule

def upCase(string):
    is_uppercase_letter = True in map(lambda l: l.isupper(), string)
    if not is_uppercase_letter:
        m = re.findall( rs_chr, string)
        if len(m)>0:
            is_uppercase_letter = True

    return is_uppercase_letter
#### checks agains the rs_<segments> above returns total groups(.*) found and a list of each group in order
#### in most cases the first group is the {entity} and the second is the {buisness Unit}
def conforms2Naming(string, regX,env):
    m = re.match( regX, string, re.M)
    #s = re.findall( regX, string)
    namesIn=()
    total=4
    if m:
        num=len(m.groups())
        if m.group(1) is not env and m.group(2) is not env and m.group(3) is not env:
            if num is 4:
                namesIn= (m.group(1),m.group(2),m.group(3),m.group(4))
            if num is 5:
                namesIn= (m.group(1),m.group(2),m.group(3),m.group(4),m.group(5))
                total=5
            if num is 6:
                namesIn= (m.group(1),m.group(2),m.group(3),m.group(4),m.group(5),m.group(6))
                total=6
            if num is 7:
                namesIn= (m.group(1),m.group(2),m.group(3),m.group(4),m.group(5),m.group(6),m.group(7))
                total=7
            return (total,namesIn)
    total=0
    return (total,None)

def poolThreadNumber(totalItems, cpucount = 1):
    print cpucount
    if cpucount==0:
        cpucount=1
    else:
        cpucount=1
    print ('-->%s threads'%(totalItems) )
    pools = 0 if totalItems < 2 else totalItems
    pools = 12*cpucount if totalItems > 12 else pools
    return pools

def namingError(errorInt):
    switcher = {
        1: "[E] Caps",
        2: "[E] Segment",
        3: "[E] Caps/Segment",
        4: "[E] VPC",
        7: "[E] Caps/Segment/VPC"
    }
    return str(switcher.get(errorInt, "CLEAR"))
def namingCrud(changeInt):
    switcher = {
        1: "CREATE",    #CREATE
        2: "UPDATE",    #UPDATE
        3: "DELETE",    #DELETE
        4: "IGNORE",    #IGNORE
        5: "ERROR",     #ERROR
        6: "MATCH",     #MATCHing record
    }
    return str(switcher.get(changeInt, "CLEAR"))
def printColor(a_msg):
    spacer="  "
    msg = a_msg
    #for msg in a_msg:
    if ('[E]' in msg):
        print(Fore.RED + msg + Style.RESET_ALL)
    elif '-----' in msg:
        print(Fore.BLACK +Back.WHITE + msg + Style.RESET_ALL)
    elif '_____' in msg:
        print(spacer+Fore.BLACK +Back.CYAN + msg + Style.RESET_ALL)
    elif '.....' in msg:
        print(spacer+spacer+Fore.BLACK +Back.GREEN + msg + Style.RESET_ALL)
    else:
        print (msg)

def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)
def writeToFile(pathandfile, inputmessagestr):
    stream = open(pathandfile, 'w')
    stream.write(inputmessagestr)
    stream.close()



def joinRecordList(aws_rsrc,svc,e,data):

    if  aws_rsrc.has_key('l_%s_%s'%(svc,e)):
         aws_rsrc['l_%s_%s'%(svc,e)]+=data
    else:
         aws_rsrc['l_%s_%s'%(svc,e)]=data
    return aws_rsrc['l_%s_%s'%(svc,e)]


def nameCheck(owner,name,regX,env):
    total,validName=conforms2Naming(name,regX,env)
    upCase(name)
    validCaps=upCase(name)
    audit="PASS2"
    if owner is "":
        owner="NA"
    errorInt=0
    if upCase(name):
        errorInt=1
    if not validName:
        if errorInt is 1:
            errorInt=3
        else:
            errorInt=2
    audit=namingError(errorInt)
    #print audit
    return audit,owner




def convertTypes(value, typein):
    if 'StringSet' in typein:
        #return serial.serialize(literal_eval(value))
        #printer( 'StringSet'
        if isinstance(value, (tuple, set,list)):
            return value
        return set(literal_eval(value))
    if 'String' in typein:

        #printer( 'String'
        return str(scrubEmail(value))
    if 'Int' in typein:
        return int(value)
    if 'List' in typein:
        #printer( '      --)))(> convertTypes'
        #printer( value
        #printer( 'List'
        if isinstance(value, (list)):
            return value
        elif isinstance(value, int):
            return [value]
        return list(literal_eval(pythonStringValidate(value)))
    elif 'Number' in typein:
        #printer( 'StringSet'
        if isinstance(value,(int,long,Decimal, float)):
            return value
        elif value == '':
            return 0
        return Decimal(value) if '.' in value else int(value)
    elif 'Map' in typein:
        printer( 'Map')
        #printer( value)
        if isinstance(value, (dict)):
            return value
        return json.loads(value,parse_float =Decimal)
    elif 'Bool' in typein:
        #printer( 'Bool')
        if isinstance(value,(bool)):
            return value
        return True if 'true' in value.lower() else False

def pythonStringValidate(value):
    if 'true' in value:
        value=value.replace('true','True')
    if 'false' in value:
        value =value.replace('false','False')
    if 'none' in value:
        value =value.replace('none','None')
    printer( value)
    return value

#String Binary Number StringSet NumberSet BinarySet Map List Boolean Null
def generateHeader(jsonTxt, lastHeader=[]):
    header=[]
    for key in jsonTxt:
        value = jsonTxt[(key)]
        if isinstance(value,(basestring)):
            typ='String'
        elif isinstance(value, (bool)):
            typ = 'Boolean'
        elif isinstance(value, (int,long,Decimal)):
            typ = 'Number'
        elif isinstance(value, (list)):
            typ = 'List'
        elif isinstance(value, (dict)):
            typ = 'Map'
        elif isinstance(value, (tuple, set)):
            typ = 'StringSet'
        else:
            typ = 'Binary'
            #print jsonTxt
            #break
        header.append('%s:%s'%(key,typ))
    if len(lastHeader) is len(header):
        return None
    return header



#CONVERTS to PYTHON objects
def generateRow(jsonTxt):
    values = []
    for key in jsonTxt:
        value = jsonTxt[(key)]
        print value
        if isinstance(value,(basestring)):
            try:
                value = value.stip() if len(value)>500 else value
            except:
                value = unicode.strip(value) if len(value)>500 else value
                value = value.replace('\n', '')
                value=scrubEmail(value)
        else:
            value =convertPythonValue(value)

        values.append(value)
    #value = deser.deserialize(jsonTxt[(key)])
    #print value
    return values

def scrubEmail(value):
    newvalue=value
    if scrubEmails:
        if re.match(r'(\w+[.|\w])*@(\w+[.])(\w)', value, re.M):
            pass

    return newvalue
def convertDynamoType(type,value):
    if 'S' in type:
        return str(value)
    if 'B' in type:
        return bool(value)
    if 'N' in type:
        return Decimal(value)
    return None
def convertPythonValue(value):
    print '             -------->convertPythonValue  '
    print value
    if isinstance(value, (basestring)):
        print 'string'
        return value
    elif isinstance(value, (bool)):
        print 'bool'
        return value
    elif isinstance(value, (int, long, Decimal)):
        print 'decimal'
        return value
    elif isinstance(value, (list)):
        print 'list' #list
        #make sure we don't have odd values in list
        return json.dumps(value,cls=DecimalEncoder)
        #return  serial.serialize(value)
    elif isinstance(value, (dict)):
        print 'map'
        #return json.dumps(value)
        return json.dumps(value,cls=DecimalEncoder)
    elif isinstance(value, (tuple, set)):
        print 'set'
        settn=list(value)
        #return repr(value)
        #return json.dumps(value,cls=DecimalEncoder)
        return json.dumps(settn,cls=DecimalEncoder)
    else:
        print '...'
        return value

def convertAcceptedRowValue(row):
    for r,value in row.items():
        if isinstance(value, ( float)):
            print '---- float found',value
            row[r]=Decimal(value)
    return row

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o,Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


class CommonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o,(tuple,set)):
            return list(o)
        if isinstance(o,Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)

        if isinstance(o, datetime):
            serial = o.isoformat()
            return serial
        return super(CommonEncoder, self).default(o)

