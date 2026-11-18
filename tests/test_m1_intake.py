import pytest
from app.config import SAMPLES
from app.errors import DomainError
from app.modules.m1_intake.rules import receive
from app.pipeline import run
def test_bom_header(raw):
    # TRAP-02
    assert receive(raw)['raw'][0]['id']=='00001'
def test_real_sample_count(raw): assert receive(raw)['input_count']==47
def test_real_bad_width(raw):
    x=receive(raw);assert [q['code'] for q in x['quarantine']]==['COLUMN_COUNT']
def test_gb18030_sample():
    x=receive((SAMPLES/'legacy.csv').read_bytes());assert x['encoding']=='gb18030'
def test_empty_rejected():
    with pytest.raises(DomainError,match='没有数据'): receive(b'')
def test_header_only():
    with pytest.raises(DomainError,match='只有字段名'): receive(b'id,bin,gross,tare,unit,moisture,impurity,version\n')
def test_real_stage_preserves_zero_id(raw):
    # TRAP-08
    assert run(raw,stop=1,persist=False)['records'][0]['id']=='00001'
