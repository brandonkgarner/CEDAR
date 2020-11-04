from context import FormatContext
import  json
from auditMeth import CommonEncoder


moduleIN=None
def printer(msg):
    moduleIN.printer(msg)
def printColor(msg):
    moduleIN.printcolor(msg)

class JSON(FormatContext):
    recentInstance = None
    def __init__(self, pathfile,ansible):
        global moduleIN
        super(JSON, self).__init__(pathfile,ansible)
        self._extension = 'json'
        JSON.recentInstance=self
        moduleIN = self


    @staticmethod
    def getInstance():
        return JSON.recentInstance

    def fileRead(self, item):
        pass
    def dbRead(self, item):
        pass
    def load(self,section,envs=None,index=None):
        printer( 'loader....CSV...')
        fullpath='%s.%s'%(self._filepath,self._extension)
        printer( fullpath)
        with open(fullpath, 'rU') as data_file:
            data = json.load(data_file)
        # print '      ***666 ddddduuuudddeee   *********009'
        # for d in data.items():
        #     print d
        # print '      ***777 ddddduuuudddeee   *********009'
        #print '----------------------'
        #print data
        return data



    def write(self, item, option=''):
        fullpath='%s%s.%s'%(self._filepath,option,self._extension)
        printer(fullpath)
        with open(fullpath, 'wb') as outfile:
            json.dump(item, outfile, cls=CommonEncoder, indent=4)
        return self._filepath

    def dump(self, item):
        pass