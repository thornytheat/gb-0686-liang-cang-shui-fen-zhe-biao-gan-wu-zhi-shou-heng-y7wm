from decimal import Decimal as D
from collections import defaultdict
def balances(rows,std):
    bins=defaultdict(list)
    for row in rows: bins[row['bin']].append(row)
    result=[]
    for name,group in sorted(bins.items()):
        net=sum((r['net_kg'] for r in group),D(0));dry=sum((r['dry_kg'] for r in group),D(0));standard=sum((r['standard_kg'] for r in group),D(0))
        delta=dry-standard*(1-std/D(100))
        result.append({'bin':name,'count':len(group),'net_kg':net,'dry_kg':dry,'standard_kg':standard,'delta_kg':delta})
    return result
