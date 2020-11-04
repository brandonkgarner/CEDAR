from context import ProviderContext
from context import FormatContext
from dynamodb import DB_dynamo
from dynamojxtapose import DB_JuxtaDynamo

from formatCSV import CSV
from formatJSON import JSON
from formatYAML import YAML
from formatSQL import SQL


class ProviderGenerate():
    def __init__(self):
        self.service_pool = {}
        self.class_pool = {c.__name__: c for c in ProviderContext.__subclasses__()}
                #(dynamo,8293748927892,ss,)
    def create(self, provider_name, account_id, session, mthread):
        class_name = "DB_%s" % provider_name
        svc_key = "%s_%s" % (str(account_id), class_name)
        if svc_key not in self.service_pool:
            cls = self.__get_class__(class_name)
            self.service_pool[svc_key] = cls(session, account_id,mthread, False)
        return self.service_pool[svc_key]

    def simulate(self, provider_name, region,account_id, client, resource,mthread, ansible=False):
        class_name = "DB_%s" % provider_name
        simulate = 'simulate'
        svc_key = "%s_%s" % (simulate, class_name)
        if svc_key not in self.service_pool:
            cls = self.__get_class__(class_name)
            self.service_pool[svc_key] = cls(None, None,mthread, ansible)
            self.service_pool[svc_key]._setBoth(region, account_id, client,resource)
        return self.service_pool[svc_key]

    def __get_type__(self, type_name):
        pass

    def __get_class__(self, class_name):
        if class_name in self.class_pool:
            return self.class_pool[class_name]

class FormaterGenerate():
    def __init__(self):
        self.convert=''
        self.convert_pool = {}
        self.class_pool = {c.__name__: c for c in FormatContext.__subclasses__()}

    def create(self, provider_name, file_path, ansible=False ):
        class_name = provider_name
        svc_key = "%s_%s" % (str(provider_name), 'aws')
        if svc_key not in self.convert_pool:
            cls = self.__get_class__(class_name)
            self.convert_pool[svc_key] = cls(file_path,ansible)
        return self.convert_pool[svc_key]


    def __get_class__(self, class_name):
        if class_name in self.class_pool:
            return self.class_pool[class_name]
