from app.normalize import number
from app.errors import DomainError
FACTORS={'kg':1,'t':1000}
def settings(params):
    out={k:number(params[k]) for k in ['standard_moisture','max_moisture','price','bin_tolerance']}
    if not 0<=out['standard_moisture']<out['max_moisture']<100 or out['price']<0 or out['bin_tolerance']<0:
        raise DomainError('RANGE','折标参数超出范围')
    return out
def coerce(row):
    out=dict(row)
    for key in ['gross','tare','moisture','impurity']: out[key]=number(row[key])
    if row['unit'] not in FACTORS: raise DomainError('UNIT','重量单位无效')
    if out['gross']<out['tare'] or out['tare']<0 or not 0<=out['moisture']<100 or not 0<=out['impurity']<100:
        raise DomainError('RANGE','水杂或毛皮重越界')
    version=number(row['version'])
    if version!=version.to_integral() or version<1: raise DomainError('RANGE','版本必须为正整数')
    out['version']=int(version);out['net_kg']=(out['gross']-out['tare'])*FACTORS[row['unit']]
    return out
