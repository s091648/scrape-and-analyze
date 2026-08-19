"""Language-aware tokenizer shared by index-build time and query time
(023-article-search / 023-article-search follow-up).

English text: lowercased, split on non-alphanumeric boundaries. Traditional Chinese
text: segmented via jieba (naive whitespace/punctuation splitting would treat whole
sentences as single unsegmented "words", useless for autocomplete). Both languages are
then filtered by minimum length and a stopword list (research.md "Decision: Term
extraction / tokenization").

Lives in shared/ (not src/modules/search/domain/services/, where this originated) because
both src/'s RebuildSearchIndexUseCase (tokenizing article text at index-build time) and
backend/services/search_service.py (tokenizing the visitor's query string at retrieval
time, for the exact-match AND-intersection lookup) must use the exact same algorithm —
a query token that doesn't match how the same text was tokenized when indexed would
simply never be found. src/'s domain-layer tokenizer.py re-exports from here to keep its
existing import path stable rather than scattering `from shared...` across src/."""
import re

import jieba
import stopwordsiso

MIN_TERM_LENGTH = 2

_EN_STOPWORDS = stopwordsiso.stopwords("en")

# stopwordsiso's "zh" set is simplified-Chinese-oriented — several very common function
# words differ in character form between simplified and traditional (這/这, 個/个, etc.)
# and would otherwise slip through untouched on zh-TW content. Supplemented with a small,
# hand-picked set of the traditional-character variants of stopwordsiso's own entries.
_ZH_TRADITIONAL_EXTRA_STOPWORDS = frozenset({
    "這個", "這樣", "這裡", "這些", "那個", "那樣", "那裡", "那些",
    "為", "個", "們", "麼", "來", "還", "後", "沒", "見", "說", "會", "只", "現", "與",
})
_ZH_STOPWORDS = stopwordsiso.stopwords("zh") | _ZH_TRADITIONAL_EXTRA_STOPWORDS

_CJK_CHAR = re.compile(r"[一-鿿]")
_NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")


def _is_cjk_char(ch: str) -> bool:
    return bool(_CJK_CHAR.match(ch))


def _split_mixed_script(text: str) -> list[str]:
    """Split text into contiguous runs of CJK vs. non-CJK characters, so each run can
    be tokenized with the right strategy below."""
    segments: list[str] = []
    current: list[str] = []
    current_is_cjk: bool | None = None
    for ch in text:
        ch_is_cjk = _is_cjk_char(ch)
        if current_is_cjk is not None and ch_is_cjk != current_is_cjk:
            segments.append("".join(current))
            current = []
        current.append(ch)
        current_is_cjk = ch_is_cjk
    if current:
        segments.append("".join(current))
    return segments


def tokenize(text: str) -> set[str]:
    """Extract the set of distinct, filtered terms occurring in `text` (title+content
    for one article at index-build time, or the raw query string at retrieval time —
    callers dedupe per-article before counting document frequency)."""
    terms: set[str] = set()
    for segment in _split_mixed_script(text):
        if segment and _is_cjk_char(segment[0]):
            candidates = jieba.lcut(segment)
            stopwords = _ZH_STOPWORDS
        else:
            candidates = [c for c in _NON_ALNUM.split(segment.lower()) if c]
            stopwords = _EN_STOPWORDS
        for term in candidates:
            term = term.strip()
            if len(term) >= MIN_TERM_LENGTH and term not in stopwords:
                terms.add(term)
    return terms
