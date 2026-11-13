from granth import gujarati as g


def test_normalize_is_display_safe_and_nfc():
    assert g.normalize_text("  પ્રકાશ\u200d  સંશ્લેષણ \n\n x ") == "પ્રકાશ સંશ્લેષણ\n\nx"


def test_fold_spelling_variants_match():
    assert g.fold("ઍસિડ") == g.fold("એસિડ")
    assert g.fold("હરીતદ્રવ્ય") == g.fold("હરિતદ્રવ્ય")
    assert g.fold("૧૨૩") == "123"
    assert g.search_key("પ્રકાશસંશ્લેષણ  એટલે શું ?") == g.search_key("પ્રકાશસંશ્લેષણ એટલે શું")


def test_stemmer_conflates_case_forms():
    forms = ["પર્ણોમાં", "પર્ણની", "પર્ણનો", "પર્ણ"]
    assert len({g.content_terms(f)[0] for f in forms}) == 1
    assert g.content_terms("અરીસો")[0] == g.content_terms("અરીસાનું")[0]


def test_stopwords_removed():
    assert g.content_terms("પ્રકાશસંશ્લેષણ એટલે શું?") == ["પ્રકાશસંશ્લેષણ"]


def test_sentence_split_keeps_decimals_and_formula_dots():
    s = g.split_sentences("pH માપક્રમ 0 થી 14 સુધીનો હોય છે. મૂલ્ય 7.5 હોય છે. અંત?")
    assert s == ["pH માપક્રમ 0 થી 14 સુધીનો હોય છે.", "મૂલ્ય 7.5 હોય છે.", "અંત?"]


def test_integrity_validation_rejects_broken_text_layer():
    broken = "àકાશસંƅેષણ એ એવી à Ìɱ યા છે જેમાં લીલી વન¥પત"      # real output of a PDF text layer (see OCR report)
    good = "પ્રકાશસંશ્લેષણ એ એવી પ્રક્રિયા છે. સૂત્ર: V = I × R"
    assert g.validate_gujarati(broken)["passed"] is False
    assert g.validate_gujarati(good)["passed"] is True
    assert g.validate_gujarati("")["passed"] is False
    assert g.validate_gujarati("only english text here")["passed"] is False


def test_cer():
    assert g.cer("વિજ્ઞાન", "વિજ્ઞાન") == 0
    assert 0 < g.cer("વિજ્ઞાન", "વિજ્ઞાત") < 0.2
    assert g.cer("", "") == 0
