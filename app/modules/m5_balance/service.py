from .rules import balances
from decimal import Decimal as D
def execute(ctx):
    rows=balances(ctx['records'],ctx['rules']['standard_moisture']);ctx['balances']=rows
    tolerance=ctx['rules']['bin_tolerance']
    for row in rows: row['state']='通过' if abs(row['delta_kg'])<=tolerance else '差异'
    ctx['stages'].append({'title':'仓批守恒','rows':rows,'metrics':{'仓批':len(rows),'干物质 kg':str(sum((r['dry_kg'] for r in rows),D(0))),'差异仓':sum(r['state']!='通过' for r in rows)}})
    return ctx
