from decimal import Decimal as D
import pytest
from app.errors import DomainError
from app.pipeline import run
from app.modules.m3_dryweight.rules import convert
RULES={'standard_moisture':D('14'),'max_moisture':D('28')}
def test_dry_matter_counterexample():
    x=convert({'net_kg':D(1000),'moisture':D(18),'impurity':D(2)},RULES)
    assert x['dry_kg']==D('803.6')
    assert x['standard_kg']!=D(1000)*(1-D('.18')+D('.14'))
def test_standard_moisture_unchanged():
    assert convert({'net_kg':D(1000),'moisture':D(14),'impurity':D(0)},RULES)['standard_kg']==1000
def test_above_limit_rejected():
    with pytest.raises(DomainError): convert({'net_kg':D(100),'moisture':D(29),'impurity':D(0)},RULES)
def test_zero_net_valid(): assert convert({'net_kg':D(0),'moisture':D(18),'impurity':D(0)},RULES)['dry_kg']==0
def test_real_rejection(raw): assert any(q['code']=='LIMIT' for q in run(raw,stop=3,persist=False)['quarantine'])
def test_real_conservation(raw):
    x=run(raw,stop=3,persist=False);assert x['input_count']==len(x['records'])+len(x['quarantine'])
def test_real_formula(raw):
    x=run(raw,stop=3,persist=False)['records'][0]
    assert D(x['dry_kg'])==D(x['standard_kg'])*D('.86')
