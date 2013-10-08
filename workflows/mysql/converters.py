'''
Classes for handling DBContexts for ILP systems.

@author: Anze Vavpetic <anze.vavpetic@ijs.si>
'''
import re

class Converter:
    '''
    Base class for converters.
    '''
    def __init__(self, dbcontext):
        self.db = dbcontext
        self.connection = dbcontext.connection.connect()
        self.cursor = self.connection.cursor()

    def __del__(self):  
        self.connection.close()

class ILP_Converter(Converter):
    '''
    Base class for converting between a given database context (selected tables, columns, etc)
    to inputs acceptable by a specific ILP system.

    If possible, all subclasses should use lazy selects by forwarding the DB connection.
    '''
    def __init__(self, *args, **kwargs):
        self.settings = kwargs.pop('settings', {}) if kwargs else {}
        self.discr_intervals = kwargs.pop('discr_intervals', {}) if kwargs else {}
        self.dump = kwargs.pop('dump', False) if kwargs else False
        Converter.__init__(self, *args, **kwargs)

    def user_settings(self):
        return [':- set(%s,%s).' % (key,val) for key, val in self.settings.items()]

    def mode(self, predicate, args, recall=1, head=False):
        return ':- mode%s(%s, %s(%s)).' % ('h' if head else 'b', str(recall), predicate, ','.join([t+arg for t,arg in args]))

    def db_connection(self):
        con = self.db.connection
        host, db, user, pwd = con.host, con.database, con.user, con.password
        return [':- use_module(library(myddas)).', \
                ':- db_open(mysql, \'%s\'/\'%s\', \'%s\', \'%s\').' % (host, db, user, pwd)] + \
               [':- db_import(%s, %s).' % (table, table) for table in self.db.tables]

    def connecting_clause(self, table, ref_table):
        var_table, var_ref_table = table.capitalize(), ref_table.capitalize()
        result=[]
        for pk,fk in self.db.connected[(table, ref_table)]:
            ref_pk = self.db.pkeys[ref_table]
            table_args, ref_table_args = [], []
            for col in self.db.cols[table]:
                if col == pk:
                    col = var_table
                elif col == fk:
                    col = var_ref_table
                table_args.append(col.capitalize())
            for col in self.db.cols[ref_table]:
                if col == ref_pk:
                    col = var_ref_table
                if col == fk:
                    col = var_table
                ref_table_args.append(col.capitalize())
            result.extend(['has_%s(%s, %s) :-' % (ref_table, var_table.capitalize(), var_ref_table.capitalize()),
                            '\t%s(%s),' % (table, ','.join(table_args)),
                            '\t%s(%s).' % (ref_table, ','.join(ref_table_args))])
        return result


    def attribute_clause(self, table, att):
        var_table, var_att, pk = table.capitalize(), att.capitalize(), self.db.pkeys[table]
        intervals = []
        if self.discr_intervals.has_key(table):
            intervals = self.discr_intervals[table].get(att, [])
            if intervals:
                var_att = 'Discrete_%s' % var_att
        values_goal = '\t%s(%s)%s' % (table, ','.join([arg.capitalize() if arg!=pk else var_table for arg in self.db.cols[table]]), ',' if intervals else '.')
        discretize_goals = []
        n_intervals = len(intervals)
        for i, value in enumerate(intervals):
            punct = '.' if i == n_intervals-1 else ';'
            if i == 0:
                # Condition: att =< value_i
                label = '=< %d' % value
                condition = '%s =< %d' % (att.capitalize(), value)
                discretize_goals.append('\t((%s = \'%s\', %s)%s' % (var_att, label, condition, punct))
            if i < n_intervals-1:
                # Condition: att in (value_i, value_i+1]
                value_next = intervals[i+1]
                label = '(%d, %d]' % (value, value_next)
                condition = '%s > %d, %s =< %d' % (att.capitalize(), value, att.capitalize(), value_next)
                discretize_goals.append('\t(%s = \'%s\', %s)%s' % (var_att, label, condition, punct))
            else:
                # Condition: att > value_i
                label = '> %d' % value
                condition = '%s > %d' % (att.capitalize(), value)
                discretize_goals.append('\t(%s = \'%s\', %s))%s' % (var_att, label, condition, punct))
        return ['%s_%s(%s, %s) :-' % (table, att, var_table, var_att),  
                values_goal] + discretize_goals

    @staticmethod
    def numeric(val):
        for num_type in [int, float, long, complex]:
            try:
                num_type(val)
                return True
            except:
                pass
        return False

    def dump_tables(self):
        dump = []
        fmt_cols = lambda cols: ','.join([("%s" % col) if ILP_Converter.numeric(col) else ("'%s'" % col) for col in cols])
        for table in self.db.tables:
            attributes = self.db.cols[table]
            dump.append('\n'.join(["%s(%s)." % (table, fmt_cols(cols)) for cols in self.db.rows(table, attributes)]))
        return dump

class RSD_Converter(ILP_Converter):
    '''
    Converts the database context to RSD inputs.
    '''
    def all_examples(self):
        target = self.db.target_table
        examples = self.db.rows(target, [self.db.target_att, self.db.pkeys[target]])
        return '\n'.join(["%s('%s', %s)." % (target, cls, pk) for cls, pk in examples])

    def background_knowledge(self):
        modeslist, getters = [self.mode(self.db.target_table, [('+', self.db.target_table)], head=True)], []
        for (table, ref_table) in self.db.connected.keys():
            if ref_table == self.db.target_table:
                continue # Skip backward connections
            modeslist.append(self.mode('has_%s' % ref_table, [('+', table), ('-', ref_table)]))
            getters.extend(self.connecting_clause(table, ref_table))
        for table, atts in self.db.cols.items():
            for att in atts:
                if att == self.db.target_att and table == self.db.target_table or \
                   att in self.db.fkeys[table] or att == self.db.pkeys[table]:
                    continue
                modeslist.append(self.mode('%s_%s' % (table, att), [('+', table), ('-', att)]))
                modeslist.append(self.mode('instantiate', [('+', att)]))
                getters.extend(self.attribute_clause(table, att))
        if not self.dump:
            b = '\n'.join(self.db_connection() + modeslist + getters + self.user_settings())
        else:
            b = '\n'.join(modeslist + getters + self.user_settings() + self.dump_tables())
        return b

class Aleph_Converter(ILP_Converter):
    '''
    Converts the database context to Aleph inputs.
    '''
    def __init__(self, *args, **kwargs):
        self.target_att_val = kwargs.pop('target_att_val')
        ILP_Converter.__init__(self, *args, **kwargs)
        self.__pos_examples, self.__neg_examples = None, None
        self.target_predicate = re.sub('\s+', '_', self.target_att_val).lower()

    def __examples(self):
        if not (self.__pos_examples and self.__neg_examples):
            target, att, target_val = self.db.target_table, self.db.target_att, self.target_att_val
            rows = self.db.rows(target, [att, self.db.pkeys[target]])
            pos_rows, neg_rows = [], []
            for row in rows:
                if row[0] == target_val:
                    pos_rows.append(row)
                else:
                    neg_rows.append(row)
            self.__pos_examples = '\n'.join(['%s(%s).' % (self.target_predicate, id) for _, id in pos_rows])
            self.__neg_examples = '\n'.join(['%s(%s).' % (self.target_predicate, id) for _, id in neg_rows])
        return self.__pos_examples, self.__neg_examples

    def positive_examples(self):
        return self.__examples()[0]

    def negative_examples(self):
        return self.__examples()[1]

    def background_knowledge(self):
        modeslist, getters = [self.mode(self.target_predicate, [('+', self.db.target_table)], head=True)], []
        determinations, types = [], []
        for (table, ref_table) in self.db.connected.keys():
            if ref_table == self.db.target_table:
                continue # Skip backward connections
            modeslist.append(self.mode('has_%s' % ref_table, [('+', table), ('-', ref_table)], recall='*'))
            determinations.append(':- determination(%s/1, has_%s/2).' % (self.target_predicate, ref_table))
            types.extend(self.concept_type_def(table))
            types.extend(self.concept_type_def(ref_table))
            getters.extend(self.connecting_clause(table, ref_table))
        for table, atts in self.db.cols.items():
            for att in atts:
                if att == self.db.target_att and table == self.db.target_table or \
                   att in self.db.fkeys[table] or att == self.db.pkeys[table]:
                    continue
                modeslist.append(self.mode('%s_%s' % (table, att), [('+', table), ('#', att)], recall='*'))
                determinations.append(':- determination(%s/1, %s_%s/2).' % (self.target_predicate, table, att))
                types.extend(self.constant_type_def(table, att))
                getters.extend(self.attribute_clause(table, att))
        local_copies = [self.local_copy(table) for table in self.db.tables]
        if not self.dump:
            b = '\n'.join(self.db_connection() + local_copies + self.user_settings() + modeslist + determinations + types + getters)
        else:
            b = '\n'.join(self.user_settings() + modeslist + determinations + types + getters + self.dump_tables())
        return b

    def concept_type_def(self, table):
        var_pk = self.db.pkeys[table].capitalize()
        variables = ','.join([var_pk if col.capitalize() == var_pk else '_' for col in self.db.cols[table]])
        return ['%s(%s) :-' % (table, var_pk), 
                '\t%s(%s).' % (table, variables)]

    def constant_type_def(self, table, att):
        var_att = att.capitalize()
        variables = ','.join([var_att if col == att else '_' for col in self.db.cols[table]])
        return ['%s(%s) :-' % (att, var_att), 
                '\t%s(%s).' % (table, variables)]

    def db_connection(self):
        con = self.db.connection
        host, db, user, pwd = con.host, con.database, con.user, con.password
        return [':- use_module(library(myddas)).', \
                ':- db_open(mysql, \'%s\'/\'%s\', \'%s\', \'%s\').' % (host, db, user, pwd)] + \
               [':- db_import(%s, tmp_%s).' % (table, table) for table in self.db.tables]

    def local_copy(self, table):
        cols = ','.join([col.capitalize() for col in self.db.cols[table]])
        return ':- repeat, tmp_%s(%s), (%s(%s), !, fail ; assertz(%s(%s)), fail).' % (table, cols, table, cols, table, cols)


class Orange_Converter(Converter):
    '''
    Converts the selected tables in the given context to orange example tables.
    '''
    continuous_types = ('FLOAT','DOUBLE','DECIMAL','NEWDECIMAL')
    integer_types = ('TINY','SHORT','LONG','LONGLONG','INT24')
    ordinal_types = ('YEAR','VARCHAR','SET','VAR_STRING','STRING','BIT')
    
    def __init__(self, *args, **kwargs):
        Converter.__init__(self, *args, **kwargs)
        self.types={}
        for table in self.db.tables:
            self.types[table]= self.db.fetch_types(table, self.db.cols[table])
        self.db.compute_col_vals()

    def target_Orange_table(self):
        table, cls_att = self.db.target_table, self.db.target_att
        return self.convert_table(table, cls_att)

    def other_Orange_tables(self):
        target_table = self.db.target_table

        return[ self.convert_table(table,None) for table in self.db.tables if table!=target_table]


    def convert_table(self, table_name, cls_att=None):
        '''
        Returns the target table as an orange example table.
        '''
        import orange

        cols = self.db.cols[table_name]
        attributes, metas, class_var = [], [], None
        for col in cols:
            att_type = self.orng_type(table_name,col)
            if att_type == 'd':
                att_vals = self.db.col_vals[table_name][col]
                att_var = orange.EnumVariable(str(col), values=[str(val) for val in att_vals])
            elif att_type == 'c':
                att_var = orange.FloatVariable(str(col))
            else:
                att_var = orange.StringVariable(str(col))
            if col == cls_att:
                if att_type == 'string':
                    raise Exception('Unsuitable data type for a target variable: %s' % att_type)
                class_var=att_var
                continue
            elif att_type == 'string' or table_name in self.db.pkeys and col in self.db.pkeys[table_name] or table_name in self.db.fkeys and col in self.db.fkeys[table_name]:
                metas.append(att_var)
            else:
                attributes.append(att_var)
        domain = orange.Domain(attributes, class_var)
        for meta in metas:
            domain.addmeta(orange.newmetaid(), meta)
        dataset = orange.ExampleTable(domain)
        dataset.name=table_name
        for row in self.db.rows(table_name, cols):
            example = orange.Example(domain)
            for col, val in zip(cols, row):
                example[str(col)] = str(val) if val!=None else '?'
            dataset.append(example)
        return dataset

    def orng_type(self, table_name, col):
        '''
        Assigns a given mysql column an orange type.
        '''
        mysql_type = self.types[table_name][col]
        n_vals = len(self.db.col_vals[table_name][col])
        if mysql_type in Orange_Converter.continuous_types or (n_vals >= 50 and mysql_type in Orange_Converter.integer_types):
            return 'c'
        elif mysql_type in Orange_Converter.ordinal_types+Orange_Converter.integer_types:
            return 'd'
        else:
            return 'string'

if __name__ == '__main__':
    from context import DBConnection, DBContext

    context = DBContext(DBConnection('root','','localhost','test'))
    context.target_table = 'trains'
    context.target_att = 'direction'
    intervals = {'cars': {'position' : [1, 3]}}
    import cPickle
    cPickle.dump(intervals, open('intervals.pkl','w'))
    rsd = RSD_Converter(context, discr_intervals=intervals, dump=True)
    aleph = Aleph_Converter(context, target_att_val='east', discr_intervals=intervals, dump=True)
    print rsd.background_knowledge()
    print aleph.background_knowledge()
    #orange = Orange_Converter(context)
    #orange.target_table()
