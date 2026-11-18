from app.normalize import rows_from
REQUIRED=['id','bin','gross','tare','unit','moisture','impurity','version']
def receive(raw):
    result=rows_from(raw,REQUIRED)
    for row in result['raw']:
        if not row['id'] or not row['bin']: row['_missing_key']=True
    return result
