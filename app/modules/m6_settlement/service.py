from .rules import settle
def execute(ctx):
    rows,total=settle(ctx['records'],ctx['rules']['price']);ctx['records']=rows;ctx['total_amount']=total
    ctx['stages'].append({'title':'结算复核','rows':rows,'metrics':{'结算 CNY':str(total),'单价 CNY/kg':str(ctx['rules']['price']),'分录':len(rows)}})
    return ctx
