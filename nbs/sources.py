# v0 활성. RSS 코어 (죽은 피드는 Task 6 스모크에서 교체) + X(twitter) + Reddit(opencli).
RSS_FEEDS = [
    {"name":"OpenAI",        "url":"https://openai.com/news/rss.xml",                                  "source_type":"article"},
    {"name":"GoogleAI",      "url":"https://blog.google/technology/ai/rss/",                           "source_type":"article"},
    {"name":"HuggingFace",   "url":"https://huggingface.co/blog/feed.xml",                             "source_type":"article"},
    {"name":"GeekNews",      "url":"https://feeds.feedburner.com/geeknews-feed",                       "source_type":"article"},
    {"name":"HackerNews",    "url":"https://hnrss.org/frontpage",                                      "source_type":"article"},
    {"name":"TheVerge AI",   "url":"https://www.theverge.com/rss/ai-artificial-intelligence/index.xml","source_type":"article"},
    {"name":"TechCrunch AI", "url":"https://techcrunch.com/category/artificial-intelligence/feed/",    "source_type":"article"},
    {"name":"arXiv cs.AI",   "url":"https://rss.arxiv.org/rss/cs.AI",                                  "source_type":"paper"},
    {"name":"arXiv cs.CL",   "url":"https://rss.arxiv.org/rss/cs.CL",                                  "source_type":"paper"},
]
# X (twitter CLI, 인증됨 @beaten2it) — v0 활성
X_QUERIES = [
    'AI agents OR "coding agents" OR agentic',
    '"Claude Code" OR Cursor OR Codex OR Windsurf',
    "OpenAI OR Anthropic OR Gemini OR Grok model",
    "open source LLM OR Qwen OR DeepSeek OR Mistral",
]
# Reddit (opencli) — v0 활성(best-effort). Chrome+Browser-Bridge 미가동 시 collect에서 가드 스킵.
REDDIT_SUBS = ["LocalLLaMA", "MachineLearning"]
