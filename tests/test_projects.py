"""Business-rule and algorithm tests, using fresh temporary databases."""
import csv
import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from projects.smartfind import SmartFind
from projects.attendance import Attendance
from projects.peso import Peso
from projects.accesspath import AccessPath
from projects.minilang import run
from shared.core import APIError, csv_text, money
import sqlite3


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.inventory = SmartFind(root/'stock.db')
        self.attendance = Attendance(root/'attendance.db')
        self.peso = Peso(root/'peso.db')
        self.routes = AccessPath(root/'routes.db')

    def tearDown(self):
        self.temp.cleanup()

    def call(self, app, method, path, data=None, query=None):
        return app.handle(method, path, data or {}, query or {})

    def test_money_exactness_and_invalid_values(self):
        self.assertEqual(money('0.29'), 29)
        self.assertEqual(money('1.10'), 110)
        for invalid in ['NaN', 'Infinity', '-1', '1.001', None, '1000001']:
            with self.subTest(invalid=invalid), self.assertRaises(APIError):
                money(invalid)

    def test_export_neutralizes_spreadsheet_formulas(self):
        value = csv_text(['note'], [[' =HYPERLINK("x")']])
        self.assertTrue(list(csv.reader(io.StringIO(value)))[1][0].startswith("'"))

    def test_stock_change_has_audit_record(self):
        result = self.call(self.inventory, 'POST', '/adjust', {'product_id':1,'delta':-3,'reason':'Demo sale'})
        self.assertEqual(result['stock'], 45)
        ledger = self.call(self.inventory, 'GET', '/movements')
        self.assertEqual((ledger[0]['delta'],ledger[0]['reason']), (-3,'Demo sale'))

    def test_failed_stock_change_rolls_back_everything(self):
        before = self.call(self.inventory, 'GET', '/movements')
        with self.assertRaises(APIError):
            self.call(self.inventory, 'POST', '/adjust', {'product_id':1,'delta':-49,'reason':'Too much'})
        self.assertEqual(self.call(self.inventory,'GET','/movements'), before)
        with self.inventory.db.connect() as conn:
            self.assertEqual(conn.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],48)

    def test_concurrent_changes_do_not_oversell(self):
        def consume(_):
            try:
                self.call(self.inventory,'POST','/adjust',{'product_id':1,'delta':-30,'reason':'Concurrent sale'})
                return True
            except APIError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(consume,range(2)))
        self.assertEqual(sum(outcomes), 1)
        with self.inventory.db.connect() as conn:
            self.assertEqual(conn.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],18)

    def test_seed_is_not_reinserted_on_restart(self):
        self.call(self.inventory,'POST','/adjust',{'product_id':1,'delta':-1,'reason':'Persisted'})
        restarted = SmartFind(self.inventory.db.path)
        self.assertEqual(len(self.call(restarted,'GET','/products')),4)
        with restarted.db.connect() as conn:
            self.assertEqual(conn.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],47)

    def test_duplicate_sku_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.call(self.inventory,'POST','/products',{'name':'Duplicate','sku':'PEN-01','category':'Test','price':'1','stock':0,'reorder_level':1})

    def test_sql_injection_is_stored_as_plain_text(self):
        name = "Test'); DROP TABLE products; --"
        self.call(self.inventory,'POST','/products',{'name':name,'sku':'SAFE-1','category':'Test','price':'1','stock':0,'reorder_level':0})
        self.assertEqual(len(self.call(self.inventory,'GET','/products')),5)

    def test_attendance_lifecycle_and_absent_report(self):
        data = {'student_id':1,'event_id':1}
        with self.assertRaises(APIError):
            self.call(self.attendance,'POST','/check-out',data)
        self.call(self.attendance,'POST','/check-in',data)
        with self.assertRaises(sqlite3.IntegrityError):
            self.call(self.attendance,'POST','/check-in',data)
        self.call(self.attendance,'POST','/check-out',data)
        with self.assertRaises(APIError):
            self.call(self.attendance,'POST','/check-out',data)
        report = self.call(self.attendance,'GET','/records')
        self.assertEqual(sorted(r['status'] for r in report),['Absent','Absent','Completed'])
        completed = next(r for r in report if r['status']=='Completed')
        self.assertLessEqual(completed['time_in'],completed['time_out'])

    def test_attendance_is_unique_per_event(self):
        new = self.call(self.attendance,'POST','/events',{'name':'Second','event_date':'2026-10-01'})
        for event in [1,new['id']]:
            self.call(self.attendance,'POST','/check-in',{'student_id':1,'event_id':event})
        self.assertEqual(sum(r['status']=='Present' for r in self.call(self.attendance,'GET','/records',query={'event_id':[str(new['id'])]})),1)

    def test_unknown_student_and_invalid_date(self):
        with self.assertRaises(APIError):
            self.call(self.attendance,'POST','/check-in',{'student_id':999,'event_id':1})
        with self.assertRaises(APIError):
            self.call(self.attendance,'POST','/events',{'name':'Invalid','event_date':'2026-02-30'})

    def test_expense_summary_is_scoped_to_month(self):
        data = {'kind':'expense','category':'Test','amount':'0.29','date':'2020-01-01','note':'Exact'}
        self.call(self.peso,'POST','/transactions',data)
        summary = self.call(self.peso,'GET','/summary',query={'month':['2020-01']})
        self.assertEqual((summary['income'],summary['expense'],summary['balance']), (0,29,-29))
        self.assertEqual(summary['categories'],[{'category':'Test','total':29}])

    def test_csv_import_is_atomic(self):
        month = date.today().strftime('%Y-%m')
        before = self.call(self.peso,'GET','/transactions',query={'month':[month]})
        source = f'kind,category,amount,date,note\nexpense,Food,10,{month}-01,Valid\nexpense,Food,-5,{month}-01,Invalid\n'
        with self.assertRaises(APIError):
            self.call(self.peso,'POST','/import',{'csv':source})
        self.assertEqual(self.call(self.peso,'GET','/transactions',query={'month':[month]}), before)

    def test_csv_import_quotes_and_export(self):
        source = 'kind,category,amount,date,note\nexpense,Food,12.25,2020-02-01,"Lunch, snack"\n'
        self.assertEqual(self.call(self.peso,'POST','/import',{'csv':source})['imported'],1)
        exported,_ = self.call(self.peso,'GET','/export',query={'month':['2020-02']})
        record = list(csv.DictReader(io.StringIO(exported)))[0]
        self.assertEqual((record['note'],record['amount']),('Lunch, snack','12.25'))

    def test_bad_month_and_missing_transaction(self):
        with self.assertRaises(APIError):
            self.call(self.peso,'GET','/summary',query={'month':['2026-99']})
        with self.assertRaises(APIError):
            self.call(self.peso,'DELETE','/transactions/999')

    def test_step_free_route_avoids_shorter_stairs(self):
        base = {'start':'gate','end':'lab','max_slope':8,'min_width':90}
        accessible = self.call(self.routes,'POST','/plan',{**base,'step_free':True})
        unrestricted = self.call(self.routes,'POST','/plan',{**base,'step_free':False})
        self.assertEqual(accessible['distance'],220)
        self.assertEqual(accessible['nodes'],['gate','ramp','hall','lab'])
        self.assertEqual(unrestricted['distance'],170)

    def test_closed_route_reroutes_then_becomes_unreachable(self):
        self.call(self.routes,'PATCH','/edges/6',{'blocked':True})
        result = self.call(self.routes,'POST','/plan',{'start':'gate','end':'lab'})
        self.assertFalse(result['found'])
        self.call(self.routes,'PATCH','/edges/6',{'blocked':False})
        self.assertTrue(self.call(self.routes,'POST','/plan',{'start':'gate','end':'lab'})['found'])

    def test_same_node_route_has_zero_distance(self):
        result=self.call(self.routes,'POST','/plan',{'start':'gate','end':'gate'})
        self.assertEqual((result['nodes'],result['distance']),(['gate'],0))

    def test_route_invalid_preferences(self):
        for data in [{'start':'unknown','end':'lab'}, {'start':'gate','end':'lab','max_slope':float('nan')}, {'start':[],'end':'lab'}]:
            with self.subTest(data=data), self.assertRaises(APIError):
                self.call(self.routes,'POST','/plan',data)

    def test_language_precedence_unary_and_associativity(self):
        result=run('print 2 + 3 * 4; print (2 + 3) * 4; print 8 / 2 / 2; print -2 * 3;')
        self.assertEqual(result['output'],['14','20','2','-6'])
        self.assertEqual(result['ast']['type'],'Program')

    def test_language_repeat_variables_and_comments(self):
        result=run('# hello\nlet x = 0; repeat 3 { let x = x + 2; print x; }')
        self.assertEqual(result['output'],['2','4','6'])
        self.assertEqual(result['variables'],{'x':6})
        self.assertEqual(result['tokens'][0]['line'],2)

    def test_language_errors_have_useful_messages(self):
        cases={'print x;':'Undefined variable', 'print 1/0;':'Division by zero', 'let x = 1':'Expected ;', 'print @;':'line 1, column 7', 'repeat 101 { print 1; }':'Repeat count', 'print 10000000000000;':'supported range'}
        for source,message in cases.items():
            with self.subTest(source=source), self.assertRaisesRegex(APIError,message):
                run(source)

    def test_language_execution_and_depth_bounds(self):
        with self.assertRaises(APIError):
            run('repeat 100 { repeat 100 { let x = 1; } }')
        with self.assertRaises(APIError):
            run('print ' + '('*50+'1'+')'*50+';')
        with self.assertRaises(APIError):
            run('repeat 100 { repeat 100 { print 1; } }')

    def test_language_does_not_execute_python(self):
        with self.assertRaises(APIError):
            run("import os;")


if __name__ == '__main__':
    unittest.main()
