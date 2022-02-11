# Log2SQL

```
Usage: Log2SQL.py [options] {-|inputfile}

Convert variable logfile format input to SQL INSERT statements

positional arguments:
  inputfile             log file source(s)

optional arguments:
  -h, --help            show this help message and exit
  -t TEMPLATE, --template TEMPLATE
                        template for what lines look like (may be repeated)
  -d DATADESC, --data DATADESC
                        description of the fields to send to the database
  -s DATABASE, --sql DATABASE
                        sqlite database to write do (if not present, output
                        SQL statements
  --date DATEFORMAT     date-field format
  --time TIMEFORMAT     time-field format
  -v, --verbose         show what's happening (repeat for more)
  -i, --info            more information on --template and --data
  -c, --case            field names are case-sensitive
  -a, --all             include all results (else filter intermediate
                        duplicates)
  -k, --keep            keep duplicates in the table (otherwise delete after
                        processing.
  -m, --midpoints       keep midpoints the table (otherwise delete after
                        processing.
```
