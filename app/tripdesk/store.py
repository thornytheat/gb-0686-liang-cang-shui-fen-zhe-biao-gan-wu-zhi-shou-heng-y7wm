import json
from decimal import Decimal as D
from datetime import datetime, timezone
from app.store import connection
SCHEMA = """
CREATE TABLE IF NOT EXISTS td_meta (id INTEGER PRIMARY KEY CHECK(id=1), params TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS td_uploads (upload_id TEXT PRIMARY KEY, created TEXT NOT NULL, rows INTEGER NOT NULL, accepted INTEGER NOT NULL, quarantine TEXT NOT NULL, params TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS td_events (event_id TEXT PRIMARY KEY, plate TEXT NOT NULL, kind TEXT NOT NULL, weight_kg TEXT NOT NULL, weighed_at TEXT NOT NULL, weighed_local TEXT NOT NULL, day TEXT NOT NULL, bin TEXT NOT NULL DEFAULT '', moisture TEXT, impurity TEXT, hash TEXT NOT NULL, upload_id TEXT NOT NULL, line INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS td_events_plate ON td_events(plate, kind);
CREATE TABLE IF NOT EXISTS td_trips (trip_id TEXT PRIMARY KEY, plate TEXT NOT NULL, bin TEXT NOT NULL, day TEXT NOT NULL, gross_event_id TEXT NOT NULL UNIQUE, gross_at TEXT NOT NULL, gross_local TEXT NOT NULL, gross_kg TEXT NOT NULL, moisture TEXT NOT NULL, impurity TEXT NOT NULL, tare_event_id TEXT, tare_at TEXT, tare_local TEXT, tare_kg TEXT, tare_state TEXT NOT NULL, estimate_source TEXT, estimate_kg TEXT, net_kg TEXT, clean_kg TEXT, dry_kg TEXT, standard_kg TEXT, amount TEXT, cum_exact TEXT, cum_after TEXT, seq INTEGER, version INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL, updated TEXT NOT NULL, audit TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS td_trips_plate ON td_trips(plate);
CREATE INDEX IF NOT EXISTS td_trips_chain ON td_trips(bin, day, seq);
"""
def now(): return datetime.now(timezone.utc).isoformat()
def db():
    conn = connection()
    conn.executescript(SCHEMA)
    return conn
def locked_params(conn):
    row = conn.execute("SELECT params FROM td_meta WHERE id=1").fetchone()
    return None if row is None else json.loads(row["params"])
def lock_params(conn, params):
    locked = locked_params(conn)
    if locked is None:
        conn.execute("INSERT INTO td_meta(id,params,created) VALUES(1,?,?)",
                     (json.dumps(params, ensure_ascii=False, sort_keys=True), now()))
        return params
    return locked
def find_upload(conn, upload_id):
    row = conn.execute("SELECT * FROM td_uploads WHERE upload_id=?", (upload_id,)).fetchone()
    if row is None: return None
    return {"upload_id": row["upload_id"], "created": row["created"], "rows": row["rows"],
            "accepted": row["accepted"], "quarantined": len(json.loads(row["quarantine"])), "replay": True}
def record_upload(conn, upload_id, summary, quarantine, params):
    conn.execute("INSERT INTO td_uploads(upload_id,created,rows,accepted,quarantine,params) VALUES(?,?,?,?,?,?)",
                 (upload_id, summary["created"], summary["rows"], summary["accepted"],
                  json.dumps(quarantine, ensure_ascii=False), json.dumps(params, ensure_ascii=False, sort_keys=True)))
def get_event(conn, event_id):
    row = conn.execute("SELECT * FROM td_events WHERE event_id=?", (event_id,)).fetchone()
    return None if row is None else dict(row)
def insert_event(conn, ev, upload_id):
    conn.execute("INSERT INTO td_events(event_id,plate,kind,weight_kg,weighed_at,weighed_local,day,bin,moisture,impurity,hash,upload_id,line) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (ev["event_id"], ev["plate"], ev["kind"], str(ev["weight_kg"]), ev["weighed_at"], ev["weighed_local"],
                  ev["day"], ev["bin"], None if ev["moisture"] is None else str(ev["moisture"]),
                  None if ev["impurity"] is None else str(ev["impurity"]), ev["hash"], upload_id, ev["_line"]))
def event_count(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM td_events").fetchone()["n"]
def insert_trip(conn, trip):
    conn.execute("INSERT INTO td_trips(trip_id,plate,bin,day,gross_event_id,gross_at,gross_local,gross_kg,moisture,impurity,tare_state,created,updated,audit) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (trip["trip_id"], trip["plate"], trip["bin"], trip["day"], trip["gross_event_id"], trip["gross_at"],
                  trip["gross_local"], str(trip["gross_kg"]), str(trip["moisture"]), str(trip["impurity"]),
                  trip["tare_state"], now(), now(), json.dumps(trip["audit"], ensure_ascii=False)))
def get_trip(conn, trip_id):
    row = conn.execute("SELECT * FROM td_trips WHERE trip_id=?", (trip_id,)).fetchone()
    return None if row is None else dict(row)
def open_trips(conn, plate):
    rows = conn.execute("SELECT * FROM td_trips WHERE plate=? AND tare_event_id IS NULL ORDER BY gross_at, trip_id", (plate,)).fetchall()
    return [dict(row) for row in rows]
def loose_tares(conn, plate=None):
    sql = ("SELECT e.* FROM td_events e WHERE e.kind='tare' "
           "AND NOT EXISTS (SELECT 1 FROM td_trips t WHERE t.tare_event_id=e.event_id)")
    args = ()
    if plate is not None: sql, args = sql + " AND e.plate=?", (plate,)
    rows = conn.execute(sql + " ORDER BY e.weighed_at, e.event_id", args).fetchall()
    return [dict(row) for row in rows]
def confirmed_tares(conn, plate):
    rows = conn.execute("SELECT tare_at,tare_event_id,tare_kg FROM td_trips WHERE plate=? AND tare_event_id IS NOT NULL", (plate,)).fetchall()
    return [(row["tare_at"], row["tare_event_id"], D(row["tare_kg"])) for row in rows]
def chain_tail(conn, bin_, day):
    row = conn.execute("SELECT cum_exact,cum_after,seq FROM td_trips WHERE bin=? AND day=? AND seq IS NOT NULL ORDER BY seq DESC LIMIT 1", (bin_, day)).fetchone()
    if row is None: return {"cum_exact": D(0), "cum_after": D(0), "seq": 0}
    return {"cum_exact": D(row["cum_exact"]), "cum_after": D(row["cum_after"]), "seq": row["seq"]}
def bind_tare(conn, trip_id, tare, conv, amount, cum_exact, cum_after, seq, audit):
    conn.execute("UPDATE td_trips SET tare_event_id=?,tare_at=?,tare_local=?,tare_kg=?,tare_state='实称',"
                 "estimate_source=NULL,estimate_kg=NULL,net_kg=?,clean_kg=?,dry_kg=?,standard_kg=?,"
                 "amount=?,cum_exact=?,cum_after=?,seq=?,version=version+1,updated=?,audit=? WHERE trip_id=?",
                 (tare["event_id"], tare["weighed_at"], tare["weighed_local"], str(tare["weight_kg"]),
                  str(conv["net_kg"]), str(conv["clean_kg"]), str(conv["dry_kg"]), str(conv["standard_kg"]),
                  str(amount), str(cum_exact), str(cum_after), seq, now(), json.dumps(audit, ensure_ascii=False), trip_id))
def set_estimate(conn, trip_id, state, source, kg, conv, audit):
    conn.execute("UPDATE td_trips SET tare_state=?,estimate_source=?,estimate_kg=?,net_kg=?,clean_kg=?,dry_kg=?,standard_kg=?,"
                 "version=version+1,updated=?,audit=? WHERE trip_id=?",
                 (state, source, None if kg is None else str(kg),
                  None if conv is None else str(conv["net_kg"]), None if conv is None else str(conv["clean_kg"]),
                  None if conv is None else str(conv["dry_kg"]), None if conv is None else str(conv["standard_kg"]),
                  now(), json.dumps(audit, ensure_ascii=False), trip_id))
def all_trips(conn):
    rows = conn.execute("SELECT * FROM td_trips ORDER BY gross_at, trip_id").fetchall()
    return [dict(row) for row in rows]
def uploads(conn):
    rows = conn.execute("SELECT * FROM td_uploads ORDER BY created, upload_id").fetchall()
    result = []
    for row in rows:
        result.append({"upload_id": row["upload_id"], "created": row["created"], "rows": row["rows"],
                       "accepted": row["accepted"], "quarantine": json.loads(row["quarantine"])})
    return result
