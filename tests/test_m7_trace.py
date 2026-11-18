import pytest
from app.errors import DomainError
from app.pipeline import run
from app.modules.m7_trace.rules import audit
def test_audit_mismatch_rejected():
    with pytest.raises(DomainError): audit([],[],1)
def test_audit_duplicate_rejected():
    with pytest.raises(DomainError): audit([{'id':'1'},{'id':'1'}],[],2)
def test_stable_fingerprint(): assert audit([{'id':'1'}],[],1)['fingerprint']==audit([{'id':'1'}],[],1)['fingerprint']
def test_changed_fingerprint(): assert audit([{'id':'1'}],[],1)['fingerprint']!=audit([{'id':'2'}],[],1)['fingerprint']
def test_real_causes_count(raw):
    x=run(raw,persist=False);assert sum(x['audit']['causes'].values())==len(x['quarantine'])
def test_real_hash_stable(raw): assert run(raw,persist=False)['audit']==run(raw,persist=False)['audit']
def test_real_manifest_hash(raw,isolate):
    import hashlib
    x=run(raw);assert x['manifest']['sha256']==hashlib.sha256(raw).hexdigest()
