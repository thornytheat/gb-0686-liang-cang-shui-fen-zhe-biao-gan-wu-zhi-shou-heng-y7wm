import pytest
from decimal import Decimal as D
from app.errors import DomainError
from app.pipeline import run
from app.modules.m2_contract.rules import coerce,settings
from app.config import DEFAULTS
def row(**kw): return dict(id='001',bin='甲仓',gross='1,200',tare='200',unit='kg',moisture='18',impurity='2',version='1',**kw)
def test_thousands_fullwidth():
    # TRAP-06
    x=row();x['gross']='１，２００';assert coerce(x)['net_kg']==D('1000')
def test_unit_ton():
    # TRAP-15
    x=row();x.update(gross='1.2',tare='.2',unit='t');assert coerce(x)['net_kg']==1000
def test_sentinel_not_zero():
    # TRAP-07
    x=row();x['moisture']='N/A'
    with pytest.raises(DomainError): coerce(x)
def test_params_boundary():
    with pytest.raises(DomainError): settings({**DEFAULTS,'standard_moisture':'100'})
def test_real_missing_isolated(raw):
    x=run(raw,stop=2,persist=False);assert any(q['code']=='MISSING' for q in x['quarantine'])
def test_real_unit_normalized(raw):
    x=run(raw,stop=2,persist=False);assert x['records'][0]['net_kg']=='1000'
def test_real_range_isolated(raw):
    x=run(raw,stop=2,persist=False);assert any(q['code']=='RANGE' for q in x['quarantine'])
