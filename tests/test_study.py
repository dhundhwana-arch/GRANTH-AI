from granth import answer, study
from conftest import SAMPLE

ABSTAIN = "આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી."


def test_find_definitions_patterns():
    f = study.find_definitions
    assert f("પર્ણના કોષોમાં આવેલા લીલા રંગના દ્રવ્યને હરિતદ્રવ્ય કહે છે.") == ["હરિતદ્રવ્ય"]
    assert f("સપાટી પર પડતા કિરણને આપાતકિરણ અને પાછા ફરતા કિરણને પરાવર્તિત કિરણ કહે છે.") == ["આપાતકિરણ", "પરાવર્તિત કિરણ"]
    assert f("લીલી વનસ્પતિ સ્વયંપોષી છે.") == []
    assert f("પ્રાણીઓ અને ફૂગ પરપોષી છે.") == []


# ---- Feature 3: exam preparation ------------------------------------------------------------
def test_exam_formats(con, ids):
    s = {"edition_id": ids["sci"]}
    one = answer.ask(con, "મનુષ્યમાં શ્વસન માટેનું મુખ્ય અંગ કયું છે?", s, mode="one_line", marks=1)
    assert one["answer"]["text"] == "મનુષ્યમાં શ્વસન માટેનું મુખ્ય અંગ ફેફસાં છે."
    d = answer.ask(con, "અવરોધ", s, mode="definition")
    assert "અવરોધ કહે છે" in d["answer"]["text"] and d["mode_label"] == "વ્યાખ્યા"
    p = answer.ask(con, "પરાવર્તનના નિયમો લખો", s, mode="points", marks=3)
    assert p["answer"]["text"].startswith("1. ") and "આપાતકોણ અને પરાવર્તનકોણ" in p["answer"]["text"] and "સમતલ" in p["answer"]["text"]
    diff = answer.ask(con, "જારક શ્વસન અને અજારક શ્વસન વચ્ચેનો તફાવત લખો", s, mode="difference")
    assert diff["answer"]["parts"][0]["kind"] == "table" and diff["citations"][0]["page_number"] == 3
    f = answer.ask(con, "ઓહ્મના નિયમનું સૂત્ર લખો", s, mode="formula")
    assert "સૂત્ર: V = I × R" in f["answer"]["text"] and f["citations"][0]["page_number"] == 7
    for r in (one, d, p, diff, f):
        assert r["verification"]["verified"] and r["citations"][0]["chapter_title"]


def test_requested_length_not_supported_is_flagged_not_padded(con, ids):
    r = answer.ask(con, "કીડીના ડંખમાં કયો ઍસિડ હોય છે?", {"edition_id": ids["sci"]}, mode="detailed", marks=5)
    assert r["status"] == "answered" and r["length_supported"] is False and "ગુણ" in r["note"]
    assert len(r["answer"]["parts"]) < 6
    text = " ".join((SAMPLE / "granth_vigyan_10_2026" / "content.txt").read_text(encoding="utf-8").split())
    assert all(" ".join(p["text"].split()) in text for p in r["answer"]["parts"])


def test_unsupported_exam_questions_are_rejected(con, ids):
    s = {"edition_id": ids["sci"]}
    for q, mode, reason in [("ન્યૂટનનો ગતિનો બીજો નિયમ લખો", "detailed", None),
                            ("શ્વસનનું સૂત્ર લખો", "formula", "formula_not_found"),
                            ("હરિતદ્રવ્ય અને જળચક્ર વચ્ચેનો તફાવત લખો", "difference", None),
                            ("ફેફસાં", "definition", "definition_not_found")]:
        r = answer.ask(con, q, s, mode=mode, marks=3)
        assert r["status"] == "abstained" and r["message"] == ABSTAIN, q
        if reason:
            assert r["reason"] == reason


def test_difference_without_table_uses_both_textbook_definitions(con, ids):
    r = answer.ask(con, "ઍસિડ અને બેઇઝ વચ્ચેનો તફાવત આપો", {"edition_id": ids["sci"]})
    assert r["mode"] == "difference" and len(r["answer"]["parts"]) == 2 and "કોષ્ટક મળ્યું નથી" in r["note"]


def test_practice_questions_come_from_chapter_text_only(con, ids):
    pq = study.practice_questions(con, ids["ch"][1])
    assert "કોઈ દાવો નથી" in pq["disclaimer"]
    types = {q["type"] for q in pq["questions"]}
    assert {"definition", "fill_blank", "short_note", "formula"} <= types
    for q in pq["questions"]:
        assert 1 <= q["page_number"] <= 2
        if q["chunk_id"]:
            chunk = con.execute("SELECT text, chapter_id FROM text_chunks WHERE id=?", (q["chunk_id"],)).fetchone()
            assert chunk["chapter_id"] == ids["ch"][1]
            if q["type"] == "definition":
                assert q["answer"] in chunk["text"]
            if q["type"] == "fill_blank":
                assert q["question"].replace("ખાલી જગ્યા પૂરો: ", "").replace("________", q["answer"]) in chunk["text"]
    assert not any("પરીક્ષામાં પુછાશે" in q["question"] for q in pq["questions"])


def test_revision_is_verbatim(con, ids):
    rev = study.chapter_revision(con, ids["ch"][4])
    assert rev["chapter"]["title"] == "વિદ્યુત" and len(rev["sections"]) == 3
    assert any(f["text"] == "સૂત્ર: V = I × R" for f in rev["formulas"]) and rev["tables"] and rev["examples"]
    for d in rev["definitions"]:
        assert d["text"] in con.execute("SELECT text FROM text_chunks WHERE id=?", (d["chunk_id"],)).fetchone()[0]
    assert study.chapter_revision(con, 99999) is None


# ---- Feature 4: dictionary -------------------------------------------------------------------
def test_dictionary_entries_have_source_and_labels(con, ids):
    words = study.chapter_vocabulary(con, ids["ch"][1])
    kinds = {w["kind"] for w in words}
    assert {"textbook_definition", "textbook_glossary"} <= kinds
    for w in words:
        chunk = con.execute("SELECT text, page_number, chapter_id FROM text_chunks WHERE id=?", (w["chunk_id"],)).fetchone()
        assert chunk["page_number"] == w["page_number"] and chunk["chapter_id"] == ids["ch"][1]
        assert w["origin"] == "textbook" and w["kind_label"] and w["chapter_title"] == "સજીવોમાં પોષણ"
        if w["kind"] == "textbook_definition":
            assert w["explanation"] in chunk["text"]            # definition is the verbatim textbook sentence
        elif w["kind"] == "textbook_glossary":
            assert w["explanation"] in chunk["text"]            # gloss is the book's own glossary line
        else:
            assert w["explanation"] is None                     # no meaning invented


def test_definition_and_simple_explanation_are_separately_labelled(con, ids):
    hits = study.search_vocabulary(con, "હરિતદ્રવ્ય", ids["sci"])
    by = {h["kind"]: h for h in hits}
    assert by["textbook_definition"]["explanation"].endswith("હરિતદ્રવ્ય કહે છે.")
    assert by["textbook_glossary"]["explanation"] == "પાંદડાંને લીલો રંગ આપતું દ્રવ્ય"
    assert by["textbook_definition"]["kind_label"] != by["textbook_glossary"]["kind_label"]


def test_dictionary_search_handles_inflection_and_misses(con, ids):
    assert study.search_vocabulary(con, "હરીતદ્રવ્યનો", ids["sci"])
    assert study.search_vocabulary(con, "જ્વાળામુખી", ids["sci"]) == []
    assert study.search_vocabulary(con, "", ids["sci"]) == []
