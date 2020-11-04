#!/usr/bin/python

import datetime
import sys
import json
import os
import shlex
from ansible.module_utils.basic import AnsibleModule

date = str(datetime.datetime.now())
print json.dumps({
    "time" : date
})


if __name__ == '__main__':
    main()