from .rules import merge
def execute(ctx):
    good,bad=merge(ctx['records']);ctx['records']=good;ctx['quarantine'].extend(bad)
    ctx['stages'].append({'title':'车次裁决','rows':good,'metrics':{'保留车次':len(good),'冲突':sum(q['code']=='CONFLICT' for q in bad),'去重':sum(q['code']=='DUPLICATE' for q in bad)}})
    return ctx
