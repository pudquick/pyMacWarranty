#!/usr/bin/env python

# Note: Mid August 2012, Apple removed the warranty status JSON URL located at:
# https://selfsolve.apple.com/warrantyChecker.do
# This version of the code (tag: v1.0) is preserved for historical purposes. 

http://support-sp.apple.com/sp/product?cc=%s&lang=en_US

import sys, json, subprocess, datetime, os.path, pickle, dateutil.parser, re

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
                 ('EST_MANUFACTURED_DATE', 'Estimated Manufacture Date'))

standard_offline_keys = (('PROD_DESCR', 'Product Description'),
                 ('SERIAL_ID', 'Serial Number'),
                 ('EST_MANUFACTURED_DATE', 'Estimated Manufacture Date'),
                 ('EST_APPLECARE_END_DATE', 'Estimated AppleCare End Date'),
                 ('EST_APPLECARE_STATUS', 'Estimated AppleCare Status'))

asd_db = {}

try:
    model_file = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_snippets.pickle'), 'rb')
    model_db = pickle.load(model_file)
    model_file.close()
except:
    model_db = {}

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

def get_estimated_manufacture(serial):
    # http://www.macrumors.com/2010/04/16/apple-tweaks-serial-number-format-with-new-macbook-pro/
    est_date = u''
    if 10 < len(serial) < 13:
        if len(serial) == 11:
            # Old format
            year = serial[2].lower()
            est_year = 2000 + '   3456789012'.index(year)
            week = int(serial[3:5]) - 1
            year_time = datetime.date(year=est_year, month=1, day=1)
            if (week):
                week_dif = datetime.timedelta(weeks=week)
                year_time += week_dif
            est_date = u'' + year_time.strftime('%Y-%m-%d')
        else:
            # New format
            alpha_year = 'cdfghjklmnpqrstvwxyz'
            year = serial[3].lower()
            est_year = 2010 + (alpha_year.index(year) / 2)
            # 1st or 2nd half of the year
            est_half = alpha_year.index(year) % 2
            week = serial[4].lower()
            alpha_week = ' 123456789cdfghjklmnpqrtvwxy'
            est_week = alpha_week.index(week) + (est_half * 26) - 1
            year_time = datetime.date(year=est_year, month=1, day=1)
            if (est_week):
                week_dif = datetime.timedelta(weeks=est_week)
                year_time += week_dif
            est_date = u'' + year_time.strftime('%Y-%m-%d')
    return est_date

def coverage_date(details):
    coverage = 'EXPIRED'
    if (details.has_key('COV_END_DATE') and (details['COV_END_DATE'] != u'')):
        coverage = 'COV_END_DATE'
    if (details.has_key('HW_END_DATE')):
        coverage = 'HW_END_DATE'
    return (coverage, 'Coverage')

def offline_coverage_status(details):
    coverage = 'EXPIRED'
    date_expires = dateutil.parser.parse(details['EST_APPLECARE_END_DATE'])
    today = datetime.datetime.today()
    if (today <= date_expires):
        coverage = 'ACTIVE'
    return coverage

def get_estimated_applecare_end_date(details):
    manu_date  = details['EST_MANUFACTURED_DATE']
    prod_name  = details['PROD_DESCR']
    iOS_device = re.compile('(iPhone|iPad|iPod)')
    if (iOS_device.match(prod_name)):
        # Use date of manufacture + 2 years for max AppleCare coverage
        return u'' + (dateutil.parser.parse(manu_date) + datetime.timedelta(weeks=(52*2))).strftime('%Y-%m-%d')
    else:
        # Use date of manufacture + 3 years for max AppleCare coverage
        return u'' + (dateutil.parser.parse(manu_date) + datetime.timedelta(weeks=(52*3))).strftime('%Y-%m-%d')

def get_warranty(*serials):
    for serial in serials:
        info = warranty_json(serial)
        if (info.has_key('ERROR_CODE')):
            print "ERROR: Invalid serial: %s\n" % (serial)
        else:
            info[u'EST_MANUFACTURED_DATE'] = get_estimated_manufacture(serial)
            for key,label in (standard_keys + (coverage_date(info), asd_version(info))):
                print "%s: %s" % (label, info.get(key, key))

def offline_warranty_json(sn):
    offline_warranty = dict()
    offline_warranty['PROD_DESCR'] = get_snippet(sn)
    if (offline_warranty['PROD_DESCR']):
        offline_warranty['SERIAL_ID'] = sn
        return offline_warranty
    else:
        return {'ERROR_CODE': 'Unidentified model'}

def get_offline_warranty(*serials):
    for serial in serials:
        info = offline_warranty_json(serial)
        if (info.has_key('ERROR_CODE')):
            print "ERROR: Unidentified model snippet: %s\n" % (serial)
        else:
            info[u'EST_MANUFACTURED_DATE'] = get_estimated_manufacture(serial)
            info[u'EST_APPLECARE_END_DATE'] = get_estimated_applecare_end_date(info)
            info[u'EST_APPLECARE_STATUS'] = offline_coverage_status(info)            
            for key,label in standard_offline_keys:
                print "%s: %s" % (label, info.get(key, key))
            print ""

def get_warranty_dict(serial):
    info = warranty_json(serial)
    if (info.has_key('ERROR_CODE')):
        return None
    else:
        info[u'EST_MANUFACTURED_DATE'] = get_estimated_manufacture(serial)
        return info

def get_my_serial():
    return [x for x in [subprocess.Popen("system_profiler SPHardwareDataType |grep -v tray |awk '/Serial/ {print $4}'", shell=True, stdout=subprocess.PIPE).communicate()[0].strip()] if x]

def get_snippet(serial):
    # http://support-sp.apple.com/sp/product?cc=%s&lang=en_US
    # https://km.support.apple.com.edgekey.net/kb/securedImage.jsp?configcode=%s&size=72x72
    # https://github.com/MagerValp/MacModelShelf
    # Serial Number "Snippet": http://www.everymac.com/mac-identification/index-how-to-identify-my-mac.html
    if (len(serial) == 11):
        snippet = serial[-3:]
    elif (len(serial) == 12):
        snippet = serial[-4:]
    elif (2 < len(serial) < 5):
        snippet = serial
    else:
        return None
    return model_db.get(snippet.upper(), None)

def main():
    for serial in (sys.argv[1:] or get_my_serial()):
        get_warranty(serial)
        
if __name__ == "__main__":
    main()

