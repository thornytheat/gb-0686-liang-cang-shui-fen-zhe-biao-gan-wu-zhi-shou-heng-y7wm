import csv, hashlib, io, json
from decimal import Decimal as D
from app.config import DEFAULTS
from app.errors import DomainError
from app.normalize import rows_from, number
from app.reasons import rejected
from app.modules.m2_contract.rules import settings
from app.modules.m3_dryweight.rules import convert
from . import store
from .rules import REQUIRED, parse_event, pair, estimate, chain_append, fen
PARAM_KEYS = ['standard_moisture', 'max_moisture', 'price', 'bin_tolerance', 'default_tare_kg']
def effective_params(given):
    if not isinstance(given, (dict, type(None))): raise DomainError("PARAMS", "参数必须是对象")
    merged = {**DEFAULTS, 'default_tare_kg': '', **(given or {})}
    rules = settings(merged)
    default = number(merged['default_tare_kg'], nullable=True)
    if default is not None and default < 0: raise DomainError("RANGE", "默认皮重不能为负")
    rules['default_tare_kg'] = default
    view = {k: str(rules[k]) for k in PARAM_KEYS[:-1]}
    view['default_tare_kg'] = '' if default is None else str(default)
    return rules, view
def _canon(value):
    return None if value in ('', None) else D(str(value))
def same_params(locked, view):
    return all(_canon(locked.get(k)) == _canon(view.get(k)) for k in PARAM_KEYS)
def rules_from(locked):
    rules = {k: D(locked[k]) for k in PARAM_KEYS[:-1]}
    rules['default_tare_kg'] = _canon(locked.get('default_tare_kg'))
    return rules
def _decimals(trip):
    out = dict(trip)
    for key in ['gross_kg', 'tare_kg', 'moisture', 'impurity', 'estimate_kg', 'net_kg',
                'clean_kg', 'dry_kg', 'standard_kg', 'amount', 'cum_exact', 'cum_after']:
        out[key] = None if trip[key] is None else D(trip[key])
    out['audit'] = json.loads(trip['audit'])
    return out
def _new_trip(event):
    return {'trip_id': event['event_id'], 'plate': event['plate'], 'bin': event['bin'], 'day': event['day'],
            'gross_event_id': event['event_id'], 'gross_at': event['weighed_at'], 'gross_local': event['weighed_local'],
            'gross_kg': event['weight_kg'], 'moisture': event['moisture'], 'impurity': event['impurity'],
            'tare_state': '待皮重',
            'audit': [{'at': store.now(), 'action': 'gross',
                       'detail': f"毛重入账 {event['weight_kg']} kg（{event['weighed_local']}）"}]}
def _convert(net, trip, rules):
    return convert({'net_kg': net, 'moisture': trip['moisture'], 'impurity': trip['impurity']}, rules)
def _confirm(conn, trip_id, tare, rules):
    trip = _decimals(store.get_trip(conn, trip_id))
    tare = {**tare, 'weight_kg': D(tare['weight_kg'])}
    conv = _convert(trip['gross_kg'] - tare['weight_kg'], trip, rules)
    exact = conv['standard_kg'] * rules['price']
    tail = store.chain_tail(conn, trip['bin'], trip['day'])
    amount, cum_exact, cum_after = chain_append(tail['cum_exact'], tail['cum_after'], exact)
    audit = trip['audit'] + [{'at': store.now(), 'action': 'bind',
                              'detail': f"皮重 {tare['event_id']} 入账，净重 {conv['net_kg']} kg，金额冻结 {amount}"}]
    store.bind_tare(conn, trip_id, tare, conv, amount, cum_exact, cum_after, tail['seq'] + 1, audit)
def _pair_plate(conn, plate, rules):
    trips = store.open_trips(conn, plate)
    tares = store.loose_tares(conn, plate)
    if not trips or not tares: return
    open_view = [{'trip_id': t['trip_id'], 'gross_at': t['gross_at'], 'gross_kg': D(t['gross_kg'])} for t in trips]
    loose_view = [{'event_id': e['event_id'], 'weighed_at': e['weighed_at'], 'weight_kg': D(e['weight_kg'])} for e in tares]
    bindings, _ = pair(open_view, loose_view)
    by_id = {e['event_id']: e for e in tares}
    for tare_id, trip_id in bindings: _confirm(conn, trip_id, by_id[tare_id], rules)
def _refresh_estimates(conn, plate, rules):
    opens = store.open_trips(conn, plate)
    if not opens: return
    confirmed = store.confirmed_tares(conn, plate)
    for row in opens:
        trip = _decimals(row)
        found = estimate(trip['gross_at'], confirmed, rules['default_tare_kg'])
        conv = source = kg = None
        state = '待皮重'
        if found is not None:
            source, kg = found
            net = trip['gross_kg'] - kg
            if net > 0:
                conv = _convert(net, trip, rules); state = '暂估'
            else: source = kg = None
        if trip['tare_state'] == state and trip['estimate_source'] == source and trip['estimate_kg'] == kg:
            continue
        audit = trip['audit'] + [{'at': store.now(), 'action': 'estimate',
                                  'detail': '暂估皮重 ' + (f"{kg} kg（来源 {source}）" if source else '不可用，等待皮重')}]
        store.set_estimate(conn, trip['trip_id'], state, source, kg, conv, audit)
def upload(raw, given):
    if isinstance(raw, str): raw = raw.encode('utf-8')
    rules, view = effective_params(given)
    upload_id = hashlib.sha256(raw + json.dumps(view, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    with store.db() as conn:
        locked = store.lock_params(conn, view)
        if not same_params(locked, view):
            raise DomainError("PARAMS_LOCKED", "折标参数已锁定，与首次上传不一致", 409)
        prior = store.find_upload(conn, upload_id)
        if prior is not None: return prior
        parsed = rows_from(raw, REQUIRED)
        quarantine = list(parsed['quarantine'])
        accepted = []
        for row in parsed['raw']:
            try: event = parse_event(row, rules)
            except DomainError as exc:
                quarantine.append(rejected(row, exc.code, exc.message)); continue
            existing = store.get_event(conn, event['event_id'])
            if existing is not None:
                same = existing['hash'] == event['hash']
                quarantine.append(rejected(row, 'DUPLICATE' if same else 'CONFLICT',
                                           '相同称重已入账' if same else '同号称重内容不一致，采信首次入账'))
                continue
            store.insert_event(conn, event, upload_id)
            accepted.append(event)
            if event['kind'] == 'gross': store.insert_trip(conn, _new_trip(event))
        for plate in sorted({e['plate'] for e in accepted}):
            _pair_plate(conn, plate, rules)
            _refresh_estimates(conn, plate, rules)
        summary = {'upload_id': upload_id, 'created': store.now(), 'rows': parsed['input_count'],
                   'blank': parsed['blank_count'], 'accepted': len(accepted),
                   'gross': sum(e['kind'] == 'gross' for e in accepted),
                   'tare': sum(e['kind'] == 'tare' for e in accepted),
                   'quarantined': len(quarantine), 'replay': False}
        store.record_upload(conn, upload_id, summary, quarantine, view)
        return summary
def snapshot():
    with store.db() as conn:
        locked = store.locked_params(conn)
        trips = [_decimals(row) for row in store.all_trips(conn)]
        loose = store.loose_tares(conn)
        ups = store.uploads(conn)
        events = store.event_count(conn)
        rules = rules_from(locked) if locked else None
        for trip in trips:
            trip['state'] = '实称' if trip['tare_event_id'] else ('暂估' if trip['estimate_source'] else '待皮重')
            trip['estimated_amount'] = (fen(trip['standard_kg'] * rules['price'])
                                        if rules and not trip['tare_event_id'] and trip['standard_kg'] is not None else None)
        chains = {}
        for trip in trips:
            key = (trip['bin'], trip['day'])
            chain = chains.setdefault(key, {'bin': key[0], 'day': key[1], 'trips': 0, 'confirmed': 0, 'pending': 0,
                                            'net_kg': D(0), 'dry_kg': D(0), 'standard_kg': D(0),
                                            'confirmed_amount': D(0), 'estimated_amount': D(0)})
            chain['trips'] += 1
            if trip['tare_event_id']:
                chain['confirmed'] += 1; chain['confirmed_amount'] += trip['amount']
            else:
                chain['pending'] += 1
                if trip['estimated_amount'] is not None: chain['estimated_amount'] += trip['estimated_amount']
            if trip['net_kg'] is not None:
                chain['net_kg'] += trip['net_kg']; chain['dry_kg'] += trip['dry_kg']; chain['standard_kg'] += trip['standard_kg']
        for key, chain in chains.items():
            tail = store.chain_tail(conn, *key)
            if tail['cum_after'] != chain['confirmed_amount']:
                raise DomainError("INCOMPLETE", "仓批分录不守恒", 500)
            chain['amount'] = chain['confirmed_amount'] + chain['estimated_amount']
    open_by_plate = {}
    for trip in trips:
        if not trip['tare_event_id']: open_by_plate.setdefault(trip['plate'], []).append(trip)
    for event in loose:
        event['weight_kg'] = D(event['weight_kg'])
        candidates = [t for t in open_by_plate.get(event['plate'], []) if t['gross_at'] < event['weighed_at']]
        event['note'] = '皮重不小于最近毛重' if candidates else '无在先毛重可配对'
    chain_list = [chains[key] for key in sorted(chains)]
    confirmed_amount = sum((c['confirmed_amount'] for c in chain_list), D(0))
    estimated_amount = sum((c['estimated_amount'] for c in chain_list), D(0))
    bound = sum(1 for t in trips if t['tare_event_id'])
    checks = [
        {'item': '称重事件 = 车次 + 已配皮重 + 待配皮重', 'left': events, 'right': len(trips) + bound + len(loose)},
        {'item': '上传行数 = 采信 + 隔离', 'left': sum(u['rows'] for u in ups),
         'right': sum(u['accepted'] for u in ups) + sum(len(u['quarantine']) for u in ups)},
        {'item': '仓批净重 = 车次净重合计', 'left': sum((c['net_kg'] for c in chain_list), D(0)),
         'right': sum((t['net_kg'] for t in trips if t['net_kg'] is not None), D(0))},
        {'item': '仓批应付 = 已定金额 + 暂估金额', 'left': confirmed_amount + estimated_amount,
         'right': sum((t['amount'] for t in trips if t['amount'] is not None), D(0))
                + sum((t['estimated_amount'] for t in trips if t['estimated_amount'] is not None), D(0))},
    ]
    for check in checks: check['ok'] = check['left'] == check['right']
    quarantine = [{'upload': u['upload_id'][:8], **q} for u in ups for q in u['quarantine']]
    upload_views = [{'upload_id': u['upload_id'], 'created': u['created'], 'rows': u['rows'],
                     'accepted': u['accepted'], 'quarantined': len(u['quarantine'])} for u in ups]
    return {'locked': locked is not None, 'params': locked, 'trips': trips, 'chains': chain_list,
            'pending_trips': [t for t in trips if not t['tare_event_id']], 'loose_tares': loose,
            'uploads': upload_views, 'quarantine': quarantine,
            'reconcile': {'checks': checks, 'balanced': all(c['ok'] for c in checks)},
            'totals': {'trips': len(trips), 'confirmed': bound, 'pending': len(trips) - bound,
                       'net_kg': sum((t['net_kg'] for t in trips if t['net_kg'] is not None), D(0)),
                       'dry_kg': sum((t['dry_kg'] for t in trips if t['dry_kg'] is not None), D(0)),
                       'standard_kg': sum((t['standard_kg'] for t in trips if t['standard_kg'] is not None), D(0)),
                       'confirmed_amount': confirmed_amount, 'estimated_amount': estimated_amount,
                       'amount': confirmed_amount + estimated_amount},
            'generated': store.now()}
def export_csv():
    with store.db() as conn:
        rows = [row for row in store.all_trips(conn) if row['tare_event_id']]
    rows.sort(key=lambda r: (r['bin'], r['day'], r['gross_at'], r['trip_id']))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(['id', 'bin', 'gross', 'tare', 'unit', 'moisture', 'impurity', 'version'])
    for row in rows:
        writer.writerow([row['trip_id'], row['bin'], row['gross_kg'], row['tare_kg'], 'kg',
                         row['moisture'], row['impurity'], 1])
    return stream.getvalue()
