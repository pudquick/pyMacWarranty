#!/usr/bin/env python

import sys, json

try:
    import requests
except:
    # My strange hack to use standard libs, if requests module isn't available
    # http://docs.python-requests.org/en/latest/index.html
    # Really, check it out - it's great
    import urllib, types
    import urllib2 as requests
    setattr(requests,'content','')
    def get(self, urlstr, params={}):
        if (params):
            urlstr += "?%s" % urllib.urlencode(params)
        self.content = self.urlopen(urlstr).read()
        return self
    requests.get = types.MethodType(get,requests)

standard_keys = (('PROD_DESCR', 'Product Description'),
                 ('SERIAL_ID', 'Serial Number'),
                 ('HW_COVERAGE_DESC', 'Warranty Type'),
                 ('PURCHASE_DATE', 'Purchase Date'))

asd_db = {}

def init_asd_db():
    if (not asd_db):
        response = requests.get('https://raw.github.com/stefanschmidt/warranty/master/asdcheck')
        for model,val in [model_str.strip().split(':') for model_str in response.content.split('\n') if model_str.strip()]:
            asd_db[model] = val

def warranty_json(sn, country='US'):
    return json.loads(requests.get('https://selfsolve.apple.com/warrantyChecker.do', params={'country': country, 'sn': sn}).content[5:-1])

def coverage_date(details):
    coverage = 'EXPIRED'
    if (details.has_key('COV_END_DATE') and (details['COV_END_DATE'] != u'')):
        coverage = 'COV_END_DATE'
    if (details.has_key('HW_END_DATE')):
        coverage = 'HW_END_DATE'
    return (coverage, 'Coverage')

def asd_version(details):
    init_asd_db()
    return (asd_db.get(details['PROD_DESCR'], 'Not found')+"\n", 'ASD Version')

def get_warranty(*serials):
    for serial in serials:
        info = warranty_json(serial)
        if (info.has_key('ERROR_CODE')):
            print "ERROR: Invalid key: %s\n" % (serial)
        else:
            for key,label in (standard_keys + (coverage_date(info), asd_version(info))):
                print "%s: %s" % (label, info.get(key, key))

def main():
    for serial in sys.argv[1:]:
        get_warranty(serial)
        
if __name__ == "__main__":
    main()
