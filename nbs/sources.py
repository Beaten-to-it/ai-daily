RSS_FEEDS = [
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml",
     "source_type": "article", "lane": "official"},
    {"name": "Google AI", "url": "https://blog.google/technology/ai/rss/",
     "source_type": "article", "lane": "official"},
    {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml",
     "source_type": "article", "lane": "official"},
    {"name": "AWS ML", "url": "https://aws.amazon.com/blogs/machine-learning/feed/",
     "source_type": "article", "lane": "official"},
    {"name": "NVIDIA Developer", "url": "https://developer.nvidia.com/blog/feed/",
     "source_type": "article", "lane": "official"},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml",
     "source_type": "article", "lane": "official"},
    {"name": "GeekNews", "url": "https://feeds.feedburner.com/geeknews-feed",
     "source_type": "article", "lane": "media"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
     "source_type": "article", "lane": "media"},
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
     "source_type": "article", "lane": "media"},
    {"name": "AI타임스", "url": "https://www.aitimes.com/rss/allArticle.xml",
     "source_type": "article", "lane": "media"},
    {"name": "arXiv cs.AI", "url": "https://rss.arxiv.org/rss/cs.AI",
     "source_type": "paper", "lane": "research"},
    {"name": "arXiv cs.CL", "url": "https://rss.arxiv.org/rss/cs.CL",
     "source_type": "paper", "lane": "research"},
    {"name": "GitHub Changelog", "url": "https://github.blog/changelog/feed/",
     "source_type": "article", "lane": "developer"},
]

BLUESKY_ACCOUNTS = [
    "simonwillison.net",
    "emollick.bsky.social",
    "hardmaru.bsky.social",
    "jeremyphoward.bsky.social",
    "jackclark.bsky.social",
]

GITHUB_REPOS = [
    "openai/openai-python",
    "anthropics/anthropic-sdk-python",
    "huggingface/transformers",
    "langchain-ai/langchain",
    "ollama/ollama",
]

GDELT_QUERIES = [
    '("artificial intelligence" OR "large language model" OR OpenAI OR Anthropic OR Gemini)',
]

X_QUERIES = [
    'AI agents OR "coding agents" OR agentic',
    '"Claude Code" OR Cursor OR Codex OR Windsurf',
    "OpenAI OR Anthropic OR Gemini OR Grok model",
    "open source LLM OR Qwen OR DeepSeek OR Mistral",
]

REDDIT_SUBS = ["LocalLLaMA", "MachineLearning"]
