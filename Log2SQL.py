#!/usr/bin/python3
# NB Visual Studio may prefix the file with \EF \BB \BF
#   strip this with: tail -c +4 iam.py > iam
#
# Log2SQL - convert a variable logfile into SQL Entries
#
# Usage:
#
import os,sys
iam=os.path.splitext(os.path.split(sys.argv[0])[-1])[0]

import argparse
parser=argparse.ArgumentParser(usage="usage: %(prog)s [options] {-|inputfile}",
                               description="Convert variable logfile format input to SQL INSERT statements"
                               )
parser.add_argument("args",metavar="inputfile",nargs="*",help="log file source(s)")
parser.add_argument("-t","--template",dest="template",default="",help="template for what lines look like (may be repeated)")
parser.add_argument("-d","--data",dest="datadesc",default="",help="description of the fields to send to the database")
parser.add_argument("-s","--sql",dest="database",default="",help="sqlite database to write do (if not present, output SQL statements")
parser.add_argument("--date",dest="dateFormat",default="%Y-%m-%d",help="date-field format")
parser.add_argument("--time",dest="timeFormat",default="%H:%M:%S",help="time-field format")
parser.add_argument("-v","--verbose",dest="verbose",default=0,action="count",help="show what's happening (repeat for more)")
parser.add_argument("-i","--info",dest="info",default=0,action="count",help="more information on --template and --data")
parser.add_argument("-c","--case",dest="caseSensitive",default=False,action="store_true",help="field names are case-sensitive")
parser.add_argument("-a","--all",dest="applyFilter",default=True,action="store_false",help="include all results (else filter intermediate duplicates)")
parser.add_argument("-k","--keep",dest="keepDuplicates",default=False,action="store_true",help="keep duplicates in the table (otherwise delete after processing).")
parser.add_argument("-m","--midpoints",dest="keepMidpoints",default=False,action="store_true",help="keep midpoints the table (otherwise delete after processing).")

info=r"\
Format for --template template:\
    template is tested for matches with each line of inputfile using regular expressions\
    Use [name:type] to identify data that is for the SQL column called 'name'\
        type can be:\
            string  - text that is either delimited by single/double quotes, or a word\
            word    - text that is not whitespace\
            time    - a time field (default HH:MM:SS - change with --time)\
            date    - a date field (eg YYYY-mm-dd - change with --date)\
            json    - a json string, which will be decoded into name:value pairs\
\
Format for --data datadesc\
    datadesc describes the fields that will be transferred to the database\
    the format for data resembles a SQL CREATE statement:\
        TABLE(NAME TYPE, ...)\
        where NAME is the field name\
        and TYPE is one of:\
            STRING      - the field will be passed to SQL as a quoted string\
            INTEGER     - the field will be passed to SQL as an integer\
            NUMBER(a.b) - the field will be passed to SQL as a number as aaaa.bb\
            REAL        - the field will be passed to SQL as an IEEE floating point number\
            DATE or TIME or\
            DATETIME - the field will be passed to SQL as an ISO8601 string\
                        Note: if you have a DATE and TIME input field and a DATETIME table field\
                              the table will take the combined value.\
"
# Format of a template:
#   text is just text
#   [name:string] is a word (or quoted string) that will be column named 'text'
#           if :string is omitted, it is assumed
#   [name:word] is a word (not quoted string)
#   [name:date] is a date field
#   [name:time] is a time field
#   [name:json] is a json string, the contents of which will be columns

try:
    options=parser.parse_args()
except:
    print(parser.format_help())
    sys.exit(0)

if options.info > 0:
    print(info.replace('\\',''))
    sys.exit(0)

if len(options.args)==0:
    print(parser.format_help())
    sys.exit(0)

tf={}   #tf is the template format. Elements are (name,format)
tn=[]   #tn is the names of the template formats in order
fre={'string':"(\'[^\']*\'|\"[^\"]*\"|[^/s]+)",
     'word':"([^/s]+)"
     }
numberre='number\((\d*).(\d*)\)'
tt=options.template
data={}     # Initialize data - it needs to be global
datadesc={}
fieldNo=1
import re,json
try:
    xx=re.findall("\[[^\[]*\]",tt)   # search for [text]
    xx.reverse()
    for x in xx:
        tDesc=x[1:-1].split(':')         # remove the enclosing [] and break on ':'
        if not options.caseSensitive:
            tDesc[0]=tDesc[0].lower()
        if tDesc[0] in tf:
            print(format("Duplicate column name: {}. Please use use unique column names.",tDesc[0]))
        if tDesc[0]=="":
            tDesc[0]="Field{:n}".format(fieldNo) 
        if len(tDesc) > 1:               # is a format specified?
            tf[tDesc[0]]=tDesc[1]
        else:
            tf[tDesc[0]]="string"        # no - default to string
        tn.append(tDesc[0])
        retype=tf[tDesc[0]]
        if retype=='json': retype='string' 
        try:
            retype=fre[retype]
        except:
            retype=fre['word']
        tt=tt.replace(x,retype)   # replace the [place holder] with search for "a b", 'a b', or ab
        fieldNo+=1
    tn.reverse()
    if options.verbose>1:
        print("Template: %s [%s]"%(tt,tf))
except:
    print("Error in Template. Please check, or run with --info for more information")
    sys.exit(1)

try:
    dd=options.datadesc.strip('"\'')  # remove any leading/trailing quotes and brackets
    datatable=re.search("[^(]*",dd).group()
    dd=dd[len(datatable):]
    if dd[0]=='(' and dd[-1]==')':
       dd=dd[1:-1]  # remove leading/trailing brackets
    if len(datatable)==0:
        datatable="aTable"
    df=re.split(',',dd)                 # df is now a list of space-delimited name field pairs
    for dff in df:
        dft=re.split(' ',dff.strip())
        datadesc[dft[0]]=dft[1].lower()
    if options.verbose>1:
        print("DataDesc: %s %s [%s]"%(datatable,dd,datadesc))
except:
    print("Error in DataDesc. Please check, or run with --info for more information")
    sys.exit(1)

class Log2SQLFieldNotFound(Exception):
    pass

import datetime

def sqlDataFromRaw(data,sqlData):
    for field in datadesc:
        dField=field if options.caseSensitive else field.lower()              
        if datadesc[field]=='string':
            sqlData[field]="\"{}\"".format(data[dField])
        elif datadesc[field]=='integer':
            sqlData[field]="{:n}".format(int(data[dField]))
        elif datadesc[field][0:6]=='number':
            if dField in data:
                ff=re.search(numberre,datadesc[field])
                if ff:
                    nFormat=":{}.{}f".format(ff.groups(0)[0],ff.groups(0)[1])
                    nFormat="{"+nFormat+"}"
                    nValue=nFormat.format(float(data[dField]))
                    sqlData[field]="{}".format(nValue)
            else:
                raise Log2SQLFieldNotFound
        elif datadesc[field]=='real':
            sqlData[field]="{:e}".format(float(data[dField]))
        elif datadesc[field]=='date':
            value=datetime.strptime(data[dField],options.dateFormat)
            sqlData[field]="\"{}\"".format(value.srftime("%Y-%m-%d"))
        elif datadesc[field]=='time':
            value=datetime.strptime(data[dField],options.timeFormat)
            sqlData[field]="\"{}\"".format(value.srftime("%H:%M:%S"))
        elif datadesc[field]=='datetime':
            value=None  # if we can't get a datetime, we don't want it
            for tfX in tf:
                if tfX in tf and tf[tfX]=='date':
                    dField=tfX if options.caseSensitive else tfX.lower()              
                    try:
                        value=datetime.datetime.strptime(data[dField],options.dateFormat)
                        break
                    except:
                        pass
            for tfX in tf:
                if tfX in tf and tf[tfX]=='time':
                    dField=tfX if options.caseSensitive else tfX.lower()              
                    try:
                        value=datetime.datetime.combine(value.date(),datetime.datetime.strptime(data[dField],options.timeFormat).time())
                        break
                    except:
                        pass
            if value:
                sqlData[field]="\"{}\"".format(value.strftime("%Y-%m-%d %H:%M:%S"))

def sqlInsert(data):
    sqlFields=""
    sqlData=""
    for field in datadesc:
        if len(sqlFields) > 0:
            sqlFields=sqlFields+", "
            sqlData=sqlData+", "
        dField=field if options.caseSensitive else field.lower()              
        if datadesc[field]=='string':
            sqlFields=sqlFields+field
            sqlData=sqlData+"\"{}\"".format(data[dField])
        elif datadesc[field]=='integer':
            sqlFields=sqlFields+field
            sqlData=sqlData+"{:n}".format(int(data[dField]))
        elif datadesc[field][0:6]=='number':
            if dField in data:
                ff=re.search(numberre,datadesc[field])
                if ff:
                    nFormat=":{}.{}f".format(ff.groups(0)[0],ff.groups(0)[1])
                    nFormat="{"+nFormat+"}"
                    nValue=nFormat.format(float(data[dField]))
                    sqlFields=sqlFields+field
                    sqlData=sqlData+"{}".format(nValue)
            else:
                raise Log2SQLFieldNotFound
        elif datadesc[field]=='real':
            sqlFields=sqlFields+field
            sqlData=sqlData+"{:e}".format(float(data[dField]))
        elif datadesc[field]=='date':
            value=datetime.strptime(data[dField],options.dateFormat)
            sqlFields=sqlFields+field
            sqlData=sqlData+"\"{}\"".format(value.srftime("%Y-%m-%d"))
        elif datadesc[field]=='time':
            value=datetime.strptime(data[dField],options.timeFormat)
            sqlFields=sqlFields+field
            sqlData=sqlData+"\"{}\"".format(value.srftime("%H:%M:%S"))
        elif datadesc[field]=='datetime':
            value=None  # if we can't get a datetime, we don't want it
            for tfX in tf:
                if tfX in tf and tf[tfX]=='date':
                    dField=tfX if options.caseSensitive else tfX.lower()              
                    try:
                        value=datetime.datetime.strptime(data[dField],options.dateFormat)
                        break
                    except:
                        pass
            for tfX in tf:
                if tfX in tf and tf[tfX]=='time':
                    dField=tfX if options.caseSensitive else tfX.lower()              
                    try:
                        value=datetime.datetime.combine(value.date(),datetime.datetime.strptime(data[dField],options.timeFormat).time())
                        break
                    except:
                        pass
            if value:
                sqlFields=sqlFields+field
                sqlData=sqlData+"\"{}\"".format(value.strftime("%Y-%m-%d %H:%M:%S"))
    sql="INSERT INTO {} ({}) VALUES ({})".format(datatable,sqlFields,sqlData)
    return sql

def processLine(line,cursor,useCols,selectSQL,insertSQL):
    line=line.strip()
    if options.verbose>1:
        print("Line: %s"%line)
    x=re.search(tt,line)
    if x:
        if options.verbose>1:
            print("Line matches %s"%tt)
        data={}
        for i in range(0,len(tn)):
            s=x.group(i+1)
            if s[0] == "'" or s[0] == '"':
                s=s.strip(s[0])
            data[tn[i]]=s.strip()
            if tf[tn[i]]=='json':
                try:
                    jdata=json.loads(s)
                    for jitem in jdata:
                        data[jitem]=jdata[jitem]
                except:
                    pass
        if options.verbose>1:
            print(data)
        # Filter - when there is a list of records identical except for the time, then filter means keep the first and last
        sqlData={}
        lastSqlData=None
        try:
            if cursor:
                sqlDataFromRaw(data,sqlData)
                cursor.execute(selectSQL,tuple([sqlData[x] for x in useCols ]))
                rows=cursor.fetchall()
                if len(rows)==0: # this row doesn't exist
                    if lastSqlData: # If there is a last row
                        TorF=True
                        try:
                            for x in lastSqlData:
                                if datadesc[x]!='datetime':
                                    if lastSqlData[x]!=sqlData[x]:
                                        TorF=False
                                        break
                        except:
                            TorF=False
                        if TorF: # the last row is the same as this row (but with a different time)
                            pass
            # Now generate the SQL
            try:
                sql=sqlInsert(data)
                sql=insertSQL.replace('?','{}').format(*[sqlData[x] for x in useCols])
                if options.verbose>1 or not cursor:
                    print(sql)
                if cursor:
                    cursor.executescript(sql)
            except Log2SQLFieldNotFound:
                pass
            except Exception as error:
                print("Error: {}".format(error))
        except:
            pass # This exception is when data doesn't match sqlData, so this row should be discarded 

import sqlite3

if options.database=="":
    database=None
    cursor=None
else:
    # Make sure the database has an extension - defaulting to .db if none specified
    dbFile=os.path.splitext(options.database)
    dbFile=dbFile[0]+".db" if dbFile[1]=="" else dbFile[1]
    database=sqlite3.connect(dbFile)
    cursor=database.cursor()
    useCols=[]
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables=[ v[0] for v in cursor.fetchall() if v[0] != 'sqlite_sequence' ]
        if datatable in tables:
            rows=cursor.execute("PRAGMA table_info({})".format(datatable))
            rows=cursor.fetchall()
            for row in rows:    # row[0]=colId, row[1]=name, row[2]=type, row[3]=not null, row[4]=default, row[5]=PK
                if row[1] in datadesc:
                    useCols.append(row[1])
            if not len(useCols)==len(datadesc):
                print("Existing table and Data Description do not match. Please check:")
                for row in rows:
                    print("  "+row[1]+" "+row[2])
                sys.exit(2)
        else:
            cursor.executescript("CREATE TABLE "+options.datadesc.strip('"\''))
    except Exception as error:
        print("Data Description cannot be used to create the table {} - please check.".format(error))
        sys.exit(1)
    selectSQL="SELECT {fields} FROM {table} WHERE {match};".format(table=datatable,fields=", ".join(useCols),match=" AND ".join([x+"=?" for x in useCols]))
    insertSQL="INSERT INTO {table} ({fields}) VALUES ({data});".format(table=datatable,fields=", ".join(useCols),data=", ".join(["?" for x in useCols]))

for arg in options.args:
    if arg == "-":
        if options.verbose>0:
            print('Processing StdIn')
        inStream=sys.stdin
        for line in inStream:
            processLine(line)
    else:
        inFile=arg
        if not os.path.exists(inFile):
            print('inputFile "%s" not found.'%inFile)
            continue
        if options.verbose>0:
            print('Processing %s'%inFile)
        inStream=open(inFile,"r")
    while True:
        line=inStream.readline()
        if line:
           processLine(line,cursor,useCols,selectSQL,insertSQL)
        else:
            break
    # If we've added duplicates, we need to remove them.
    if not options.keepDuplicates:
        sql="DELETE FROM {table} WHERE EXISTS (SELECT 1 FROM {table} T2 WHERE {table}.{datetimeField} = T2.{datetimeField} AND {table}.ROWID > T2.ROWID)".format(table=datatable,datetimeField=[x for x in useCols if datadesc[x]=='datetime'][0])
        if options.verbose > 1:
            print(sql)
        cursor.execute(sql)
        if not options.keepMidpoints:
# Some special SQL to remove all intermediate values (where there is a same-valued record just prior and just after)
            sql=" \
DELETE FROM LOG_TEMPERATURE \
  WHERE rowId in (\
WITH {datetimeField}S AS\
 ( select rowid, LEAD({datetimeField}) OVER (ORDER BY {datetimeField}) as pre{datetimeField}, {datetimeField} as this{datetimeField}, LAG({datetimeField}) OVER(ORDER BY {datetimeField}) as post{datetimeField}\
   from {table}\
   ) \
SELECT rowid \
  FROM {datetimeField}S A \
  WHERE \
".format(table=datatable,datetimeField=[x for x in useCols if datadesc[x]=='datetime'][0])

            # We need where claises for each of the fields that are not the DateTime key
            sql=sql+" AND ".join(["\
     (SELECT PRE.{field}  FROM {table} PRE  WHERE PRE.{datetimeField}  = A.pre{datetimeField})  = (SELECT THIS.{field} FROM {table} THIS WHERE THIS.{datetimeField} = A.this{datetimeField}) \
 AND (SELECT THIS.{field} FROM {table} THIS WHERE THIS.{datetimeField} = A.this{datetimeField}) = (SELECT POST.{field} FROM {table} POST WHERE POST.{datetimeField} = A.post{datetimeField}) \
".format(table=datatable,datetimeField=[x for x in useCols if datadesc[x]=='datetime'][0],field=ff) for ff in useCols if datadesc[ff]!='datetime'])
            sql=sql+')'
            if options.verbose > 1:
                print(sql)
            cursor.execute(sql)
if database:
    database.commit()
