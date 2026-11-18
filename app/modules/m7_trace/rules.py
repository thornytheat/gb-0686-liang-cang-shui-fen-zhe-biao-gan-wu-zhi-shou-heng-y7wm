from collections import Counter
import hashlib,json
from app.normalize import serial
from app.errors import DomainError
def audit(rows,quarantine,input_count):
    if len(rows)+len(quarantine)!=input_count: raise DomainError('INCOMPLETE','行数平衡失败')
    if len({r['id'] for r in rows})!=len(rows): raise DomainError('CONFLICT','重复磅单未裁决')
    fingerprint=hashlib.sha256(json.dumps(serial(rows),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {'count':len(rows),'quarantined':len(quarantine),'input_count':input_count,'fingerprint':fingerprint,'causes':dict(Counter(r['code'] for r in quarantine))}
