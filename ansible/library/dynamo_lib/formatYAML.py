from context import FormatContext
import pyaml
import yaml
import decimal


class FormatSafeDumper(yaml.SafeDumper):
    def represent_decimal(self, data):
        return self.represent_scalar('tag:yaml.org,2002:str', str(data))
    def represent_set(self, data):
        return self.represent_sequence('tag:yaml.org,2002:seq', list(data))

FormatSafeDumper.add_representer(decimal.Decimal, FormatSafeDumper.represent_decimal)
FormatSafeDumper.add_representer(set, FormatSafeDumper.represent_set)
FormatSafeDumper.add_representer(tuple, FormatSafeDumper.represent_set)

# def unicode_representer(dumper, uni):
#     node = yaml.ScalarNode(tag=u'tag:yaml.org,2002:str', value=uni)
#     return node
#
# yaml.add_representer(unicode, unicode_representer)

moduleIN=None
def printer(msg):
    moduleIN.printer(msg)
def printColor(msg):
    moduleIN.printcolor(msg)

class YAML(FormatContext):
    def __init__(self, pathfile,ansible):
        global moduleIN
        super(YAML, self).__init__(pathfile,ansible)
        self._extension = 'yaml'
        #self._service_name = 'dynamodb'
        moduleIN = self


    def fileRead(self, item):
        pass
    def dbRead(self, item):
        pass

    def load(self,section,envs=None,index=None):
        fullpath = '%s.%s' % (self._filepath, self._extension)
        with open(fullpath, newline='') as stream:
            data=yaml.load(stream)
        #
        # for d in data:
        #     print d
        return data


    def write(self, item, option=''):
        fullpath='%s%s.%s'%(self._filepath,option,self._extension)
        with open(fullpath, 'wb') as outfile:
            yaml.dump(item, outfile, default_flow_style=False, encoding='utf-8', allow_unicode=True, Dumper=FormatSafeDumper)
        return fullpath

    def dump(self, item):
        pass

