import csv, io
import pytest
from decimal import Decimal as D
from app.pipeline import run
from app.tripdesk.rules import pair, estimate, chain_append, fen
HEADER = "event_id,plate,kind,weight,unit,weighed_at,bin,moisture,impurity"
DAY1 = "\n".join([HEADER,
    "G1,辽A00177,gross,15200,kg,2026-11-18T08:05:00+08:00,仓1,15,1.2",
    "T1,辽A00177,tare,5100,kg,2026-11-18T08:50:00+08:00,,,",
    "G2,辽A00177,gross,15100,kg,2026-11-18T11:20:00+08:00,仓1,15.4,1.1",
    "G3,辽A00177,gross,15300,kg,2026-11-18T15:40:00+08:00,仓2,16,1",
    "T3,辽A00177,tare,5120,kg,2026-11-18T16:30:00+08:00,,,"])
DAY2 = "\n".join([HEADER,
    "T2,辽A00177,tare,5080,kg,2026-11-18T12:10:00+08:00,,,"])
def upload(client, text, params=None):
    return client.post("/api/trips/uploads", json={"text": text, "params": params or {}})
def snap(client):
    reply = client.get("/api/trips"); assert reply.status_code == 200
    return reply.json
def by_id(state): return {t["trip_id"]: t for t in state["trips"]}
def gross(tid, plate="辽A00177", at="2026-11-18T08:00:00+08:00", kg="15000", bin_="仓1"):
    return f"{tid},{plate},gross,{kg},kg,{at},{bin_},15,1"
def tare(tid, plate="辽A00177", at="2026-11-18T09:00:00+08:00", kg="5000"):
    return f"{tid},{plate},tare,{kg},kg,{at},,,"
# ---- 纯规则：配对、暂估、分币链 ----
def test_pair_binds_nearest_preceding_gross():
    trips = [{"trip_id": "G1", "gross_at": "2026-11-18T00:05:00+00:00", "gross_kg": D(15200)},
             {"trip_id": "G2", "gross_at": "2026-11-18T03:20:00+00:00", "gross_kg": D(15100)}]
    tares = [{"event_id": "T2", "weighed_at": "2026-11-18T04:10:00+00:00", "weight_kg": D(5080)}]
    bindings, notes = pair(trips, tares)
    assert bindings == [("T2", "G2")] and notes == {}  # 第二趟的皮重不会记到第一趟
def test_pair_tare_consumed_once():
    trips = [{"trip_id": "G1", "gross_at": "2026-11-18T00:05:00+00:00", "gross_kg": D(15000)},
             {"trip_id": "G2", "gross_at": "2026-11-18T03:20:00+00:00", "gross_kg": D(15000)}]
    tares = [{"event_id": "T1", "weighed_at": "2026-11-18T01:00:00+00:00", "weight_kg": D(5000)},
             {"event_id": "T2", "weighed_at": "2026-11-18T04:00:00+00:00", "weight_kg": D(5000)}]
    bindings, _ = pair(trips, tares)
    assert bindings == [("T1", "G1"), ("T2", "G2")]
def test_pair_tare_without_prior_gross_stays_loose():
    _, notes = pair([], [{"event_id": "T9", "weighed_at": "2026-11-18T01:00:00+00:00", "weight_kg": D(5000)}])
    assert notes == {"T9": "无在先毛重可配对"}
def test_pair_tare_not_lighter_than_gross_stays_loose():
    trips = [{"trip_id": "G1", "gross_at": "2026-11-18T00:05:00+00:00", "gross_kg": D(5000)}]
    tares = [{"event_id": "T1", "weighed_at": "2026-11-18T01:00:00+00:00", "weight_kg": D(5000)}]
    bindings, notes = pair(trips, tares)
    assert bindings == [] and notes["T1"] == "皮重不小于最近毛重"
def test_pair_result_is_arrival_order_independent():
    trips = [{"trip_id": "G1", "gross_at": "2026-11-18T00:05:00+00:00", "gross_kg": D(15000)},
             {"trip_id": "G2", "gross_at": "2026-11-18T03:20:00+00:00", "gross_kg": D(15000)}]
    tares = [{"event_id": "T1", "weighed_at": "2026-11-18T01:00:00+00:00", "weight_kg": D(5000)},
             {"event_id": "T2", "weighed_at": "2026-11-18T04:00:00+00:00", "weight_kg": D(5100)}]
    first, _ = pair(trips, tares)
    again, _ = pair(trips, list(reversed(tares)))
    assert first == again == [("T1", "G1"), ("T2", "G2")]
def test_estimate_prefers_latest_confirmed_tare():
    confirmed = [("2026-11-18T01:00:00+00:00", "T1", D(5100)), ("2026-11-18T06:00:00+00:00", "T3", D(5120))]
    assert estimate("2026-11-18T03:00:00+00:00", confirmed, None) == ("T1", D(5100))
    assert estimate("2026-11-18T07:00:00+00:00", confirmed, None) == ("T3", D(5120))
def test_estimate_falls_back_to_default_then_none():
    assert estimate("2026-11-18T03:00:00+00:00", [], D(5000)) == ("DEFAULT", D(5000))
    assert estimate("2026-11-18T03:00:00+00:00", [], None) is None
def test_chain_append_conserves_and_freezes():
    tail_exact, tail_rounded, amounts = D(0), D(0), []
    for _ in range(3):
        amount, tail_exact, tail_rounded = chain_append(tail_exact, tail_rounded, D("0.005"))
        amounts.append(amount)
    assert amounts == [D("0.01"), D("0.00"), D("0.01")]
    assert sum(amounts) == fen(D("0.015")) == D("0.02")  # 分录守恒到分
# ---- 入账与配对 ----
def test_upload_pairs_and_marks_pending(client):
    reply = upload(client, DAY1)
    assert reply.status_code == 200 and reply.json["accepted"] == 5
    state = snap(client); trips = by_id(state)
    assert trips["G1"]["state"] == "实称" and trips["G1"]["tare_event_id"] == "T1"
    assert D(trips["G1"]["net_kg"]) == D(10100)
    assert trips["G2"]["state"] == "暂估" and trips["G2"]["estimate_source"] == "T1"
    assert D(trips["G2"]["net_kg"]) == D(10000)  # 暂估用同车最近一次实称皮重
    assert trips["G3"]["state"] == "实称"
    assert [t["trip_id"] for t in state["pending_trips"]] == ["G2"]
    assert state["loose_tares"] == []
def test_late_tare_completes_trip_without_disturbing_settled(client):
    upload(client, DAY1)
    before = by_id(snap(client))
    order_before = [t["trip_id"] for t in snap(client)["trips"]]
    upload(client, DAY2)
    state = snap(client); after = by_id(state)
    assert after["G2"]["state"] == "实称" and after["G2"]["tare_event_id"] == "T2"
    assert D(after["G2"]["net_kg"]) == D(10020)
    for tid in ("G1", "G3"):  # 已定车次不被挤乱
        assert after[tid]["net_kg"] == before[tid]["net_kg"]
        assert after[tid]["amount"] == before[tid]["amount"]
        assert after[tid]["tare_event_id"] == before[tid]["tare_event_id"]
        assert after[tid]["version"] == before[tid]["version"]
    assert [t["trip_id"] for t in state["trips"]] == order_before
    assert state["pending_trips"] == []
def test_same_upload_replays_without_double_intake(client):
    upload(client, DAY1)
    reply = upload(client, DAY1)
    assert reply.status_code == 200 and reply.json["replay"] is True
    state = snap(client)
    assert state["totals"]["trips"] == 3 and len(state["uploads"]) == 1
def test_overlapping_upload_only_books_new_events(client):
    upload(client, DAY1)
    reply = upload(client, DAY1 + "\n" + DAY2.split("\n", 1)[1])
    assert reply.json["accepted"] == 1 and reply.json["quarantined"] == 5
    state = snap(client)
    assert state["totals"]["trips"] == 3
    assert sum(q["code"] == "DUPLICATE" for q in state["quarantine"]) == 5
def test_conflict_same_event_id_keeps_first(client):
    upload(client, DAY1)
    reply = upload(client, "\n".join([HEADER, "T1,辽A00177,tare,5200,kg,2026-11-18T08:50:00+08:00,,,"]))
    assert reply.json["accepted"] == 0
    state = snap(client)
    assert any(q["code"] == "CONFLICT" for q in state["quarantine"])
    assert by_id(state)["G1"]["tare_kg"] == "5100"  # 采信首次入账
def test_duplicate_row_within_one_file(client):
    reply = upload(client, "\n".join([HEADER, gross("G1"), gross("G1")]))
    assert reply.json["accepted"] == 1 and reply.json["quarantined"] == 1
    assert snap(client)["quarantine"][0]["code"] == "DUPLICATE"
def test_loose_tare_binds_when_its_gross_arrives(client):
    upload(client, "\n".join([HEADER, tare("T9", at="2026-11-18T07:00:00+08:00")]))
    assert snap(client)["loose_tares"][0]["note"] == "无在先毛重可配对"
    upload(client, "\n".join([HEADER, gross("G9", at="2026-11-18T06:30:00+08:00")]))
    state = snap(client)
    assert state["loose_tares"] == [] and by_id(state)["G9"]["tare_event_id"] == "T9"
def test_tare_earlier_than_gross_never_binds(client):
    upload(client, "\n".join([HEADER, gross("G1", at="2026-11-18T08:00:00+08:00"),
                              tare("T1", at="2026-11-18T07:00:00+08:00")]))
    state = snap(client)
    assert by_id(state)["G1"]["state"] == "待皮重" and len(state["loose_tares"]) == 1
# ---- 金额：冻结与守恒 ----
def test_amounts_frozen_and_chain_conserved(client):
    upload(client, DAY1)
    before = by_id(snap(client))
    upload(client, DAY2)
    state = snap(client); after = by_id(state)
    assert after["G1"]["amount"] == before["G1"]["amount"]
    chain = next(c for c in state["chains"] if c["bin"] == "仓1")
    assert D(chain["confirmed_amount"]) == D(after["G1"]["amount"]) + D(after["G2"]["amount"])
    exact = sum(D(after[t]["standard_kg"]) * D("2.6") for t in ("G1", "G2"))
    assert D(chain["confirmed_amount"]) == fen(exact)  # 仓批应付 = R(精确总额)
def test_chain_total_equals_rounded_exact_per_chain(client):
    upload(client, DAY1); upload(client, DAY2)
    state = snap(client); trips = by_id(state)
    for chain in state["chains"]:
        exact = sum(D(t["standard_kg"]) * D("2.6") for t in state["trips"]
                    if t["bin"] == chain["bin"] and t["day"] == chain["day"] and t["amount"] is not None)
        assert D(chain["confirmed_amount"]) == fen(exact)
def test_estimated_amounts_add_to_chain_total(client):
    upload(client, DAY1)
    state = snap(client)
    chain = next(c for c in state["chains"] if c["bin"] == "仓1")
    assert D(chain["amount"]) == D(chain["confirmed_amount"]) + D(chain["estimated_amount"])
    assert D(chain["estimated_amount"]) > 0
# ---- 参数锁定 ----
def test_params_locked_after_first_upload(client):
    assert upload(client, DAY1, {"price": "2.6"}).status_code == 200
    reply = upload(client, DAY2, {"price": "3.0"})
    assert reply.status_code == 409 and reply.json["code"] == "PARAMS_LOCKED"
    assert upload(client, DAY2, {"price": "2.60"}).status_code == 200  # 数值相等放行
# ---- 暂估 ----
def test_default_tare_estimate_when_no_history(client):
    upload(client, "\n".join([HEADER, gross("G1")]), {"default_tare_kg": "5000"})
    trip = by_id(snap(client))["G1"]
    assert trip["state"] == "暂估" and trip["estimate_source"] == "DEFAULT"
    assert D(trip["net_kg"]) == D(10000)
def test_pending_without_any_source(client):
    upload(client, "\n".join([HEADER, gross("G1")]))
    trip = by_id(snap(client))["G1"]
    assert trip["state"] == "待皮重" and trip["net_kg"] is None
# ---- 数据契约 ----
def test_fullwidth_number_and_ton_unit(client):
    upload(client, "\n".join([HEADER, "G1,辽A00177,gross,１５，２００,kg,2026-11-18T08:00:00+08:00,仓1,15,1",
                              "T1,辽A00177,tare,5.1,t,2026-11-18T09:00:00+08:00,,,"]))
    assert D(by_id(snap(client))["G1"]["net_kg"]) == D(10100)
def test_over_limit_moisture_quarantined(client):
    reply = upload(client, "\n".join([HEADER, gross("G1").replace(",15,1", ",35,1"),
                                      tare("T1")]))
    assert reply.json["accepted"] == 1  # 仅皮重入账
    state = snap(client)
    assert state["quarantine"][0]["code"] == "LIMIT"
    assert state["totals"]["trips"] == 0 and len(state["loose_tares"]) == 1
def test_missing_bin_on_gross_quarantined(client):
    reply = upload(client, "\n".join([HEADER, "G1,辽A00177,gross,15000,kg,2026-11-18T08:00:00+08:00,,15,1"]))
    assert reply.json["accepted"] == 0 and snap(client)["quarantine"][0]["code"] == "MISSING"
def test_bad_kind_quarantined(client):
    upload(client, "\n".join([HEADER, "G1,辽A00177,weigh,15000,kg,2026-11-18T08:00:00+08:00,仓1,15,1"]))
    assert snap(client)["quarantine"][0]["code"] == "KIND"
def test_rows_balance_per_upload(client):
    reply = upload(client, DAY1 + "\n\n" + "bad,row\n")
    assert reply.json["rows"] == reply.json["accepted"] + reply.json["quarantined"]
    assert reply.json["blank"] == 1
# ---- 对账与导出 ----
def test_reconcile_checks_balanced(client):
    upload(client, DAY1); upload(client, DAY2)
    state = snap(client)
    assert state["reconcile"]["balanced"] is True
    assert all(c["ok"] for c in state["reconcile"]["checks"])
def test_export_reconciles_with_pipeline_per_chain(client):
    upload(client, DAY1); upload(client, DAY2)
    text = client.get("/api/trips/export.csv").text.lstrip("﻿")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 3
    state = snap(client)
    for chain in state["chains"]:
        subset = [r for r in rows if r["bin"] == chain["bin"]]
        body = "id,bin,gross,tare,unit,moisture,impurity,version\n" + "\n".join(
            ",".join(r[k] for k in ["id", "bin", "gross", "tare", "unit", "moisture", "impurity", "version"]) for r in subset)
        result = run(body, stop=6, persist=False)
        assert D(result["total_amount"]) == D(chain["confirmed_amount"])  # 与M1-M6管线一致
        assert sum(D(r["net_kg"]) for r in result["records"]) == D(chain["net_kg"])
def test_pages_and_api(client):
    assert client.get("/trips").status_code == 200
    assert client.get("/api/trips").status_code == 200
    assert client.get("/api/trips/export.csv").status_code == 200
    upload(client, DAY1)
    assert "G1" in client.get("/trips").get_data(as_text=True)
def test_sample_files_flow(client):
    from app.config import SAMPLES
    day1 = (SAMPLES / "weigh_day1.csv").read_text(encoding="utf-8-sig")
    day2 = (SAMPLES / "weigh_day2.csv").read_text(encoding="utf-8-sig")
    upload(client, day1)
    state = snap(client)
    assert state["totals"]["trips"] == 5 and state["totals"]["pending"] == 1
    assert len(state["loose_tares"]) == 1  # E-T-1999 的毛重行被隔离
    upload(client, day2)
    state = snap(client)
    trips = by_id(state)
    assert trips["E-G-1102"]["state"] == "实称" and trips["E-G-1102"]["tare_event_id"] == "E-T-1102"
    assert trips["E-G-1103"]["tare_kg"] == "5120"  # 冲突补传不改已定车次
    assert state["reconcile"]["balanced"] is True
    assert sum(q["code"] == "CONFLICT" for q in state["quarantine"]) == 1
    assert sum(q["code"] == "DUPLICATE" for q in state["quarantine"]) == 2
