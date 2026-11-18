from decimal import Decimal as D
from app.modules.m6_settlement.rules import settle
from app.pipeline import run
def test_largest_remainder_conservation():
    # TRAP-24
    rows,total=settle([{'id':str(i),'standard_kg':D('.005')} for i in range(3)],D(1))
    assert total==D('.02') and sum(r['amount'] for r in rows)==total
    assert [r['amount'] for r in rows]==[D('.01'),D('.01'),D('0')]
def test_tie_stable_by_key():
    rows,total=settle([{'id':'b','standard_kg':D('.005')},{'id':'a','standard_kg':D('.005')}],D(1))
    assert rows[1]['amount']==D('.01') and rows[0]['amount']==0
def test_zero_price(): assert settle([{'id':'1','standard_kg':D(1)}],D(0))[1]==0
def test_empty_total(): assert settle([],D(1))==([],D('0.00'))
def test_real_amount_conservation(raw):
    x=run(raw,stop=6,persist=False);assert sum(D(r['amount']) for r in x['records'])==D(x['total_amount'])
def test_real_currency_scale(raw): assert all(D(r['amount']).as_tuple().exponent==-2 for r in run(raw,stop=6,persist=False)['records'])
def test_real_positive_total(raw): assert D(run(raw,stop=6,persist=False)['total_amount'])>0
