from collections import defaultdict
import pprint
from django import forms
import mysql.connector as sql

class DBConnection:
    '''
    Database credentials.
    '''
    def __init__(self, user, password, host, database):
        self.user = user
        self.password = password
        self.host = host
        self.database = database
        self.check_connection()

    def check_connection(self):
        try:
            con = sql.connect(user=self.user, password=self.password, host=self.host, database=self.database)
            con.close()
        except Exception,e:
            raise Exception('Problem connecting to the database. Please re-check your credentials.')

    def connect(self):
        return sql.connect(user=self.user, password=self.password, host=self.host, database=self.database)

class DBContext:
    def __init__(self, connection, find_connections=False):
        '''
        Initializes the fields:
            tables:           list of selected tables
            cols:             dict of columns for each table
            all_cols:         dict of columns for each table (even unselected)
            col_vals:         available values for each table/column 
            connected:        dict of table pairs and the connected columns
            fkeys:            foreign keys in a given table
            pkeys:            private key for a given table
            target_table:     selected table for learning
            target_att:       selected column for learning
        '''
        self.connection = connection
        con = connection.connect()
        cursor = con.cursor()
        cursor.execute('SHOW tables')
        self.tables = [table for (table,) in cursor]
        self.cols = {}
        for table in self.tables:
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = '%s' AND table_schema='%s'" % (table,connection.database))
            self.cols[table] = [col for (col,) in cursor]
        self.all_cols = dict(self.cols)
        self.col_vals = {}

        self.connected = defaultdict(list)
        cursor.execute(
           "SELECT table_name, column_name, referenced_table_name, referenced_column_name \
            FROM information_schema.KEY_COLUMN_USAGE \
            WHERE referenced_table_name IS NOT NULL AND table_schema='%s'" % connection.database)
        self.fkeys = defaultdict(set)
        self.pkeys = {}
        if find_connections:
            for table in self.tables:
                for col in self.cols[table]:
                    if col.endswith('_id'):
                        ref_table = (col[:-4] + 'ies') if col[-4] == 'y' else (col[:-3] + 's')
                        if ref_table in self.tables:
                            self.connected[(table, ref_table)].append((col, 'id'))
                            self.connected[(ref_table, table)].append(('id', col))
                            self.fkeys[table].add(col)
                    if col == 'id':
                        self.pkeys[table] = col
        for (table, col, ref_table, ref_col) in cursor:
            self.connected[(table, ref_table)].append((col, ref_col))
            self.connected[(ref_table, table)].append((ref_col, col))
            self.fkeys[table].add(col)


        cursor.execute(
            "SELECT table_name, column_name \
             FROM information_schema.KEY_COLUMN_USAGE \
             WHERE constraint_name='PRIMARY' AND table_schema='%s'" % connection.database)
        for (table, pk) in cursor:
            self.pkeys[table] = pk
        self.target_table = self.tables[0]
        self.target_att = None
        con.close()

    def update(self, postdata):
        '''
        Updates the default selections with user's selections.
        '''
        widget_id = postdata.get('widget_id')[0]
        self.target_table = postdata.get('target_table%s' % widget_id)[0]
        self.target_att = postdata.get('target_att%s' % widget_id)[0]
        #self.target_att_val = postdata.get('target_att_val%s' % widget_id)[0]
        self.tables = postdata.get('tables%s' % widget_id, [])
        if self.target_table not in self.tables:
            raise Exception('The selected target table "%s" is not among the selected tables.' % self.target_table)
        # Propagate the selected tables
        for table in self.cols.keys():
            if table not in self.tables:
                del self.cols[table]
        for pair in self.connected.keys():
            if pair[0] in self.tables and pair[1] in self.tables:
                continue
            del self.connected[pair]
        for table in self.tables:
            self.cols[table] = postdata.get('%s_columns%s' % (table, widget_id), [])
            if table == self.target_table and self.target_att not in self.cols[table]:
                raise Exception('The selected target attribute ("%s") is not among the columns selected for the target table ("%s").' % (self.target_att, self.target_table))

    def fmt_cols(self, cols):
        return ','.join(["`%s`" % col for col in cols])

    def rows(self, table, cols):
        con = self.connection.connect()
        cursor = con.cursor() 
        cursor.execute("SELECT %s FROM %s" % (self.fmt_cols(cols), table))
        con.close()
        return [cols for cols in cursor]

    def fetch_types(self, table, cols):
        '''
        Returns a dictionary of field types for the given table and columns.
        '''
        con = self.connection.connect()
        cursor = con.cursor() 
        cursor.execute("SELECT %s FROM `%s` LIMIT 1" % (self.fmt_cols(cols), table))
        cursor.fetchall()
        types = {}
        for desc in cursor.description:
            types[desc[0]] = sql.FieldType.get_info(desc[1])
        con.close()
        return types

    def compute_col_vals(self):
        import time
        con = self.connection.connect()
        cursor = con.cursor()
        for table, cols in self.cols.items():
            self.col_vals[table] = {}
            for col in cols:
                cursor.execute("SELECT DISTINCT BINARY `%s`, `%s` FROM `%s`" % (col, col, table))
                self.col_vals[table][col] = [val for (_,val) in cursor]
        con.close()

    def __repr__(self):
        return pprint.pformat({
            'target_table' : self.target_table, 
            'target attribute' : self.target_att, 
            'tables' : self.tables, 
            'cols' : self.cols, 
            'connected' : self.connected, 
            'pkeys' : self.pkeys, 
            'fkeys' : self.fkeys 
        })

