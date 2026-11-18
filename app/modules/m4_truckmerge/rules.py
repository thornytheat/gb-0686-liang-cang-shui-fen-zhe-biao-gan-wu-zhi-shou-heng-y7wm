from collections import defaultdict
from app.reasons import rejected
def merge(rows):
    groups=defaultdict(list)
    for row in rows: groups[row['id']].append(row)
    good=[];bad=[]
    for key,group in sorted(groups.items()):
        highest=max(r['version'] for r in group);latest=[r for r in group if r['version']==highest]
        signature=lambda r: tuple(str(r[k]) for k in ['bin','net_kg','moisture','impurity'])
        if len({signature(r) for r in latest})>1:
            bad.extend(rejected(r,'CONFLICT','同版磅单矛盾') for r in group);continue
        winner=min(latest,key=lambda r:r['_line']);good.append(winner)
        for row in group:
            if row is not winner: bad.append(rejected(row,'DUPLICATE','旧版替换' if row['version']<highest else '重复磅单'))
    return good,bad
