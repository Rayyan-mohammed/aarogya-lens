"""Endpoint tests using FastAPI's TestClient — no running server or LLM key needed."""
import math


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["districts"] == 706
    assert body["states"] == 36


def test_schema(client):
    r = client.get("/schema")
    assert r.status_code == 200
    assert len(r.json()) == 448


def test_indicators(client):
    r = client.get("/indicators")
    assert r.status_code == 200
    body = r.json()
    assert body["total_indicators"] == 448
    assert len(body["clusters"]) > 0


def test_states(client):
    r = client.get("/states")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 36
    assert sum(s["districts"] for s in body["states"]) == 706


def test_districts_by_state(client):
    r = client.get("/districts/Kerala")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "Kerala"
    assert body["count"] > 0


def test_districts_by_state_fuzzy_match(client):
    r = client.get("/districts/keral")  # slight misspelling
    assert r.status_code == 200
    assert r.json()["state"] == "Kerala"


def test_districts_by_unknown_state_404s(client):
    r = client.get("/districts/CompletelyFakePlace")
    assert r.status_code == 404


def test_district_detail(client):
    r = client.get("/districts/Kerala")
    district_id = r.json()["districts"][0]["district_id"]
    r2 = client.get(f"/district/{district_id}")
    assert r2.status_code == 200
    assert r2.json()["district_id"] == district_id


def test_district_detail_handles_missing_values_without_crashing(client):
    """Thrissur has a genuinely missing vaccination value — this used to 500."""
    r = client.get("/districts/Kerala")
    thrissur = next(d for d in r.json()["districts"] if d["district"] == "Thrissur")
    r2 = client.get(f"/district/{thrissur['district_id']}")
    assert r2.status_code == 200


def test_district_detail_unknown_id_404s(client):
    r = client.get("/district/999999")
    assert r.status_code == 404


def test_national_summary(client):
    r = client.get("/national-summary")
    assert r.status_code == 200
    assert r.json()["n_districts"] == 706


def test_state_comparison(client):
    r = client.get("/state-comparison/stunting_pct")
    assert r.status_code == 200
    body = r.json()
    assert len(body["data"]) == 36


def test_state_comparison_unknown_indicator_404s(client):
    r = client.get("/state-comparison/not_a_real_column_xyz")
    assert r.status_code == 404


def test_query_direct_pandas(client):
    r = client.post("/query/direct", json={
        "tool": "pandas_query",
        "params": {"code": "result = df['stunting_pct'].mean()"},
    })
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_query_direct_unknown_tool_400s(client):
    r = client.post("/query/direct", json={"tool": "not_a_tool", "params": {}})
    assert r.status_code == 400


def test_response_never_contains_raw_nan(client):
    """A NaN literal in a JSON body means it was serialized with allow_nan=True,
    which most JSON parsers (including browsers') reject outright."""
    r = client.get("/districts/Kerala")
    assert "NaN" not in r.text


def test_benchmark_questions(client):
    r = client.get("/benchmark/questions")
    assert r.status_code == 200
    body = r.json()
    assert len(body["questions"]) == 200
