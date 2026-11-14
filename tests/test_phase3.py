"""Phase 3 regression tests: the question must be matched to evidence for the concept actually asked about."""
import json
from pathlib import Path

import pytest

from granth import answer, concepts, explain, retrieval

ROOT = Path(__file__).resolve().parent.parent
CONCAVE_DEF = "જે ગોળીય અરીસાની પરાવર્તક સપાટી અંદરની તરફ વળેલી હોય તેને અંતર્ગોળ અરીસો કહે છે."
FOCAL_DEF = "ગોળીય અરીસાના ધ્રુવથી મુખ્ય કેન્દ્ર સુધીના અંતરને કેન્દ્રલંબાઈ કહે છે."


def ask(con, ids, q, book="sci", **kw):
    return answer.ask(con, q, {"edition_id": ids[book]}, use_cache=False, **kw)


def text(r):
    return r["answer"]["text"] if r.get("answer") else ""


def trust(r):
    return r["structured"]["trust"]["status"]


# ---------------------------------------------------------------- 1. the reported wrong answer
@pytest.mark.parametrize("q", [
    "concave mirror નું focal length એટલે શું?",
    "અંતર્ગોળ અરીસાની કેન્દ્રલંબાઈ એટલે શું?",
    "What is the focal length of a concave mirror?",
    "બહિર્ગોળ અરીસાની કેન્દ્રલંબાઈ એટલે શું?",
])
def test_focal_length_question_never_returns_the_mirror_definition(con, ids, q):
    r = ask(con, ids, q)
    assert CONCAVE_DEF not in text(r) and "બહિર્ગોળ અરીસો કહે છે" not in text(r)
    assert r["status"] == "answered" and text(r) == FOCAL_DEF and r["citations"][0]["page_number"] == 6
    # the book defines focal length for spherical mirrors in general, so this is NOT "Verified"
    assert trust(r) == "partial" and r["note"] and "સામાન્ય વ્યાખ્યા" in r["note"]


def test_fully_supported_concept_is_verified(con, ids):
    r = ask(con, ids, "ગોળીય અરીસાની કેન્દ્રલંબાઈ એટલે શું?")
    assert text(r) == FOCAL_DEF and trust(r) == "verified"
    assert text(ask(con, ids, "અંતર્ગોળ અરીસો એટલે શું?")) == CONCAVE_DEF


@pytest.mark.parametrize("q,reason", [
    ("લેન્સની કેન્દ્રલંબાઈ એટલે શું?", None),                       # lens is not in the book
    ("અંતર્ગોળ અરીસાની મોટવણી એટલે શું?", "concept_not_supported"),  # definition does not mention mirrors at all
    ("અરીસો એટલે શું?", "definition_not_found"),                    # only kinds of mirror are defined
    ("નિયમ એટલે શું?", "definition_not_found"),                     # not a request for Ohm's law
    ("ઓહ્મ એટલે શું?", "definition_not_found"),                     # the unit is used, never defined
    ("વોલ્ટમીટર એટલે શું?", "definition_not_found"),
])
def test_related_sentence_is_not_an_answer(con, ids, q, reason):
    r = ask(con, ids, q)
    assert r["status"] == "abstained" and r["message"] == answer.ABSTAIN_MESSAGE and trust(r) == "insufficient"
    if reason:
        assert r["reason"] == reason


def test_general_concept_is_not_replaced_by_a_narrower_one(con, ids):
    r = ask(con, ids, "શ્વસન એટલે શું?")
    assert "પ્રક્રિયાને શ્વસન કહે છે" in text(r) and "જારક" not in text(r)
    assert "જારક શ્વસન કહે છે" in text(ask(con, ids, "જારક શ્વસન કોને કહે છે?"))
    assert "પ્રકાશનું પરાવર્તન કહે છે" in text(ask(con, ids, "પરાવર્તન એટલે શું?"))      # fuller printed name is fine


def test_aspect_questions_unit_use_types(con, ids):
    r = ask(con, ids, "અવરોધનો એકમ શું છે?")
    assert r["status"] == "answered" and "અવરોધનો એકમ ઓહ્મ છે." in text(r) and "તેને અવરોધ કહે છે" not in text(r)
    assert "ઍમ્પિયર" in text(ask(con, ids, "What is the unit of electric current?"))
    assert text(ask(con, ids, "અંતર્ગોળ અરીસાનો ઉપયોગ લખો")) == "દાંતના ડૉક્ટર અંતર્ગોળ અરીસાનો ઉપયોગ કરે છે."
    assert "વાહનોમાં" in text(ask(con, ids, "બહિર્ગોળ અરીસાનો ઉપયોગ જણાવો"))
    for q in ("અવરોધનો ઉપયોગ લખો", "હરિતદ્રવ્યના પ્રકાર જણાવો"):
        r = ask(con, ids, q)
        assert r["status"] == "abstained" and r["reason"] == "aspect_not_found"


def test_new_numbers_are_never_answered_from_a_similar_example(con, ids):
    r = ask(con, ids, "5 ઓહ્મ અવરોધમાંથી 3 ઍમ્પિયર પ્રવાહ વહે તો વોલ્ટેજ કેટલું થાય?")
    assert r["status"] == "abstained" and r["reason"] == "numbers_not_in_source"


def test_match_definition_rules():
    md = concepts.match_definition
    assert md(["કેન્દ્રલંબાઇ"], [], "કેન્દ્રલંબાઈ", "x")["kind"] == "exact"
    a = concepts.analyse("અંતર્ગોળ અરીસાની કેન્દ્રલંબાઈ")
    assert a["head"] == ["કેન્દ્રલંબાઇ"] and len(a["modifiers"]) == 2
    assert md(a["terms"], a["modifiers"], "અંતર્ગોળ અરીસો", CONCAVE_DEF) is None
    m = md(a["terms"], a["modifiers"], "કેન્દ્રલંબાઈ", FOCAL_DEF)
    assert m["kind"] == "head_only" and len(m["missing"]) == 1
    assert concepts.analyse("છોડ પોતાનો ખોરાક")["modifiers"] == []            # "પોતાનો" is not a genitive


# ---------------------------------------------------------------- 2. paraphrase, synonyms, spelling
@pytest.mark.parametrize("q,must,page", [
    ("છોડ પોતાનો ખોરાક કેવી રીતે બનાવે છે?", "પ્રકાશસંશ્લેષણ", 1),
    ("How do plants make their food?", "પ્રકાશસંશ્લેષણ", 1),
    ("ઓમનો નિયમ", "ઓહ્મનો નિયમ કહે છે", 7),
    ("પરાવતન", "પરાવર્તન કહે છે", 5),
    ("પાંદડાં લીલાં કેમ દેખાય છે?", "હરિતદ્રવ્યને કારણે", 2),
])
def test_paraphrase_and_spelling_find_the_evidence(con, ids, q, must, page):
    r = ask(con, ids, q)
    assert r["status"] == "answered" and must in text(r)
    assert page in [c["page_number"] for c in r["citations"]]
    assert all(p["text"] in (ROOT / "data/sample/granth_vigyan_10_2026/content.txt").read_text(encoding="utf-8")
               for p in r["answer"]["parts"])


@pytest.mark.parametrize("q", ["છોડ પોતાનો ખોરાક કેવી રીતે બનાવે છે?", "ઓમનો નિયમ", "પરાવતન"])
def test_assumed_word_is_never_verified(con, ids, q):
    r = ask(con, ids, q)
    assert trust(r) == "partial"
    assert any("ધારીને શોધ્યું" in x for x in r["structured"]["trust"]["reasons"])


def test_pure_spelling_variant_stays_verified_with_a_note(con, ids):
    assert trust(ask(con, ids, "તટસ્થિકરણ એટલે શું?")) == "verified"          # vowel length is folded before matching
    r = ask(con, ids, "ઓહમનો નિયમ લખો")                                     # missing virama
    assert "ઓહ્મનો નિયમ કહે છે" in text(r)
    assert trust(r) == "verified" and any("જોડણી" in n for n in r["structured"]["notes"])


def test_expansion_never_supplies_answer_text_or_accepts_weak_matches(con, ids):
    data = json.loads((ROOT / "data/glossary/gu_synonyms.json").read_text(encoding="utf-8"))
    # a concept alias whose term the book does not contain cannot produce an answer
    r = ask(con, ids, "વસ્તુ નીચે કેમ પડે છે?")
    assert r["status"] == "abstained"
    assert any(c["term"] == "ગુરુત્વાકર્ષણ" for c in data["concepts"])
    # ambiguous near-miss: two words equally close -> not accepted
    idx = retrieval.get_index(con)
    assert idx._fuzzy("ક્ષ", idx.scope([ids["sci"]])) is None
    # vocabulary is scoped: a word that exists only in the other book is not offered
    terms = idx.resolve_terms("જળચક્ર", [ids["sci"]])
    assert terms[0]["term"] is None
    assert idx.resolve_terms("જળચક્ર", [ids["soc"]])[0]["match"] == "exact"


# ---------------------------------------------------------------- 3. editions
def test_edition_conflict_on_paraphrase_keeps_evidence_separate(con, ids):
    scope = {"standard": 10, "subject": "વિજ્ઞાન"}
    r = answer.ask(con, "ઘરમાં આવતી વીજળીનું વોલ્ટેજ કેટલું ગણવામાં આવ્યું છે?", scope, use_cache=False)
    assert r["status"] == "edition_conflict" and r["answer"] is None
    by = {e["edition_id"]: e for e in r["editions"]}
    assert "220 વોલ્ટ" in by[ids["sci"]]["answer"]["text"] and "230" not in by[ids["sci"]]["answer"]["text"]
    assert "230 વોલ્ટ" in by[ids["sci27"]]["answer"]["text"] and "220" not in by[ids["sci27"]]["answer"]["text"]
    for eid, e in by.items():
        assert e["evidence"] and all(ev["edition_id"] == eid for ev in e["evidence"])
        assert all(c["edition_id"] == eid for c in e["citations"])
    assert r["structured"]["trust"]["status"] == "partial"


def test_missing_evidence_is_named_per_edition(con, ids):
    scope = {"standard": 10, "subject": "વિજ્ઞાન"}
    r = answer.ask(con, "પ્રકાશસંશ્લેષણ એટલે શું?", scope, use_cache=False)
    assert r["status"] == "answered" and all(e["edition_id"] == ids["sci"] for e in r["evidence"])
    per = {e["edition_id"]: e for e in r["edition_results"]}
    assert per[ids["sci"]]["status"] == "answered" and per[ids["sci27"]]["status"] == "abstained"
    assert per[ids["sci27"]]["answer"] is None and per[ids["sci27"]]["message"]
    assert r["editions_missing_evidence"] and r["editions_missing_evidence"][0] in r["edition_note"]
    none = answer.ask(con, "ભૂકંપ એટલે શું?", scope, use_cache=False)
    assert none["status"] == "abstained" and len(none["edition_results"]) == 2
    assert all(e["status"] == "abstained" for e in none["edition_results"])
    one = answer.ask(con, "ઘરવપરાશના વિદ્યુતપુરવઠાનું વોલ્ટેજ કેટલું છે?", {"edition_id": ids["sci27"]}, use_cache=False)
    assert "230" in text(one) and "220" not in text(one) and "edition_results" not in one


# ---------------------------------------------------------------- 4. simple explanation
def test_explanation_is_separate_traceable_and_adds_no_fact(con, ids):
    r = ask(con, ids, "પ્રકાશસંશ્લેષણ એટલે શું?")
    ex = r["structured"]["explanation"]
    assert ex["available"] and "અવતરણ નથી" in ex["label_gu"]
    quote = text(r)
    assert all(p["source_type"] == "quotation" for p in r["answer"]["parts"])          # the quotation itself is untouched
    for ln in ex["lines"]:
        assert ln["evidence"][0]["quote"] in quote and ln["evidence"][0]["page_number"] == 1
        assert all(piece in ln["evidence"][0]["quote"] for piece in ln["pieces"])
    assert explain.verify([{**ln} for ln in ex["lines"]], quote)
    assert len(ex["lines"]) == 2 and ex["lines"][0]["text"].startswith("પહેલાં આ વાત સમજો")
    assert any(w["everyday"] == "છોડ-ઝાડ" and w["source_type"] == "word_list" for w in ex["everyday_words"])
    corpus = (ROOT / "data/sample/granth_vigyan_10_2026/content.txt").read_text(encoding="utf-8")
    assert ex["terms"] and all(t["meaning"] in corpus and t["page_number"] for t in ex["terms"])


def test_explanation_definition_question_form_and_fallback(con, ids):
    ex = ask(con, ids, "અંતર્ગોળ અરીસો એટલે શું?")["structured"]["explanation"]
    assert ex["lines"][0]["text"] == "‘અંતર્ગોળ અરીસો’ એ એક નામ (પારિભાષિક શબ્દ) છે."
    assert ex["lines"][1]["text"].startswith("કોને ‘અંતર્ગોળ અરીસો’ કહે છે? — જે ગોળીય અરીસાની")
    # tampering is detected: an added fact or a dropped word fails verification
    src = CONCAVE_DEF
    good = explain._restate(src)
    assert explain.verify(good, src)
    bad = [{**good[0]}, {**good[1], "text": good[1]["text"] + " તે કાચનો બનેલો હોય છે."}]
    assert not explain.verify(bad, src)
    assert not explain.verify(good[:1], src)
    assert not explain.verify([{**good[0], "pieces": ["બહિર્ગોળ"]}], src)
    # nothing safe to do -> no explanation, the verified passage stands alone
    r = ask(con, ids, "વિદ્યુતપાવરનો એકમ કયો છે?")
    ex = r["structured"]["explanation"]
    if not ex["available"]:
        assert ex["lines"] == [] and ex["fallback_gu"]
    f = ask(con, ids, "અરીસાનું સૂત્ર લખો")["structured"]["explanation"]
    assert f["available"] is False and f["lines"] == []


def test_examples_in_explanation_are_only_printed_examples(con, ids):
    r = ask(con, ids, "ગોળીય અરીસાની કેન્દ્રલંબાઈ એટલે શું?")
    ex = r["structured"]["explanation"]
    corpus = (ROOT / "data/sample/granth_vigyan_10_2026/content.txt").read_text(encoding="utf-8")
    assert all(e["text"] in corpus and e["source_type"] == "textbook_example" for e in ex["examples"])


# ---------------------------------------------------------------- found by the held-out benchmark (first run)
def test_use_question_is_not_answered_by_the_definition_of_the_subject(con, ids):
    r = ask(con, ids, "અંતર્ગોળ અરીસો ક્યાં વપરાય છે?")
    assert r["status"] == "answered" and "દાંતના ડૉક્ટર" in text(r)
    assert CONCAVE_DEF not in text(r) and "વાહનોમાં" not in text(r)
    r = ask(con, ids, "વિદ્યુતપ્રવાહ માપવા માટે કયું સાધન વપરાય છે?")
    assert "ઍમિટર" in text(r)


def test_named_formula_question_leads_with_the_sentence_that_names_it(con, ids):
    r = ask(con, ids, "અરીસાનું સૂત્ર એટલે શું?")
    assert "અરીસાનું સૂત્ર કહે છે" in text(r) and "1/f = 1/v + 1/u" in text(r)
    assert FOCAL_DEF not in text(r)


def test_bare_topic_in_several_chapters_asks_which_one(con, ids):
    r = ask(con, ids, "કાર્બન ડાયૉક્સાઇડ")
    assert r["status"] == "abstained" and r["reason"] == "ambiguous_question" and r["suggestions"]


def test_either_or_question_shows_only_the_sentence_that_decides_it(con, ids):
    """Held-out set 2, G11 (wrong until Phase 4): the soil / pH sentences share the words but do not decide the question."""
    r = ask(con, ids, "ચૂનાનું પાણી ઍસિડિક છે કે બેઇઝિક?")
    assert text(r) == "સાબુનું દ્રાવણ અને ચૂનાનું પાણી બેઇઝિક હોય છે."
