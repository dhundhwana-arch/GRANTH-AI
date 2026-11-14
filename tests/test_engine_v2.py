"""Engine extractive-1.1: languages, structured answers, supplementary mode, personal notes, saved answers."""
import json

import pytest

from granth import answer, api, ingest, lang
from conftest import SAMPLE
from test_api import server  # noqa: F401  (shared HTTP fixture)


def sup_id(con):
    return con.execute("SELECT id FROM textbook_editions WHERE role='supplementary'").fetchone()[0]


def corpus(slug="granth_vigyan_10_2026"):
    return " ".join((SAMPLE / slug / "content.txt").read_text(encoding="utf-8").split())


@pytest.mark.parametrize("q,expected", [("પ્રકાશસંશ્લેષણ એટલે શું?", "gu"), ("What is photosynthesis?", "en"),
                                        ("photosynthesis એટલે શું?", "mixed"), ("प्रकाश संश्लेषण क्या है?", "hi"), ("12345", "other")])
def test_language_detection(q, expected):
    assert lang.detect_language(q)["language"] == expected


def test_english_question_is_answered_with_verbatim_gujarati_source_text(con, ids):
    r = answer.ask(con, "What is photosynthesis?", {"edition_id": ids["sci"]})
    assert r["status"] == "answered" and r["language"] == "en" and r["question"] == "What is photosynthesis?"
    assert r["query_translation"]["terms"] == [{"en": "photosynthesis", "gu": "પ્રકાશસંશ્લેષણ"}]
    assert all(p["text"] in corpus() for p in r["answer"]["parts"])
    assert r["citations"][0]["page_number"] == 1


def test_unknown_english_word_is_not_guessed(con, ids):
    r = answer.ask(con, "What is a volcano?", {"edition_id": ids["sci"]})
    assert r["status"] == "abstained" and r["message"] == answer.ABSTAIN_MESSAGE
    assert r["query_translation"]["unmapped"] == ["volcano"]


def test_english_difference_and_formula_questions(con, ids):
    d = answer.ask(con, "Explain the difference between aerobic respiration and anaerobic respiration.", {"edition_id": ids["sci"]})
    assert d["status"] == "answered" and d["mode"] == "difference" and d["citations"][0]["page_number"] == 3
    f = answer.ask(con, "Write the formula of Ohm's law", {"edition_id": ids["sci"]})
    assert f["status"] == "answered" and "V = I × R" in f["answer"]["text"]


def test_hindi_question_is_refused_not_guessed(con, ids):
    r = answer.ask(con, "प्रकाश संश्लेषण क्या है?", {"edition_id": ids["sci"]})
    assert r["status"] == "abstained" and r["reason"] == "language_not_supported"


def test_structured_answer_has_all_sections_and_no_percentage(con, ids):
    r = answer.ask(con, "ઓહ્મનો નિયમ લખો", {"edition_id": ids["sci"]}, mode="short")
    st = r["structured"]
    assert st["question"] == "ઓહ્મનો નિયમ લખો"
    assert "ઓહ્મનો નિયમ કહે છે" in " ".join(p["text"] for p in st["simple_answer"])
    assert st["key_points"] and st["basis"] == r["citations"]
    assert st["trust"] == {"status": "verified", "label_gu": "સ્રોત સાથે ચકાસેલું", "label_en": "Verified against source", "reasons": []}
    assert st["answer_source_type"] == "quotation"
    assert all(p["source_type"] == "quotation" for p in r["answer"]["parts"])
    assert "%" not in json.dumps(st, ensure_ascii=False)
    # glossary help comes from the book's own શબ્દાર્થ and is labelled as such
    assert all(w["source_type"] == "textbook_glossary" for w in st["word_help"])


def test_trust_is_partial_when_requested_length_is_not_supported(con, ids):
    r = answer.ask(con, "ફેફસાં વિશે લખો", {"edition_id": ids["sci"]}, marks=5)
    if r["status"] == "answered" and r["length_supported"] is False:
        assert r["structured"]["trust"]["status"] == "partial" and r["structured"]["trust"]["reasons"]
    else:
        assert r["status"] in ("answered", "abstained")


def test_refusal_carries_insufficient_trust_and_exact_message(con, ids):
    r = answer.ask(con, "જ્વાળામુખી કેવી રીતે ફાટે છે?", {"edition_id": ids["sci"]})
    assert r["status"] == "abstained" and r["message"] == "આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી."
    assert r["structured"]["trust"]["status"] == "insufficient" and r["structured"]["trust"]["label_en"] == "Insufficient source evidence"


def test_ambiguous_single_word_question_is_refused_with_suggestions(con, ids):
    r = answer.ask(con, "નિયમ", {"edition_id": ids["sci"]})
    assert r["status"] == "abstained" and r["reason"] == "ambiguous_question" and len(r["suggestions"]) >= 3
    # the same word inside one chosen chapter is no longer ambiguous
    r2 = answer.ask(con, "ઓહ્મનો નિયમ", {"edition_id": ids["sci"]})
    assert r2["status"] == "answered"


def test_worked_example_steps_are_copied_never_computed(con, ids):
    r = answer.ask(con, "ઓહ્મના નિયમનું ઉદાહરણ પગલાંવાર સમજાવો", {"edition_id": ids["sci"]})
    assert r["status"] == "answered" and r["mode"] == "steps" and r["citations"][0]["page_number"] == 8
    assert r["answer"]["text"].startswith("પગલું 1:") and "પગલું 2:" in r["answer"]["text"]
    assert all(p["text"] in corpus() for p in r["answer"]["parts"])
    new = answer.ask(con, "5 ઓહ્મ અવરોધમાંથી 3 ઍમ્પિયર પ્રવાહ વહે તો વોલ્ટેજ કેટલું થાય?", {"edition_id": ids["sci"]})
    assert new["status"] == "abstained"


def test_formula_lookup_returns_the_statement_printed_before_the_formula(con, ids):
    r = answer.ask(con, "V = I × R કયો નિયમ છે?", {"edition_id": ids["sci"]})
    assert r["status"] == "answered" and "ઓહ્મનો નિયમ કહે છે" in r["answer"]["text"] and r["citations"][0]["page_number"] == 7
    m = answer.ask(con, "m = -v/u સૂત્ર શાનું છે?", {"edition_id": ids["sci"]})
    assert "મોટવણી કહે છે" in m["answer"]["text"]
    assert answer.ask(con, "E = mc² સમજાવો", {"edition_id": ids["sci"]})["status"] == "abstained"


def test_supplementary_is_never_used_unless_selected_and_never_mixed(con, ids):
    q = "ન્યૂટનનો ત્રીજો નિયમ સમજાવો"
    plain = answer.ask(con, q, {"edition_id": ids["sci"]})
    assert plain["status"] == "abstained" and plain["supplementary"] is None
    r = answer.ask(con, q, {"edition_id": ids["sci"]}, supplementary_edition_id=sup_id(con))
    assert r["status"] == "abstained" and r["answer"] is None and r["evidence"] == []      # textbook part unchanged
    s = r["supplementary"]
    assert s["status"] == "answered" and "પ્રતિક્રિયા બળ" in s["answer"]["text"]
    assert s["structured"]["answer_source_type"] == "supplementary" and s["source"]["license"] == "CC BY 4.0"
    assert "પાઠ્યપુસ્તકનો ભાગ નથી" in s["notice_gu"]
    # scope searches over everything never reach the supplementary source
    wide = answer.ask(con, q, {})
    assert wide["status"] == "abstained"
    # a supplementary edition cannot be passed off as the textbook, nor a textbook as supplementary
    assert answer.ask(con, q, {"edition_id": sup_id(con)})["status"] == "abstained"
    assert answer.ask(con, q, {"edition_id": ids["sci"]}, supplementary_edition_id=ids["soc"])["supplementary"] is None


def test_supplementary_answers_the_requested_example_questions(con, ids):
    sup = sup_id(con)
    r = answer.ask(con, "ભારતનું બંધારણ ક્યારે અમલમાં આવ્યું?", {"edition_id": ids["sci"]}, supplementary_edition_id=sup)
    assert "26 જાન્યુઆરી 1950" in r["supplementary"]["answer"]["text"]
    r = answer.ask(con, "What is quadratic equation?", {"edition_id": ids["sci"]}, supplementary_edition_id=sup)
    assert "દ્વિઘાત સમીકરણ કહે છે" in r["supplementary"]["answer"]["text"]
    r = answer.ask(con, "Explain the difference between mitosis and meiosis.", {"edition_id": ids["sci"]}, supplementary_edition_id=sup)
    assert r["supplementary"]["mode"] == "difference" and "અર્ધીકરણ" in r["supplementary"]["answer"]["text"]


def test_personal_notes_are_private_uncached_and_deletable(con, ids):
    with pytest.raises(ingest.IngestionRefused):
        ingest.add_personal_notes(con, "sess-aaaa-0001", "t", "ચુંબકને બે ધ્રુવ હોય છે: ઉત્તર ધ્રુવ અને દક્ષિણ ધ્રુવ.", False)
    with pytest.raises(ingest.IngestionRefused):
        ingest.add_personal_notes(con, "anonymous", "t", "ચુંબકને બે ધ્રુવ હોય છે: ઉત્તર ધ્રુવ અને દક્ષિણ ધ્રુવ.", True)
    n = ingest.add_personal_notes(con, "sess-aaaa-0001", "મારી નોંધ",
                                  "ચુંબકની આસપાસ જે વિસ્તારમાં તેની અસર અનુભવાય છે તે વિસ્તારને ચુંબકીય ક્ષેત્ર કહે છે.", True)
    q = "ચુંબકીય ક્ષેત્ર એટલે શું?"
    mine = answer.ask(con, q, {"edition_id": n["edition_id"]}, session_id="sess-aaaa-0001")
    assert mine["status"] == "answered" and mine["structured"]["answer_source_type"] == "personal"
    again = answer.ask(con, q, {"edition_id": n["edition_id"]}, session_id="sess-aaaa-0001")
    assert not again["cache"]["hit"]
    assert answer.ask(con, q, {"edition_id": n["edition_id"]}, session_id="sess-bbbb-0002")["status"] == "abstained"
    assert answer.ask(con, q, {}, session_id="sess-aaaa-0001")["status"] == "abstained"       # never part of a wide scope
    assert "મારી નોંધ" not in json.dumps(api.catalog(con), ensure_ascii=False)
    with pytest.raises(api.ApiError):
        api.page(con, n["edition_id"], 1, "sess-bbbb-0002")
    assert api.page(con, n["edition_id"], 1, "sess-aaaa-0001")["page"]["page_number"] == 1
    assert not ingest.delete_personal_notes(con, "sess-bbbb-0002", n["edition_id"])
    assert ingest.delete_personal_notes(con, "sess-aaaa-0001", n["edition_id"])
    assert con.execute("SELECT COUNT(*) FROM text_chunks WHERE edition_id=?", (n["edition_id"],)).fetchone()[0] == 0
    assert answer.ask(con, q, {"edition_id": n["edition_id"]}, session_id="sess-aaaa-0001")["status"] == "abstained"


def test_catalog_exposes_registry_fields_and_roles(con):
    cat = api.catalog(con)
    roles = {b["role"] for b in cat["textbooks"]}
    assert roles == {"textbook", "supplementary"}
    e = cat["textbooks"][0]["editions"][0]
    for f in ("edition_label", "academic_year", "source_url", "owner", "license", "permission_status", "last_verified_at",
              "ingestion_status", "chapters"):
        assert f in e
    assert e["permission_status"] in ("APPROVED", "RESTRICTED", "UNKNOWN", "DENIED")


def test_saved_answers_api(server):
    call, ids = server
    r = call("POST", "/api/ask", {"question": "પરાવર્તન એટલે શું?", "edition_id": ids["granth_vigyan_10_2026"], "session_id": "sess-save-0001"})[1]
    assert call("POST", "/api/saved-answers", {"answer_id": r["answer_id"], "session_id": "sess-other-002"})[0] == 404
    assert call("POST", "/api/saved-answers", {"answer_id": r["answer_id"], "session_id": "sess-save-0001"})[0] == 200
    saved = call("GET", "/api/saved-answers?session=sess-save-0001")[1]["saved"]
    assert len(saved) == 1 and saved[0]["result"]["citations"][0]["page_number"] == 5
    assert call("GET", "/api/saved-answers?session=sess-other-002")[1]["saved"] == []
    assert call("DELETE", f"/api/saved-answers/{r['answer_id']}?session=sess-save-0001")[0] == 200
    assert call("GET", "/api/saved-answers?session=sess-save-0001")[1]["saved"] == []


def test_personal_notes_api_requires_rights_confirmation(server):
    call, _ = server
    body = {"session_id": "sess-note-0001", "title": "નોંધ", "text": "ચુંબકને બે ધ્રુવ હોય છે: ઉત્તર ધ્રુવ અને દક્ષિણ ધ્રુવ."}
    assert call("POST", "/api/personal-notes", body)[0] == 400
    st, out, _h = call("POST", "/api/personal-notes", {**body, "rights_confirmed": True})
    assert st == 200 and out["status"] == "stored"
    assert len(call("GET", "/api/personal-notes?session=sess-note-0001")[1]["notes"]) == 1
    assert call("GET", "/api/personal-notes?session=sess-zzzz-0009")[1]["notes"] == []
    assert call("DELETE", f"/api/personal-notes/{out['edition_id']}?session=sess-zzzz-0009")[0] == 404
    assert call("DELETE", f"/api/personal-notes/{out['edition_id']}?session=sess-note-0001")[0] == 200
