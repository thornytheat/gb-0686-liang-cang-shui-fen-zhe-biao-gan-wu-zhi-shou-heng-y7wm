from .rules import convert
from app.errors import DomainError
from app.reasons import rejected
def execute(ctx):
    good=[]
    for row in ctx['records']:
        try: good.append(convert(row,ctx['rules']))
        except DomainError as exc: ctx['quarantine'].append(rejected(row,exc.code,exc.message))
    ctx['records']=good
    ctx['stages'].append({'title':'干物质折算','rows':good,'metrics':{'折标 kg':str(sum((r['standard_kg'] for r in good),0)),'干物质 kg':str(sum((r['dry_kg'] for r in good),0)),'拒收':sum(q['code']=='LIMIT' for q in ctx['quarantine'])}})
    return ctx
