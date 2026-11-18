import hashlib, json, unicodedata
from datetime import datetime, timezone
from decimal import Decimal as D, ROUND_HALF_UP
from app.errors import DomainError
from app.normalize import number
from app.modules.m2_contract.rules import FACTORS
REQUIRED = ['event_id', 'plate', 'kind', 'weight', 'unit', 'weighed_at', 'bin', 'moisture', 'impurity']
KINDS = {'gross': 'gross', '毛重': 'gross', '毛': 'gross', 'tare': 'tare', '皮重': 'tare', '皮': 'tare'}
CENT = D('.01')
def fen(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)
def moment(value):
    text = unicodedata.normalize("NFKC", str(value)).strip().replace("Z", "+00:00")
    try: parsed = datetime.fromisoformat(text)
    except (ValueError, TypeError): raise DomainError("TIME", "时间格式错误")
    if parsed.tzinfo is None: raise DomainError("TIME", "时间必须包含偏移")
    return parsed.astimezone(timezone.utc).isoformat(), parsed.isoformat(), parsed.date().isoformat()
def fingerprint(event):
    keys = ['event_id', 'plate', 'kind', 'weight_kg', 'weighed_at', 'bin', 'moisture', 'impurity']
    return hashlib.sha256(json.dumps([str(event[k]) for k in keys], ensure_ascii=False).encode()).hexdigest()
def parse_event(row, rules):
    event_id = str(row['event_id']).strip()
    plate = str(row['plate']).strip()
    if not event_id or not plate: raise DomainError("MISSING", "称重号或车牌为空")
    kind = KINDS.get(unicodedata.normalize("NFKC", str(row['kind'])).strip().lower())
    if kind is None: raise DomainError("KIND", "称重类型须为毛重或皮重")
    unit = str(row['unit']).strip()
    if unit not in FACTORS: raise DomainError("UNIT", "重量单位无效")
    weight_kg = number(row['weight']) * FACTORS[unit]
    if weight_kg <= 0: raise DomainError("RANGE", "称重必须为正数")
    if weight_kg == weight_kg.to_integral_value(): weight_kg = weight_kg.quantize(D(1))
    weighed_at, weighed_local, day = moment(row['weighed_at'])
    event = {'event_id': event_id, 'plate': plate, 'kind': kind, 'weight_kg': weight_kg,
             'weighed_at': weighed_at, 'weighed_local': weighed_local, 'day': day,
             'bin': '', 'moisture': None, 'impurity': None, '_line': row.get('_line', '')}
    if kind == 'gross':
        bin_ = str(row['bin']).strip()
        if not bin_: raise DomainError("MISSING", "毛重缺少仓号")
        moisture = number(row['moisture']); impurity = number(row['impurity'])
        if not 0 <= moisture < 100 or not 0 <= impurity < 100: raise DomainError("RANGE", "水杂越界")
        if moisture > rules['max_moisture']: raise DomainError("LIMIT", "水分超过收购上限")
        event.update(bin=bin_, moisture=moisture, impurity=impurity)
    event['hash'] = fingerprint(event)
    return event
def pair(open_trips, loose_tares):
    """最近在先毛重配对：每条皮重绑定同车、称重时间在其之前且最近的未配对车次。
    皮重只消费一次；绑定只增不改。返回 (绑定[(皮重号,车次)], 备注{皮重号:原因})。"""
    trips = sorted(open_trips, key=lambda t: (t['gross_at'], t['trip_id']))
    bindings, notes = [], {}
    for tare in sorted(loose_tares, key=lambda e: (e['weighed_at'], e['event_id'])):
        candidates = [t for t in trips if t['gross_at'] < tare['weighed_at']]
        if not candidates:
            notes[tare['event_id']] = '无在先毛重可配对'; continue
        trip = max(candidates, key=lambda t: (t['gross_at'], t['trip_id']))
        if tare['weight_kg'] >= trip['gross_kg']:
            notes[tare['event_id']] = '皮重不小于最近毛重'; continue
        bindings.append((tare['event_id'], trip['trip_id']))
        trips.remove(trip)
    return bindings, notes
def estimate(gross_at, confirmed_tares, default_tare):
    """暂估皮重来源：同车称重时间在本趟毛重之前的最近一次实称皮重，否则默认皮重。"""
    earlier = [t for t in confirmed_tares if t[0] < gross_at]
    if earlier:
        _, event_id, weight_kg = max(earlier, key=lambda t: (t[0], t[1]))
        return event_id, weight_kg
    if default_tare is not None and default_tare > 0: return 'DEFAULT', default_tare
    return None
def chain_append(tail_exact, tail_rounded, exact):
    """累计舍入：本车次金额 = R(累计精确额) − 已确认累计额。
    仓批合计恒等于 R(精确总额)，且已定车次金额冻结不变。"""
    cum_exact = tail_exact + exact
    cum_after = fen(cum_exact)
    return cum_after - tail_rounded, cum_exact, cum_after
