#!/usr/bin/env python

# Version 2.0
# Note: Mid August 2012, Apple removed the warranty status JSON URL located at:
# https://selfsolve.apple.com/warrantyChecker.do
# That version of the code (tag: v1.0) is preserved for historical purposes.
# To download it, visit this URL:
# https://github.com/pudquick/pyMacWarranty/tree/813f64166ae5fecce57387e70366c383aeb98c0c

# Recommended usage for version 2.0+:
# import getwarranty
# results =  getwarranty.online_warranty( ... one or more serials ... )
# results = getwarranty.offline_warranty( ... one or more serials ... )

import sys, subprocess, datetime, os.path, pickle, dateutil.parser, re
import xml.etree.ElementTree as ET 

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

asd_db = {}
model_db = {}

def init_asd_db():
    global asd_db
    if (not asd_db):
        try:
            response = requests.get('https://raw.github.com/stefanschmidt/warranty/master/asdcheck')
            for model,val in [model_str.strip().split(':') for model_str in response.content.split('\n') if model_str.strip()]:
                asd_db[model] = val
        except:
            asd_db = {}

def init_model_db():
    global model_db
    if (not model_db):
        try:
            model_file = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_snippets.pickle'), 'rb')
            model_db = pickle.load(model_file)
            model_file.close()
        except:
            model_db = {}

def offline_snippet_lookup(serial):
    # http://support-sp.apple.com/sp/product?cc=%s&lang=en_US
    # https://km.support.apple.com.edgekey.net/kb/securedImage.jsp?configcode=%s&size=72x72
    # https://github.com/MagerValp/MacModelShelf
    # Serial Number "Snippet": http://www.everymac.com/mac-identification/index-how-to-identify-my-mac.html
    global model_db
    init_model_db()
    if (len(serial) == 11):
        snippet = serial[-3:]
    elif (len(serial) == 12):
        snippet = serial[-4:]
    elif (2 < len(serial) < 5):
        snippet = serial
    else:
        return None
    return model_db.get(snippet.upper(), None)

def online_snippet_lookup(serial):
    snippet = serial[-3:]
    if (len(serial) == 12):
        snippet = serial[-4:]
    try:
        prod_xml = requests.get('http://support-sp.apple.com/sp/product', params={'cc': snippet, 'lang': 'en_US'}).content
        prod_descr = ET.fromstring(prod_xml).find('configCode').text
    except:
        return None
    return prod_descr

def online_asd_version(prod_descr):
    global asd_db
    init_asd_db()
    try:
        return asd_db.get(prod_descr, 'NOT FOUND')
    except:
        return 'NOT FOUND'

def online_snippet_lookup(serial):
    snippet = serial[-3:]
    if (len(serial) == 12):
        snippet = serial[-4:]
    try:
        prod_xml = requests.get('http://support-sp.apple.com/sp/product', params={'cc': snippet, 'lang': 'en_US'}).content
        prod_descr = ET.fromstring(prod_xml).find('configCode').text
    except:
        return None
    return prod_descr

def offline_estimated_manufacture(serial):
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

def offline_estimated_applecare_end_date(details):
    manu_date  = details['EST_MANUFACTURED_DATE']
    prod_descr = details['PROD_DESCR']
    iOS_device = re.compile('(iPhone|iPad|iPod)')
    if (iOS_device.match(prod_descr)):
        # Use date of manufacture + 2 years for max AppleCare coverage
        return u'' + (dateutil.parser.parse(manu_date) + datetime.timedelta(weeks=(52*2))).strftime('%Y-%m-%d')
    else:
        # Use date of manufacture + 3 years for max AppleCare coverage
        return u'' + (dateutil.parser.parse(manu_date) + datetime.timedelta(weeks=(52*3))).strftime('%Y-%m-%d')

def offline_estimated_warranty_end_date(details):
    manu_date  = details['EST_MANUFACTURED_DATE']
    return u'' + (dateutil.parser.parse(manu_date) + datetime.timedelta(weeks=(52*1))).strftime('%Y-%m-%d')

def online_warranty(*serials):
    # One or more arguments can be passed.
    # The arguments can be a single string or a sequence of strings
    # URLs used in the new code:
    # For product description pre-verification: http://support-sp.apple.com/sp/product?cc=SNIPPET&lang=en_US
    # For warranty status: https://selfsolve.apple.com/wcResults.do?sn=SERIAL&Continue=Continue&cn=&locale=&caller=&num=0

    for serial in serials:
        if (not hasattr(serial, "strip") and hasattr(serial, "__getitem__") or hasattr(serial, "__iter__")):
            # Iterable, but not a string - recurse using items of the sequence as individual arguments
            for result in online_warranty(*serial):
                yield result
        else:
            # Assume string and continue
            prod_dict = {u'SERIAL_ID': u'' + serial}
            prod_descr = online_snippet_lookup(prod_dict[u'SERIAL_ID'])
            if (not prod_descr):
                prod_dict[u'ERROR_CODE'] = u'Unknown model snippet'
                yield prod_dict
                continue
            prod_dict[u'PROD_DESCR'] = u'' + prod_descr
            prod_dict[u'ASD_VERSION'] = online_asd_version(prod_dict[u'PROD_DESCR'])
            warranty_status = requests.get('https://selfsolve.apple.com/wcResults.do',
                params={'sn': serial, 'Continue': 'Continue', 'cn': '', 'locale': '', 'caller': '', 'num': '0'}).content
            if ('sorry, but this serial number is not valid' in warranty_status):
                prod_dict[u'ERROR_CODE'] = u'Invalid serial number'
                yield prod_dict
                continue
            # Fill in some details with estimations
            try:
                prod_dict[u'EST_MANUFACTURED_DATE'] = offline_estimated_manufacture(serial)
            except:
                prod_dict[u'EST_MANUFACTURED_DATE'] = u''
            if (prod_dict[u'EST_MANUFACTURED_DATE']):
                # Try to estimate when coverages expire
                prod_dict[u'EST_WARRANTY_END_DATE'] = offline_estimated_warranty_end_date(prod_dict)
                prod_dict[u'EST_APPLECARE_END_DATE'] = offline_estimated_applecare_end_date(prod_dict)
            try:
                warranty_status = warranty_status.split('warrantyPage.warrantycheck.displayHWSupportInfo')[-1]
                warranty_status = warranty_status.split('Repairs and Service Coverage: ')[1]
                if (warranty_status.startswith('Expired')):
                    prod_dict[u'WARRANTY_STATUS'] = u'EXPIRED'
                else:
                    prod_dict[u'WARRANTY_STATUS'] = u'ACTIVE'
            except:
                prod_dict[u'ERROR_CODE'] = u'Unknown warranty status'
                yield prod_dict
                continue
            if (prod_dict[u'WARRANTY_STATUS'] == u'ACTIVE'):
                try:
                    coverage_end_date = dateutil.parser.parse(warranty_status.split('Estimated Expiration Date: ')[1].split('<')[0])
                    prod_dict[u'WARRANTY_END_DATE'] = u'' + coverage_end_date.strftime('%Y-%m-%d')
                except:
                    prod_dict[u'ERROR_CODE'] = u'Cannot parse warranty end date'
                    yield prod_dict
                    continue
            yield prod_dict

def offline_warranty(*serials):
    # One or more arguments can be passed.
    # The arguments can be a single string or a sequence of strings
    for serial in serials:
        if (not hasattr(serial, "strip") and hasattr(serial, "__getitem__") or hasattr(serial, "__iter__")):
            # Iterable, but not a string - recurse using items of the sequence as individual arguments
            for result in offline_warranty(*serial):
                yield result
        else:
            # Assume string and continue
            prod_dict = {u'SERIAL_ID': u'' + serial}
            prod_descr = offline_snippet_lookup(prod_dict[u'SERIAL_ID'])
            if (not prod_descr):
                prod_dict[u'ERROR_CODE'] = u'Unknown model snippet'
                yield prod_dict
                continue
            prod_dict[u'PROD_DESCR'] = u'' + prod_descr
            # Fill in some details with estimations
            try:
                prod_dict[u'EST_MANUFACTURED_DATE'] = offline_estimated_manufacture(serial)
            except:
                prod_dict[u'EST_MANUFACTURED_DATE'] = u''
            if (prod_dict[u'EST_MANUFACTURED_DATE']):
                # Try to estimate when coverages expire
                prod_dict[u'EST_WARRANTY_END_DATE'] = offline_estimated_warranty_end_date(prod_dict)
                prod_dict[u'EST_APPLECARE_END_DATE'] = offline_estimated_applecare_end_date(prod_dict)
                if (datetime.datetime.now() > dateutil.parser.parse(prod_dict[u'EST_APPLECARE_END_DATE'])):
                    prod_dict[u'EST_WARRANTY_STATUS'] = u'EXPIRED'
                elif (datetime.datetime.now() > dateutil.parser.parse(prod_dict[u'EST_WARRANTY_END_DATE'])):
                    prod_dict[u'EST_WARRANTY_STATUS'] = u'APPLECARE'
                else:
                    prod_dict[u'EST_WARRANTY_STATUS'] = u'ACTIVE'
            yield prod_dict

def my_serial():
    return [x for x in [subprocess.Popen("system_profiler SPHardwareDataType |grep -v tray |awk '/Serial/ {print $4}'", shell=True, stdout=subprocess.PIPE).communicate()[0].strip()] if x]

def main():
    for serial in (sys.argv[1:] or my_serial()):
        for result in offline_warranty(serial):
            print "%s: %s" % (u'SERIAL_ID', result[u'SERIAL_ID'])
            if (result.has_key(u'PROD_DESCR')):
                print "%s: %s" % (u'PROD_DESCR', result[u'PROD_DESCR'])
            for key,val in sorted(result.items(), key=lambda x: x[0]):
                if (key not in (u'SERIAL_ID', u'PROD_DESCR', u'ERROR_CODE')):
                    print "%s: %s" % (key, val)
            if (result.has_key(u'ERROR_CODE')):
                print "%s: %s" % (u'ERROR_CODE', result[u'ERROR_CODE'])
        print ""

if __name__ == "__main__":
    main()


