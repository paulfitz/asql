# asql

Query a database in natural language.  Uses docker images from 
https://github.com/paulfitz/mlsql - make sure Docker RAM limits
are not too restrictive (should be above 3GB).
 
## Installation

  * `pip install asql` to work with Sqlite or CSV files.
  * `pip install asql[postgres]` to work with PostgreSQL databases.
  * `pip install asql[mysql]` to work with MySQL databases.
  * For other databases, see [SQLAlchemy supported dialects](https://docs.sqlalchemy.org/en/13/dialects/mysql.html).

## Use

Tell `asql` which model to use:

```
# pick one of these
asql --docker sqlova
asql --docker valuenet
```

I suggest you start with just one of these, although you can start both.
The `sqlova` model works on single tables (e.g. a csv file) and can handle queries that take parameters.
The `valuenet` model works on many tables, but is less strong at queries that take parameters.


Tell `asql` which data to use:

```
$ pick one of these
asql --db your_data.csv
asql --db your_data.sqlite
asql --db postgres://user:password@host/database
asql --db mysql://user:password@host/database
```

Don't use on an enormous database just yet.

Now, ask whatever questions you like in plain English, and see what happens:

```
asql how many players are there?
asql which is the longest bridge?
```
