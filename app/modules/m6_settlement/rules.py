from decimal import Decimal as D,ROUND_HALF_UP,ROUND_FLOOR
def settle(rows,price):
    raw=[r['standard_kg']*price for r in rows];target=sum(raw,D(0)).quantize(D('.01'),rounding=ROUND_HALF_UP)
    floor=[v.quantize(D('.01'),rounding=ROUND_FLOOR) for v in raw]
    pennies=int((target-sum(floor,D(0)))/D('.01'))
    order=sorted(range(len(rows)),key=lambda i:(-(raw[i]-floor[i]),rows[i]['id']))
    for i in order[:pennies]: floor[i]+=D('.01')
    result=[{**r,'amount':floor[i],'unrounded':raw[i]} for i,r in enumerate(rows)]
    return result,target
