from context import FormatContext
import re

moduleIN=None
def printer(msg):
    moduleIN.printer(msg)
def printColor(msg):
    moduleIN.printcolor(msg)

class SQL(FormatContext):
    def __init__(self, pathfile,ansible):
        global moduleIN
        super(SQL, self).__init__(pathfile,ansible)
        self._extension = 'sql'
        moduleIN = self

    def load(self, pathfile,section,envs=None,index=None):
        sqlCommands=[]
        collection=[]
        pattern = re.compile('(^GO$)')
        create_table = re.compile('(^CREATE TABLE$)')
        with open(pathfile, 'r') as lines:
            for line in lines:
                if pattern.match(line):
                    sqlCommands.append(' '.join(collection))
                    collection=[]
                else:
                    line = line.strip()
                    collection.append(line)
                #print line
        printer( sqlCommands[4])
        if len(sqlCommands) is 0:
            return []
            printer( '...go NOT found')
            fd = open(pathfile, 'rU')
            sqlFile = fd.read()
            fd.close()
            sqlCommands = sqlparse.parse(sqlFile)
        printer( sqlCommands[0])
        return sqlCommands
    def dbRead(self, item):
        pass

    def write(self, item):
        fullpath=None
        return fullpath

    def dump(self, item):
        pass