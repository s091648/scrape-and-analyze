from src.modules.search.domain.services.tokenizer import tokenize, MIN_TERM_LENGTH


def test_tokenize_splits_english_on_non_alphanumeric_and_lowercases():
    terms = tokenize("Machine-Learning, and Deep Learning!")
    assert "machine" in terms
    assert "learning" in terms
    assert "deep" in terms


def test_tokenize_filters_terms_shorter_than_min_length():
    terms = tokenize("a an is it of ok")
    assert all(len(t) >= MIN_TERM_LENGTH for t in terms)


def test_tokenize_filters_english_stopwords():
    terms = tokenize("the quick brown fox")
    assert "the" not in terms
    assert "quick" in terms
    assert "brown" in terms
    assert "fox" in terms


def test_tokenize_dedupes_within_one_call():
    terms = tokenize("learning learning learning")
    assert terms == {"learning"}


def test_tokenize_segments_chinese_via_jieba_not_naive_split():
    terms = tokenize("機器學習的應用")
    # A naive char-by-char or whitespace split would never produce "機器學習" as one term.
    assert "機器學習" in terms or "機器" in terms  # jieba's exact boundary may vary by dict version
    assert "的" not in terms  # single-char stopword, filtered by MIN_TERM_LENGTH alone


def test_tokenize_filters_chinese_multichar_stopwords():
    terms = tokenize("這個方法可以解決問題")
    assert "這個" not in terms
    assert "可以" not in terms


def test_tokenize_handles_mixed_english_and_chinese_text():
    terms = tokenize("Machine Learning 機器學習")
    assert "machine" in terms
    assert "learning" in terms
    assert any("機器" in t or "學習" in t for t in terms)


def test_tokenize_empty_string_returns_empty_set():
    assert tokenize("") == set()


def test_tokenize_whitespace_only_returns_empty_set():
    assert tokenize("   ") == set()
