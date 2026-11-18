from app.modules.m4_truckmerge.rules import merge
from app.pipeline import run
def sample(line=2,version=1,net=100): return dict(id='001',bin='甲',net_kg=net,moisture=14,impurity=0,version=version,_line=line)
def test_conflict_keeps_neither():
    # TRAP-14
    good,bad=merge([sample(),sample(3,net=101)]);assert good==[] and len(bad)==2
    assert all(q['code']=='CONFLICT' for q in bad)
def test_exact_duplicate_dedup():
    good,bad=merge([sample(),sample(3)]);assert len(good)==len(bad)==1 and good[0]['_line']==2
def test_latest_revision_wins():
    good,bad=merge([sample(),sample(3,2,101)]);assert good[0]['net_kg']==101 and len(bad)==1
def test_order_independent():
    x=[sample(),sample(3,2,101)];assert merge(x)==merge(list(reversed(x)))
def test_real_conflicts(raw): assert sum(q['code']=='CONFLICT' for q in run(raw,stop=4,persist=False)['quarantine'])==2
def test_real_duplicates(raw): assert sum(q['code']=='DUPLICATE' for q in run(raw,stop=4,persist=False)['quarantine'])==1
def test_real_four_ledger(raw):
    x=run(raw,stop=4,persist=False);assert len(x['records'])+len(x['quarantine'])==47
