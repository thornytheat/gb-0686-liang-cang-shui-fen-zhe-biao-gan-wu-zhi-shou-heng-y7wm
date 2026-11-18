from .rules import receive
from app.reasons import rejected
def execute(ctx):
    parsed=receive(ctx['source']);ctx.update(parsed);ctx['records']=[]
    for row in ctx['raw']:
        if row.get('_missing_key'): ctx['quarantine'].append(rejected(row,'MISSING','磅单号或仓号为空'))
        else: ctx['records'].append(row)
    ctx['stages'].append({'title':'磅单采信','rows':ctx['records'],'metrics':{'逻辑行':ctx['input_count'],'采信':len(ctx['records']),'隔离':len(ctx['quarantine'])}})
    return ctx
