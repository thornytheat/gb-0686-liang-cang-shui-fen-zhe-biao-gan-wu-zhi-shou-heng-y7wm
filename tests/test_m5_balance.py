from decimal import Decimal as D
from app.modules.m5_balance.rules import balances
from app.pipeline import run
def row(name='甲',net='100',dry='86',std='100'): return dict(bin=name,net_kg=D(net),dry_kg=D(dry),standard_kg=D(std))
def test_exact_decimal_sum():
    # TRAP-10
    x=balances([row(net='.1',dry='.086',std='.1') for _ in range(1000)],D(14));assert x[0]['net_kg']==D('100.0')
def test_detect_dry_drift(): assert balances([row(dry='85')],D(14))[0]['delta_kg']==-1
def test_empty_groups(): assert balances([],D(14))==[]
def test_bins_separate(): assert len(balances([row('甲'),row('乙')],D(14)))==2
def test_real_balance_passes(raw): assert all(r['state']=='通过' for r in run(raw,stop=5,persist=False)['balances'])
def test_real_bin_count(raw): assert len(run(raw,stop=5,persist=False)['balances'])==3
def test_real_total_preserved(raw):
    x=run(raw,stop=5,persist=False);assert sum(D(r['net_kg']) for r in x['balances'])==sum(D(r['net_kg']) for r in x['records'])
