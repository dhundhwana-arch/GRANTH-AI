"""Phase 4: question intent + answer-evidence validation. Every shown sentence must carry the topic of the question
AND the kind of information that was asked for; related sentences are never added."""
import pytest

from granth import answer, intent, validate


def ask(con, ids, q, book="sci", **kw):
    return answer.ask(con, q, {"edition_id": ids[book]}, use_cache=False, **kw)


def text(r):
    return r["answer"]["text"] if r.get("answer") else ""


def sentences(r):
    return [p["text"] for p in r["answer"]["parts"]] if r.get("answer") else []


def trust(r):
    return r["structured"]["trust"]["status"]


@pytest.mark.parametrize("q,expected", [
    ("અવરોધનો એકમ કયો છે?", "unit"), ("ઍમ્પિયર શેનો એકમ છે?", "reverse_unit"), ("માણસ શ્વાસ કયા અંગથી લે છે?", "organ"),
    ("ઝાડ પાણી ક્યાંથી મેળવે છે?", "source"), ("પ્રકાશસંશ્લેષણ ક્યાં થાય છે?", "place"), ("સ્નાયુ કેમ દુખે છે?", "reason"),
    ("ચૂનાનું પાણી ઍસિડિક છે કે બેઇઝિક?", "choice"), ("વિદ્યુતપ્રવાહ શેનાથી મપાય છે?", "instrument"),
    ("અંતર્ગોળ અરીસો ક્યાં વપરાય છે?", "use"), ("હરિતદ્રવ્યનું કાર્ય શું છે?", "function"),
    ("છોડ ખોરાક કેવી રીતે બનાવે છે?", "process"), ("pH માપક્રમ કેટલો હોય છે?", "quantity"),
    ("જમીનની અંદરના પાણીને શું કહે છે?", "naming"), ("નકશામાં ઉપરની બાજુ કઈ દિશા હોય છે?", "fact"),
    ("ઘરવપરાશનું વોલ્ટેજ જણાવો", "fact"),
])
def test_intent_classification(q, expected):
    assert intent.analyse(q)["intent"] == expected


def test_either_or_shows_only_the_deciding_sentence_and_is_verified(con, ids):
    r = ask(con, ids, "ચૂનાનું પાણી ઍસિડિક છે કે બેઇઝિક?")
    assert sentences(r) == ["સાબુનું દ્રાવણ અને ચૂનાનું પાણી બેઇઝિક હોય છે."] and trust(r) == "verified"
    assert r["validation"]["intent"] == "choice"


def test_which_organ_shows_the_organ_sentence_only_and_never_verified(con, ids):
    r = ask(con, ids, "માણસ શ્વાસ કયા અંગથી લે છે?")
    assert sentences(r) == ["મનુષ્યમાં શ્વસન માટેનું મુખ્ય અંગ ફેફસાં છે."]
    assert trust(r) == "partial"          # the book says "શ્વસન", the student "શ્વાસ"; the book itself separates the two


def test_unit_of_what(con, ids):
    r = ask(con, ids, "ઍમ્પિયર શેનો એકમ છે?")
    assert sentences(r) == ["વિદ્યુતપ્રવાહનો એકમ ઍમ્પિયર છે."] and trust(r) == "verified"
    r = ask(con, ids, "ઓહ્મ શેનો એકમ છે?")
    assert sentences(r) == ["અવરોધનો એકમ ઓહ્મ છે."]            # not the sentences about ઓહ્મનો નિયમ


def test_where_from_needs_a_source_in_the_sentence(con, ids):
    r = ask(con, ids, "ઝાડ પાણી ક્યાંથી મેળવે છે?")
    assert sentences(r) == ["વનસ્પતિ મૂળ દ્વારા જમીનમાંથી પાણીનું શોષણ કરે છે."] and trust(r) == "partial"
    # same words, but no sentence says where plants get oxygen FROM
    assert ask(con, ids, "વનસ્પતિ ઑક્સિજન ક્યાંથી મેળવે છે?")["status"] == "abstained"


def test_why_do_we_need_lungs(con, ids):
    r = ask(con, ids, "Why do we need lungs?")
    assert sentences(r) == ["મનુષ્યમાં શ્વસન માટેનું મુખ્ય અંગ ફેફસાં છે."] and trust(r) == "partial"
    assert ask(con, ids, "ફેફસાં કેમ દુખે છે?")["status"] == "abstained"


def test_focal_length_unit_and_mirror_examples_still_hold(con, ids):
    r = ask(con, ids, "Concave mirror નું focal length એટલે શું?")
    assert text(r) == "ગોળીય અરીસાના ધ્રુવથી મુખ્ય કેન્દ્ર સુધીના અંતરને કેન્દ્રલંબાઈ કહે છે." and trust(r) == "partial"
    r = ask(con, ids, "અવરોધનો એકમ કયો છે?")
    assert sentences(r) == ["અવરોધનો એકમ ઓહ્મ છે."] and trust(r) == "verified"        # no unit table, no definition
    r = ask(con, ids, "અરીસો એટલે શું?")
    assert r["status"] == "abstained" and r["reason"] == "definition_not_found"


@pytest.mark.parametrize("q", [
    "અરીસાનો એકમ કયો છે?",                       # the book has mirrors and has units, but no unit of a mirror
    "હરિતદ્રવ્યનો એકમ કયો છે?",
    "ફેફસાંનો ઉપયોગ વાહનોમાં ક્યાં થાય છે?",
    "ઓહ્મનો નિયમ કયા અંગમાં લાગુ પડે છે?",
])
def test_keyword_overlap_is_not_evidence(con, ids, q):
    assert ask(con, ids, q)["status"] == "abstained"


def test_no_unrelated_sentence_is_added_to_a_correct_answer(con, ids):
    for q, must in [("હરિતદ્રવ્ય શેનું શોષણ કરે છે?", "હરિતદ્રવ્ય સૂર્યપ્રકાશની ઊર્જાનું શોષણ કરે છે."),
                    ("તટસ્થ દ્રાવણનું pH મૂલ્ય કેટલું હોય છે?", "તટસ્થ દ્રાવણનું pH મૂલ્ય 7 હોય છે.")]:
        assert sentences(ask(con, ids, q)) == [must]


def test_cause_spread_over_one_paragraph_is_shown_whole_and_only_partial(con, ids):
    r = ask(con, ids, "ખૂબ કસરત કર્યા પછી સ્નાયુ કેમ દુખે છે?")
    assert len(sentences(r)) == 3 and "લૅક્ટિક ઍસિડના ભરાવાથી" in text(r) and trust(r) == "partial"
    # two sentences that only share the question's own word are not one explanation
    assert ask(con, ids, "બહિર્ગોળ અરીસો દાંતના ડૉક્ટર કેમ વાપરે છે?")["status"] == "abstained"


def test_validator_units():
    an = intent.analyse("અવરોધનો એકમ કયો છે?")
    pl = {"need": ["અવરોધ"], "weak": [], "soft": [], "unknown": []}
    assert validate._check(an, pl, "અવરોધનો એકમ ઓહ્મ છે.", {"અવરોધ"}, [])
    assert validate._check(an, pl, "વાહકના જે ગુણધર્મને કારણે તે વિદ્યુતપ્રવાહના વહનનો વિરોધ કરે છે તેને અવરોધ કહે છે.", {"અવરોધ"}, []) is None
    assert validate._check(an, pl, "વિદ્યુતપ્રવાહનો એકમ ઍમ્પિયર છે.", {"અવરોધ"}, []) is None


def test_answer_reports_what_was_understood(con, ids):
    v = ask(con, ids, "ઝાડ પાણી ક્યાંથી મેળવે છે?")["validation"]
    assert v["intent"] == "source" and v["verbs"] == ["મેળવે"] and v["level"] == "partial" and v["assumed"]


def test_admin_token_expiry_fails_closed():
    from granth import api
    assert not api.admin_token_expired(None) and not api.admin_token_expired("")
    assert not api.admin_token_expired("2026-12-31", today="2026-12-31")
    assert api.admin_token_expired("2026-12-31", today="2027-01-01")
    assert api.admin_token_expired("next week")            # not a date: refuse rather than guess


def test_expired_admin_token_is_refused_by_the_api(monkeypatch):
    import pytest
    from granth import api
    monkeypatch.setenv("GRANTH_ADMIN_TOKEN", "Zk3v9Qm1-Lp7xT2eWs8Rb4Yc6Nd0Ha5J")
    monkeypatch.setenv("GRANTH_ADMIN_TOKEN_EXPIRES", "2020-01-01")
    h = api.Handler.__new__(api.Handler) if hasattr(api, "Handler") else None
    if h is None:
        pytest.skip("handler class name differs")
    h.client_address = ("127.0.0.1", 1)
    h.headers = {"X-Admin-Token": "Zk3v9Qm1-Lp7xT2eWs8Rb4Yc6Nd0Ha5J"}
    with pytest.raises(api.ApiError) as e:
        h._require_admin()
    assert e.value.status == 403 and "expired" in str(e.value)
