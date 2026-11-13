import json

from granth import answer, cache, cost, providers


class Fake(providers.Provider):
    def __init__(self, name, text=None, fail=False, external=True):
        self.name, self.text, self.fail, self.external, self.calls = name, text, fail, external, 0

    def configured(self):
        return True

    def generate(self, prompt, max_tokens=400):
        self.calls += 1
        if self.fail:
            raise providers.ProviderError("HTTP 429")
        return self.text


Q = "પ્રકાશસંશ્લેષણ માટે કઈ બાબતો જરૂરી છે?"


def test_cache_reuse_same_settings_zero_api_calls(con, ids):
    scope = {"edition_id": ids["sci"]}
    a = answer.ask(con, "પ્રકાશસંશ્લેષણ એટલે શું?", scope, session_id="student-A")
    b = answer.ask(con, "પ્રકાશસંશ્લેષણ  એટલે શું ?", scope, session_id="student-B")    # same question, extra spaces
    assert a["cache"]["hit"] is False and b["cache"]["hit"] is True
    assert b["answer"] == a["answer"] and b["citations"] == a["citations"] and b["external_api_calls"] == 0
    assert b["verification"]["verified"] and b["cache"]["created_at"]
    st = cache.stats(con)
    assert st["hits"] == 1 and st["misses"] == 1 and st["hit_rate"] == 0.5


def test_cache_key_separates_edition_chapter_mode_engine(con, ids):
    base = {"edition_ids": [1], "chapter_id": None, "mode": "short", "marks": None, "board": "b", "medium": "m",
            "standard": 10, "subject": "s"}
    k = cache.make_key("q", base, {1: 1})
    assert k == cache.make_key("q", dict(base), {1: 1})
    for change in ({"edition_ids": [2]}, {"chapter_id": 3}, {"mode": "detailed"}, {"marks": 5}, {"standard": 9},
                   {"subject": "x"}, {"board": "x"}, {"medium": "x"}):
        assert cache.make_key("q", {**base, **change}, {1: 1}) != k
    assert cache.make_key("q", base, {1: 2}) != k                      # corpus version
    assert cache.make_key("q", base, {1: 1}, engine_version="other") != k
    assert cache.make_key("q2", base, {1: 1}) != k


def test_answer_from_other_edition_is_never_reused(con, ids):
    q = "ઘરવપરાશના વિદ્યુતપુરવઠાનું વોલ્ટેજ કેટલું ગણવામાં આવ્યું છે?"
    a = answer.ask(con, q, {"edition_id": ids["sci"]}, mode="one_line")
    b = answer.ask(con, q, {"edition_id": ids["sci27"]}, mode="one_line")
    assert b["cache"]["hit"] is False and "230" in b["answer"]["text"] and "220" in a["answer"]["text"]


def test_abstentions_and_unverified_are_not_cached(con, ids):
    scope = {"edition_id": ids["sci"]}
    for _ in range(2):
        r = answer.ask(con, "જ્વાળામુખી એટલે શું?", scope)
        assert r["status"] == "abstained" and r["cache"]["hit"] is False
    assert con.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0] == 0
    assert cache.put(con, "k", "q", {"edition_ids": [1]}, {1: 1}, {"status": "answered", "verification": {"verified": False},
                                                                  "evidence": [{"chunk_id": 1, "text_sha256": "x"}]}) is False
    assert cache.put(con, "k", "q", {"edition_ids": [1]}, {1: 1}, {"status": "abstained", "verification": {"verified": True}}) is False


def test_cache_hit_revalidates_evidence_text(con, ids):
    scope = {"edition_id": ids["sci"]}
    a = answer.ask(con, "શ્વસન એટલે શું?", scope)
    cid = a["evidence"][0]["chunk_id"]
    con.execute("UPDATE text_chunks SET text_sha256='changed' WHERE id=?", (cid,))    # simulate corpus drift
    con.commit()
    b = answer.ask(con, "શ્વસન એટલે શું?", scope)
    assert b["cache"]["hit"] is False


def test_generation_disabled_by_default_makes_no_calls(con, ids):
    fake = Fake("fake", "anything")
    r = answer.ask(con, Q, {"edition_id": ids["sci"]}, mode="short", router=providers.Router([fake], enabled=False))
    assert fake.calls == 0 and r["external_api_calls"] == 0 and r["engine"] == "extractive"


def test_faithful_generation_is_accepted_after_verification(con, ids):
    fake = Fake("fake", "પ્રકાશસંશ્લેષણ માટે સૂર્યપ્રકાશ, હરિતદ્રવ્ય, કાર્બન ડાયૉક્સાઇડ અને પાણી જરૂરી છે.")
    r = answer.ask(con, Q, {"edition_id": ids["sci"]}, mode="short", router=providers.Router([fake], enabled=True, daily_limit=5))
    assert r["answer"]["generated"] is True and r["engine"].startswith("generative:fake") and r["external_api_calls"] == 1
    assert r["evidence"] and r["citations"][0]["page_number"] == 1


def test_hallucinated_generation_is_rejected_and_extractive_used(con, ids):
    fake = Fake("fake", "પ્રકાશસંશ્લેષણ માટે સૂર્યપ્રકાશ અને નાઇટ્રોજન જરૂરી છે. આ શોધ 1779 માં થઈ હતી.")
    r = answer.ask(con, Q, {"edition_id": ids["sci"]}, mode="short", router=providers.Router([fake], enabled=True, daily_limit=5))
    assert r["answer"]["generated"] is False and r["engine"] == "extractive"
    assert r["generation"]["accepted"] is False and "નાઇટ્રોજન" not in r["answer"]["text"] and "1779" not in r["answer"]["text"]


def test_provider_failure_falls_back_to_next_then_extractive(con, ids):
    bad, good = Fake("a", fail=True), Fake("b", "પ્રકાશસંશ્લેષણ માટે પાણી જરૂરી છે.")
    r = answer.ask(con, Q, {"edition_id": ids["sci"]}, mode="short", router=providers.Router([bad, good], enabled=True, daily_limit=9))
    assert bad.calls == 1 and good.calls == 1 and r["answer"]["generated"] is True
    r2 = answer.ask(con, "શ્વસનતંત્ર વિશે લખો", {"edition_id": ids["sci"]}, mode="short",
                    router=providers.Router([Fake("a", fail=True)], enabled=True, daily_limit=9))
    assert r2["status"] == "answered" and r2["engine"] == "extractive"      # still useful with every provider down


def test_daily_budget_stops_external_calls(con, ids):
    fake = Fake("fake", "પ્રકાશસંશ્લેષણ માટે પાણી જરૂરી છે.")
    router = providers.Router([fake], enabled=True, daily_limit=1)
    answer.ask(con, Q, {"edition_id": ids["sci"]}, mode="short", router=router, use_cache=False)
    answer.ask(con, Q, {"edition_id": ids["sci"]}, mode="short", router=router, use_cache=False)
    assert fake.calls == 1
    s = cost.summary(con)
    assert s["external_api_calls"] == 1 and any(e["kind"] == "budget_exhausted" for e in s["events"])


def test_cached_generated_answer_costs_zero_calls_second_time(con, ids):
    fake = Fake("fake", "પ્રકાશસંશ્લેષણ માટે પાણી જરૂરી છે.")
    router = providers.Router([fake], enabled=True, daily_limit=9)
    answer.ask(con, Q, {"edition_id": ids["sci"]}, mode="short", router=router)
    b = answer.ask(con, Q, {"edition_id": ids["sci"]}, mode="short", router=router)
    assert fake.calls == 1 and b["cache"]["hit"] and b["external_api_calls"] == 0


def test_real_providers_unconfigured_without_keys(monkeypatch):
    for k in ("GEMINI_API_KEY", "HUGGINGFACE_API_TOKEN", "OTHER_PROVIDER_API_KEY", "LOCAL_MODEL_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    st = {p["name"]: p["configured"] for p in providers.Router(enabled=True).status()}
    assert st["extractive"] is True and st["gemini"] is False and st["huggingface"] is False


def test_secrets_are_masked():
    from granth import config
    assert config.mask("AIzaSyD-very-secret-1234") == "****1234" and config.mask("") == "(not set)"


def test_cost_summary_counts(con, ids):
    answer.ask(con, "શ્વસન એટલે શું?", {"edition_id": ids["sci"]})
    answer.ask(con, "શ્વસન એટલે શું?", {"edition_id": ids["sci"]})
    s = cost.summary(con)
    assert s["external_api_calls"] == 0 and s["local_retrievals"] == 1 and s["cache"]["hits"] == 1
    assert s["storage"]["database_bytes"] > 0 and s["answers_served"] == 2
    json.dumps(s)
