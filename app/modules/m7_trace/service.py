from .rules import audit
def execute(ctx):
    ctx['audit']=audit(ctx['records'],ctx['quarantine'],ctx['input_count'])
    rows=[{'code':code,'count':count} for code,count in sorted(ctx['audit']['causes'].items())]
    ctx['stages'].append({'title':'批次追溯','rows':rows,'metrics':{'输入':ctx['input_count'],'采信':len(ctx['records']),'隔离':len(ctx['quarantine'])}})
    return ctx
