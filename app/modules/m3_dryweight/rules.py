from decimal import Decimal as D
from app.errors import DomainError
def convert(row,rules):
    if row['moisture']>rules['max_moisture']: raise DomainError('LIMIT','水分超过收购上限')
    out=dict(row)
    out['clean_kg']=row['net_kg']*(1-row['impurity']/D(100))
    out['dry_kg']=out['clean_kg']*(1-row['moisture']/D(100))
    out['standard_kg']=out['dry_kg']/(1-rules['standard_moisture']/D(100))
    return out
