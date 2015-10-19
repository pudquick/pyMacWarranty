#!/usr/bin/env python

# Version 2.1
# Apple has again changed the warranty lookup method and now redirects to
# a CAPTCHA protected page at https://checkcoverage.apple.com/
# As such, no "online" warranty status is now possible. All warranty
# information is now estimated.
#
# API changes:
# .online_warranty and .offline_warranty are deprecated and both
# now point to the replacement .warranty (which is offline only)

# To use as a python module:
# import getwarranty
# results =  getwarranty.warranty( ... one or more serials ... )

"""Usage: getwarranty [OPTION ...] [SERIAL1 SERIAL2 ...]

List warranty information for one or more Apple devices.

If no serial number is provided on the command-line, the script will
assume it's running on an OS X machine and attempt to query the local
serial number and provide information regarding it.

Default output is "ATTRIBUTE: value", per line. Use the options below
for alternate format output.

Options:
-h, --help          Display this message
-f, --file FILE     Read serial numbers from FILE (one per line)
-o, --output        Save output to specified file instead of stdout
-c, --csv           Output in comma-separated format
-t, --tsv           Output in tab-separated format

Example usage:
Read from file, save to csv:    getwarranty -f serials.txt -o output.csv
Print local serial to stdout:   getwarranty
Several serials to stdout:      getwarranty SERIAL1 SERIAL2 SERIAL3
"""

import sys, subprocess, datetime, os.path, dateutil.parser
import re, types, time, getopt, csv, codecs, cStringIO
import xml.etree.ElementTree as ET 
# import pickle   --- no longer doing pickles, switch to json
try:
    import json
except:
    import simplejson as json

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
            # model_file = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_snippets.pickle'), 'rb')
            model_file = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_snippets.json'), 'r')
            # model_db = pickle.load(model_file)
            model_db = json.load(model_file)
            model_file.close()
        except:
            model_db = {}

def blank_machine_dict():
    return {u'SERIAL_ID': u'',
            u'PROD_DESCR': u'',
            u'ASD_VERSION': u'',
            u'EST_APPLECARE_END_DATE': u'',
            u'EST_MANUFACTURE_DATE': u'',
            u'EST_PURCHASE_DATE': u'',
            u'EST_WARRANTY_END_DATE': u'',
            u'EST_WARRANTY_STATUS': u'',
            u'PURCHASE_DATE': u'',
            u'WARRANTY_END_DATE': u'',
            u'WARRANTY_STATUS': u'',
            u'ERROR_CODE': u''}

def apple_year_offset(dateobj, years=0):
    # Convert to a maleable format
    mod_time = dateobj.timetuple()
    # Offset year by number of years
    mod_time = time.struct_time(tuple([mod_time[0]+years]) + mod_time[1:])
    # Convert back to a datetime obj
    return datetime.datetime.fromtimestamp(int(time.mktime(mod_time)))

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
    if (len(serial) == 11):
        snippet = serial[-3:]
    elif (len(serial) == 12):
        snippet = serial[-4:]
    elif (2 < len(serial) < 5):
        snippet = serial
    else:
        return None
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
        return asd_db.get(prod_descr, u'')
    except:
        return u''

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
    manu_date  = details[u'EST_MANUFACTURE_DATE']
    prod_descr = details[u'PROD_DESCR']
    iOS_device = re.compile('(iPhone|iPad|iPod)')
    if (iOS_device.match(prod_descr)):
        # iOS: Use date of manufacture + 2 years for max AppleCare coverage
        return u'' + apple_year_offset(dateutil.parser.parse(manu_date), 2).strftime('%Y-%m-%d')
    else:
        # Mac: Use date of manufacture + 3 years for max AppleCare coverage
        return u'' + apple_year_offset(dateutil.parser.parse(manu_date), 3).strftime('%Y-%m-%d')

def offline_estimated_warranty_end_date(details):
    manu_date  = details[u'EST_MANUFACTURE_DATE']
    return u'' + apple_year_offset(dateutil.parser.parse(manu_date), 1).strftime('%Y-%m-%d')

def warranty_generator(*serials):
    # One or more arguments can be passed.
    # The arguments can be a single string or a sequence of strings
    for serial in serials:
        if (not hasattr(serial, "strip") and hasattr(serial, "__getitem__") or hasattr(serial, "__iter__")):
            # Iterable, but not a string - recurse using items of the sequence as individual arguments
            for result in warranty_generator(*serial):
                yield result
        else:
            # Assume string and continue
            prod_dict = blank_machine_dict()
            prod_dict[u'SERIAL_ID'] = serial
            try:
                prod_descr = online_snippet_lookup(prod_dict[u'SERIAL_ID'])
            except:
                prod_descr = offline_snippet_lookup(prod_dict[u'SERIAL_ID'])
            if (not prod_descr):
                prod_dict[u'ERROR_CODE'] = u'Unknown model snippet'
                yield prod_dict
                continue
            prod_dict[u'PROD_DESCR'] = u'' + prod_descr
            # Fill in some details with estimations
            try:
                prod_dict[u'EST_MANUFACTURE_DATE'] = offline_estimated_manufacture(serial)
            except:
                prod_dict[u'EST_MANUFACTURE_DATE'] = u''
            if (prod_dict[u'EST_MANUFACTURE_DATE']):
                # Try to estimate when coverages expire
                prod_dict[u'EST_PURCHASE_DATE'] = u'' + prod_dict[u'EST_MANUFACTURE_DATE']
                prod_dict[u'EST_WARRANTY_END_DATE'] = offline_estimated_warranty_end_date(prod_dict)
                prod_dict[u'EST_APPLECARE_END_DATE'] = offline_estimated_applecare_end_date(prod_dict)
                if (datetime.datetime.now() > dateutil.parser.parse(prod_dict[u'EST_APPLECARE_END_DATE'])):
                    prod_dict[u'EST_WARRANTY_STATUS'] = u'EXPIRED'
                elif (datetime.datetime.now() > dateutil.parser.parse(prod_dict[u'EST_WARRANTY_END_DATE'])):
                    prod_dict[u'EST_WARRANTY_STATUS'] = u'APPLECARE'
                else:
                    prod_dict[u'EST_WARRANTY_STATUS'] = u'LIMITED'
            yield prod_dict

def warranty(*serials):
    if not serials:
        return None
    results = list(warranty_generator(serials))
    if (len(serials) == 1) and (len(results) == 1):
        if (hasattr(serials[0], "strip") and hasattr(serials[0], "__getitem__") and not hasattr(serials[0], "__iter__")):
            return results[0]
    return results

# Deprecated, see notes above
online_warranty_generator = warranty_generator

# Deprecated, see notes above
online_warranty = warranty

# Deprecated, see notes above
offline_warranty_generator = warranty_generator

# Deprecated, see notes above
offline_warranty = warranty

def my_serial():
    return [x for x in [subprocess.Popen("system_profiler SPHardwareDataType |grep -v tray |awk '/Serial/ {print $4}'", shell=True, stdout=subprocess.PIPE).communicate()[0].strip()] if x]

class UnicodeWriter:
    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()
    def writerow(self, row):
        temp = []
        for s in row:
            if (type(s) == types.IntType):
                temp.append(str(s))
            else:
                temp.append(s)
        self.writer.writerow([s.encode("utf-8") for s in temp])
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)
    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

def usage():
    print __doc__
    sys.exit()

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hf:o:ct", ["help", "file=", "output=","csv","tsv"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
    outfile,format = None,None
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
        elif o in ("-f", "--file"):
            try:
                f = open(a, "rb")
            except:
                print "Unable to read file:", a
                usage()
            args = [line for line in f.read().splitlines() if line.strip()]
            f.close()
        elif o in ("-o", "--output"):
            outfile = a
        elif o in ("-c", "--csv"):
            format = "csv"
        elif o in ("-t", "--tsv"):
            format = "tsv"
    # Whatever args remain are considered serials
    serials = args
    warranty_dicts = []
    for serial in (serials or my_serial()):
        results = warranty(serial)
        if type(results) == types.DictType:
            results = [results]
        warranty_dicts.extend(results)
    csv.register_dialect('exceltab', delimiter='\t')
    csv.register_dialect('excel', delimiter=',')
    # writer = UnicodeWriter(outfile, dialect='exceltab')
    if (not format):
        plain_format = ""
        for result in warranty_dicts:
            plain_format += "%s: %s\n" % (u'SERIAL_ID', result[u'SERIAL_ID'])
            plain_format += "%s: %s\n" % (u'PROD_DESCR', result[u'PROD_DESCR'])
            for key,val in sorted(result.items(), key=lambda x: x[0]):
                if (key not in (u'SERIAL_ID', u'PROD_DESCR', u'ERROR_CODE')):
                    plain_format += "%s: %s\n" % (key, val)
            plain_format += "%s: %s\n\n" % (u'ERROR_CODE', result[u'ERROR_CODE'])
        if (not outfile):
            sys.stdout.write(plain_format)
        else:
            open(outfile,"wb").write(plain_format)
    elif (format in ['csv','tsv']):
        if (not outfile):
            outfile = sys.stdout
        else:
            outfile = open(outfile, "wb")
        dialect = {'csv': 'excel', 'tsv': 'exceltab'}[format]
        writer = UnicodeWriter(outfile, dialect=dialect)
        # write out headers
        sample_machine = blank_machine_dict()
        header_row = [u'SERIAL_ID', u'PROD_DESCR']
        for key,val in sorted(sample_machine.items(), key=lambda x: x[0]):
            if (key not in (u'SERIAL_ID', u'PROD_DESCR', u'ERROR_CODE')):
                header_row.append(key)
        header_row.append(u'ERROR_CODE')
        writer.writerow(header_row)
        for result in warranty_dicts:
            row_data = [result[u'SERIAL_ID']]
            row_data.append(result[u'PROD_DESCR'])
            for key,val in sorted(result.items(), key=lambda x: x[0]):
                if (key not in (u'SERIAL_ID', u'PROD_DESCR', u'ERROR_CODE')):
                    row_data.append(val)
            row_data.append(result[u'ERROR_CODE'])
            writer.writerow(row_data)

if __name__ == "__main__":
    main()
