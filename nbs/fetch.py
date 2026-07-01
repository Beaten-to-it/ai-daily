import re

MIN_ARTICLE_CHARS = 1200   # tunable — below this an article body isn't "full text"
MIN_SHELL_CHARS = 200      # below this an HTML page is an empty JS shell / dead / stub
MIN_ABSTRACT_CHARS = 400   # arXiv abstract floor for confirmed
PAYWALL_MARKERS = (
    "subscribe to continue", "subscribe to read", "sign in to read",
    "for subscribers", "create a free account", "이 기사를 읽으려면",
    "구독자 전용", "회원 전용", "로그인이 필요",
)

def _visible_len(text: str) -> int:
    # strip tags + collapse whitespace so an HTML shell scores ~0
    t = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return len(re.sub(r"\s+", " ", t).strip())

def classify_evidence(source_type, text, *, paywall_marker=False, fetch_ok=True):
    if not fetch_ok or not text or not text.strip():
        return "exclude"
    n = _visible_len(text)
    if n == 0:
        return "exclude"
    low = text.lower()
    marker = paywall_marker or any(m in low for m in PAYWALL_MARKERS)
    if source_type == "paper":
        return "confirmed" if n >= MIN_ABSTRACT_CHARS else "short"
    if source_type in ("sns", "video"):
        return "confirmed" if n >= MIN_ARTICLE_CHARS else "short"
    # article / repo (web page): tiny page = JS shell / dead / stub → not obtained
    if n < MIN_SHELL_CHARS:
        return "exclude"
    if marker and n < MIN_ARTICLE_CHARS:      # paywall stub: short body + gate marker
        return "exclude"
    return "confirmed" if n >= MIN_ARTICLE_CHARS else "short"
