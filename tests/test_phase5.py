"""Phase 5: negation / polarity, unknown and look-alike words, false premises, Gujarati paraphrases, edition conflict,
safe explanations. Tests use the self-written demo books only (synthetic corpus, not a real textbook)."""
import pytest

from granth import answer, explain, polarity, retrieval

AEROBIC = "ઑક્સિજનની હાજરીમાં થતા શ્વસનને જારક શ્વસન કહે છે."
ANAEROBIC = "ઑક્સિજનની ગેરહાજરીમાં થતા શ્વસનને અજારક શ્વસન કહે છે."
REFUSAL = "આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી."


def ask(con, ids, q, book="sci", **kw):
    return answer.ask(con, q, {"edition_id": ids[book]}, use_cache=False, **kw)


def sentences(r):
    return [p["text"] for p in r["answer"]["parts"]] if r.get("answer") and r["status"] == "answered" else []


def trust(r):
    return r["structured"]["trust"]["status"]


# ---------------------------------------------------------------- 1. negation / polarity
@pytest.mark.parametrize("q", [
    "ઑક્સિજન ન હોય ત્યારે થતા શ્વસનને શું કહે છે?",          # negation after the noun
    "ઑક્સિજન વગર થતા શ્વસનને શું કહે છે?",                  # postposition
    "ઑક્સિજન વિના થતા શ્વસનને શું કહે છે?",
    "જે શ્વસનમાં ઑક્સિજન નથી હોતો તેને શું કહે છે?",        # negation in a relative clause
    "ઑક્સિજનની ગેરહાજરીમાં થતા શ્વસનને શું કહે છે?",        # the book's own wording
    "What is respiration without oxygen called?",
    "What is respiration in the absence of oxygen called?",
])
def test_negated_question_gets_the_negated_fact(con, ids, q):
    r = ask(con, ids, q)
    assert sentences(r) == [ANAEROBIC], (q, r.get("reason"))


@pytest.mark.parametrize("q", [
    "ઑક્સિજનની હાજરીમાં થતા શ્વસનને શું કહે છે?",
    "ઑક્સિજન હોય ત્યારે થતા શ્વસનને શું કહે છે?",
    "What is respiration in the presence of oxygen called?",
])
def test_positive_question_never_gets_the_negated_fact(con, ids, q):
    r = ask(con, ids, q)
    assert ANAEROBIC not in sentences(r)
    if r["status"] == "answered":
        assert sentences(r) == [AEROBIC]


def test_polarity_detection_reads_function_words():
    assert polarity.negated("ઑક્સિજન ન હોય ત્યારે થતા શ્વસનને શું કહે છે?")
    assert polarity.negated(ANAEROBIC) and not polarity.negated(AEROBIC)
    q = polarity.negated("ઑક્સિજન વગર થતા શ્વસનને શું કહે છે?")
    assert polarity.conflict("ઑક્સિજન વગર થતા શ્વસનને શું કહે છે?", AEROBIC, set(q)) is not None
    assert polarity.conflict("ઑક્સિજન વગર થતા શ્વસનને શું કહે છે?", ANAEROBIC, set(q)) is None


def test_negation_of_a_thing_the_book_never_negates_is_refused(con, ids):
    r = ask(con, ids, "સૂર્યપ્રકાશ વગર થતા શ્વસનને શું કહે છે?")
    assert r["status"] == "abstained" and r["message"] == REFUSAL and r["answer"] is None


def test_polarity_conflict_is_never_verified(con, ids):
    for q in ["ઑક્સિજન ન હોય ત્યારે થતા શ્વસનને શું કહે છે?", "હરિતદ્રવ્ય વગર પ્રકાશસંશ્લેષણ થાય છે?",
              "પાણી વગર પ્રકાશસંશ્લેષણ કેવી રીતે થાય છે?"]:
        r = ask(con, ids, q)
        if r["status"] != "answered" or trust(r) != "verified":
            continue
        asked = set(polarity.negated(q))
        for s in sentences(r):
            assert polarity.conflict(q, s, asked) is None, (q, s)


# ---------------------------------------------------------------- 2. unknown / look-alike words
def test_look_alike_technical_word_is_not_substituted(con, ids):
    r = ask(con, ids, "વૉટમીટર શું માપે છે?")                      # the book only has વોલ્ટમીટર
    assert r["status"] == "abstained" and r["message"] == REFUSAL and r["answer"] is None
    assert "વૉટમીટર" in r["unknown_terms"]
    assert all(m["book_word"] != "વોલ્ટમીટર" or m["asked"] != "વૉટમીટર" for m in r["term_matches"])
    r = ask(con, ids, "wattmeter શું માપે છે?")
    assert r["status"] == "abstained"


def test_did_you_mean_is_a_suggestion_not_an_answer(con, ids):
    r = ask(con, ids, "વૉટમીટર શું માપે છે?")
    for m in r["did_you_mean"]:
        assert m["asked"] and m["book_word"]
    assert sentences(r) == []


@pytest.mark.parametrize("q,book_word", [
    ("વિધુતપ્રવાહનો એકમ કયો છે?", "વિદ્યુતપ્રવાહ"),             # a real misspelling
    ("હરીતદ્રવ્ય એટલે શું?", "હરિતદ્રવ્ય"),                    # ઇ/ઈ spelling variant
    ("પ્રકાશસંશ્લેશણ એટલે શું?", "પ્રકાશસંશ્લેષણ"),             # શ/ષ
])
def test_spelling_variant_is_matched_and_displayed(con, ids, q, book_word):
    r = ask(con, ids, q)
    assert r["status"] == "answered", r.get("reason")
    assert any(book_word in s for s in sentences(r))
    shown = [m for m in r["term_matches"] if book_word.startswith(m["book_word"][:6])]
    if shown and not shown[0]["normalisation"]:
        assert trust(r) != "verified"                           # a guessed spelling is never "Verified"


@pytest.mark.parametrize("q", ["ઝેનોમીટર શું માપે છે?", "ક્વાર્ટોફિલ એટલે શું?", "ફ્લક્સોમીટર કયા એકમમાં માપે છે?",
                               "What does a zenometer measure?"])
def test_invented_term_is_refused(con, ids, q):
    r = ask(con, ids, q)
    assert r["status"] == "abstained" and r["message"] == REFUSAL and r["answer"] is None


def test_transliteration_and_genuine_synonym_still_work(con, ids):
    assert any("વોલ્ટમીટર" in s for s in sentences(ask(con, ids, "voltmeter શું માપે છે?")))
    r = ask(con, ids, "વીજપ્રવાહ શેનાથી મપાય છે?")
    assert sentences(r) == ["વિદ્યુતપ્રવાહ માપવા માટે ઍમિટર વપરાય છે."]
    assert trust(r) == "partial"                                # synonym: shown, but the student is told to check
    assert any(m["kind"] == "synonym" for m in r["term_matches"])


def test_spelling_confidence_separates_typos_from_other_words():
    sc = retrieval.spelling_confidence
    assert sc("વિધુતપ્રવાહ", "વિદ્યુતપ્રવાહ") >= retrieval.FUZZY_MIN_CONFIDENCE
    assert sc("વૉટમીટર", "વોલ્ટમીટર") < retrieval.FUZZY_MIN_CONFIDENCE
    assert sc("સ્ટાર્ટ", "સ્ટાર્ચ") < retrieval.FUZZY_MIN_CONFIDENCE


# ---------------------------------------------------------------- 3. false premise
@pytest.mark.parametrize("q", [
    "ઍમિટર વિદ્યુતસ્થિતિમાનનો તફાવત કેમ માપે છે?",
    "Why does an ammeter measure potential difference?",
])
def test_false_premise_is_refused_and_book_sentence_is_only_shown_as_context(con, ids, q):
    r = ask(con, ids, q)
    assert r["status"] == "abstained" and r["reason"] == "premise_not_supported"
    assert r["message"] == REFUSAL and r["answer"] is None
    p = r["premise"]
    assert p["status"] == "not_found_in_book" and "ઉત્તર નથી" in p["label_gu"]
    for b in p["book_says"]:                                    # context is quoted, cited, never invented
        row = con.execute("SELECT text, page_number FROM text_chunks WHERE id=?", (b["chunk_id"],)).fetchone()
        assert b["text"] in row["text"] and b["page_number"] == row["page_number"]


def test_true_premise_is_still_answered(con, ids):
    r = ask(con, ids, "વિદ્યુતપ્રવાહ માપવા માટે કયું સાધન વપરાય છે?")
    assert sentences(r) == ["વિદ્યુતપ્રવાહ માપવા માટે ઍમિટર વપરાય છે."] and not r.get("premise")


# ---------------------------------------------------------------- 4. Gujarati paraphrases
@pytest.mark.parametrize("group", [
    ["હરિતદ્રવ્ય ક્યાં હોય છે?", "હરિતદ્રવ્ય ક્યાં જોવા મળે છે?", "હરિતદ્રવ્ય ક્યાં મળે છે?", "chlorophyll ક્યાં હોય છે?"],
    ["વિદ્યુતપ્રવાહ માપવા માટે કયું સાધન વપરાય છે?", "વિદ્યુતપ્રવાહ શેનાથી મપાય છે?", "વિદ્યુતપ્રવાહ શેના વડે માપવામાં આવે છે?"],
    ["પ્રકાશસંશ્લેષણ એટલે શું?", "પ્રકાશસંશ્લેષણની વ્યાખ્યા આપો.", "પ્રકાશસંશ્લેષણ કોને કહે છે?"],
    ["વનસ્પતિ પાણી શેના વડે શોષે છે?", "વનસ્પતિ પાણીનું શોષણ શેના દ્વારા કરે છે?"],
])
def test_paraphrases_reach_the_same_lead_sentence(con, ids, group):
    leads = set()
    for q in group:
        r = ask(con, ids, q)
        assert r["status"] == "answered", (q, r.get("reason"))
        leads.add(sentences(r)[0])
    assert len(leads) == 1, leads


def test_type_question_is_not_answered_with_an_unrelated_fact(con, ids):
    for q in ["હરિતદ્રવ્યના પ્રકાર જણાવો.", "વિદ્યુતપ્રવાહના પ્રકાર કયા છે?", "અંતર્ગોળ અરીસાની મોટવણી એટલે શું?"]:
        assert ask(con, ids, q)["status"] == "abstained", q


# ---------------------------------------------------------------- 5. edition conflict (two synthetic demo editions)
@pytest.mark.parametrize("q", [
    "ઘરવપરાશના વિદ્યુતપુરવઠાનું વોલ્ટેજ કેટલું છે?",
    "ઘરવપરાશની વીજળી કેટલા વોલ્ટની હોય છે?",
    "વોલ્ટેજ કેટલું છે ઘરવપરાશના વિદ્યુતપુરવઠાનું?",
    "What is the voltage of the household supply?",
    "household supply નું voltage કેટલું છે?",
])
def test_edition_conflict_shows_both_values_with_citations(con, ids, q):
    tb = con.execute("SELECT textbook_id FROM textbook_editions WHERE id=?", (ids["sci"],)).fetchone()[0]
    r = answer.ask(con, q, {"textbook_id": tb}, use_cache=False)
    assert r["status"] == "edition_conflict", (q, r["status"], r.get("reason"))
    per = {e["edition_id"]: e for e in r["editions"]}
    assert len(per) == 2
    texts = [e["answer"]["text"] for e in per.values()]
    assert any("220" in t for t in texts) and any("230" in t for t in texts)
    for e in per.values():
        assert e["citations"] and e["citations"][0]["edition_id"] == e["edition_id"] and e["citations"][0]["page_number"]
    assert r.get("structured", {}).get("trust", {}).get("status") != "verified"


# ---------------------------------------------------------------- 6. safe explanations
@pytest.mark.parametrize("q", ["હરિતદ્રવ્ય એટલે શું?", "વિદ્યુતપ્રવાહનો એકમ કયો છે?", "તટસ્થ દ્રાવણનું pH મૂલ્ય કેટલું હોય છે?",
                               "અંતર્ગોળ અરીસો એટલે શું?", "પર્ણરંધ્રનું કાર્ય શું છે?"])
def test_explanation_adds_only_brackets_and_keeps_numbers(con, ids, q):
    r = ask(con, ids, q)
    assert r["status"] == "answered"
    ex = r["structured"]["explanation"]
    src = " ".join(sentences(r))
    assert all(p["source_type"] == "quotation" for p in r["answer"]["parts"])       # the evidence itself is untouched
    for ln in ex["lines"]:
        assert all(piece in src for piece in ln["pieces"])
        assert ln["evidence"][0]["page_number"]
    if ex["lines"]:
        plain = " ".join(explain._GLOSS.sub("", ln["text"]) for ln in ex["lines"])
        assert explain._digits(plain) == explain._digits(src)
        assert explain.verify(ex["lines"], src)
    for t in ex["english_terms"]:
        assert t["source_type"] == "word_list"
    if ex["english_terms"]:
        assert "પુસ્તકનું લખાણ નથી" in ex["english_label_gu"]


def test_explanation_verify_rejects_a_changed_number_or_added_fact():
    src = "તટસ્થ દ્રાવણનું pH મૂલ્ય 7 હોય છે."
    same = [{"kind": "same", "text": "તટસ્થ (neutral) દ્રાવણનું (solution) pH મૂલ્ય 7 હોય છે.", "pieces": [src]}]
    assert explain.verify(same, src)
    assert not explain.verify([{**same[0], "text": same[0]["text"].replace("7", "8")}], src)
    assert not explain.verify([{**same[0], "text": same[0]["text"] + " તે પીવાલાયક હોય છે."}], src)
