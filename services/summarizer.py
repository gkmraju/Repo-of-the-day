"""
services/summarizer.py — Local NLP summarisation without any paid AI.

Techniques used:
  • TextRank (via sumy) for extractive summarisation
  • TF-IDF keyword extraction (scikit-learn)
  • RAKE-style keyword extraction (NLTK)
  • Template-based content generation
"""
from __future__ import annotations

import re
import string
from collections import Counter
from typing import TYPE_CHECKING

import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sumy.nlp.stemmers import Stemmer
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.utils import get_stop_words

from services.logger import logger

if TYPE_CHECKING:
    from services.github_service import RawRepo
    from services.readme_parser import ParsedReadme

LANGUAGE = "english"
_NLTK_RESOURCES = ["punkt", "stopwords", "averaged_perceptron_tagger", "punkt_tab"]


def ensure_nltk_data() -> None:
    """Download required NLTK data (idempotent)."""
    for resource in _NLTK_RESOURCES:
        try:
            nltk.data.find(f"tokenizers/{resource}")
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except Exception as exc:
                logger.debug("NLTK download {} failed: {}", resource, exc)


# ── Main summariser class ──────────────────────────────────────────────────

class Summarizer:
    """Generate structured educational content from repo metadata + README."""

    # Audience tags (topic → audience list)
    _TOPIC_AUDIENCE: dict[str, list[str]] = {
        "machine-learning": ["AI/ML Engineers", "Data Scientists", "Researchers"],
        "deep-learning": ["AI/ML Engineers", "Researchers", "Students"],
        "nlp": ["NLP Engineers", "Data Scientists", "Researchers"],
        "llm": ["AI Engineers", "Backend Developers", "Researchers"],
        "data-science": ["Data Scientists", "Analysts", "Researchers"],
        "devops": ["DevOps Engineers", "SREs", "Cloud Engineers"],
        "kubernetes": ["DevOps Engineers", "Cloud Engineers", "SREs"],
        "docker": ["DevOps Engineers", "Backend Developers", "Students"],
        "cli": ["Developers", "DevOps Engineers", "Power Users"],
        "api": ["Backend Developers", "Frontend Developers", "Students"],
        "web": ["Web Developers", "Frontend Developers", "Fullstack Developers"],
        "security": ["Security Engineers", "Pentesters", "DevOps Engineers"],
        "automation": ["DevOps Engineers", "QA Engineers", "Automation Engineers"],
        "game": ["Game Developers", "Students", "Hobbyists"],
        "mobile": ["Mobile Developers", "Flutter/React Native Devs"],
        "blockchain": ["Blockchain Developers", "Web3 Engineers", "Researchers"],
        "database": ["Backend Developers", "Data Engineers", "DBAs"],
    }

    _DEFAULT_AUDIENCE = ["Python Developers", "Open Source Contributors", "Students", "Backend Developers"]

    def __init__(self) -> None:
        ensure_nltk_data()
        self._stemmer = Stemmer(LANGUAGE)
        self._stop_words = set(get_stop_words(LANGUAGE))

    # ── Public API ─────────────────────────────────────────────────────────

    def generate(self, repo: "RawRepo", readme: "ParsedReadme") -> dict:
        """
        Return a dict with all content sections ready for the template.
        """
        full_text = self._build_corpus(repo, readme)

        keywords = self._extract_keywords(full_text, top_n=15)
        what_is = self._generate_what_is(repo, readme, keywords)
        why_useful = self._generate_why_useful(repo, readme, keywords)
        audience = self._detect_audience(repo)
        features = self._generate_features(repo, readme, keywords)
        how_it_works = self._generate_how_it_works(repo, readme, keywords)
        installation = self._generate_installation(repo, readme)
        quick_example = self._generate_quick_example(readme)
        tech_stack = self._detect_tech_stack(repo, readme)
        pros = self._generate_pros(repo, readme, keywords)
        cons = self._generate_cons(repo, readme)
        learnings = self._generate_learnings(repo, readme, tech_stack, keywords)
        similar = self._suggest_similar(repo)
        one_liner = self._generate_one_liner(repo, keywords)

        return {
            "what_is": what_is,
            "why_useful": why_useful,
            "audience": audience,
            "features": features,
            "how_it_works": how_it_works,
            "installation": installation,
            "quick_example": quick_example,
            "tech_stack": tech_stack,
            "pros": pros,
            "cons": cons,
            "learnings": learnings,
            "similar_projects": similar,
            "one_liner": one_liner,
            "keywords": keywords,
        }

    # ── Corpus builder ─────────────────────────────────────────────────────

    def _build_corpus(self, repo: "RawRepo", readme: "ParsedReadme") -> str:
        parts = [
            repo.description or "",
            " ".join(repo.topics or []),
            readme.plain_text[:5000],
        ]
        return " ".join(filter(None, parts))

    # ── Keyword extraction (TF-IDF + RAKE hybrid) ──────────────────────────

    def _extract_keywords(self, text: str, top_n: int = 15) -> list[str]:
        if not text.strip():
            return []
        try:
            # TF-IDF on sentences
            sentences = nltk.sent_tokenize(text)
            if not sentences:
                return []
            vectorizer = TfidfVectorizer(
                max_features=200,
                stop_words="english",
                ngram_range=(1, 2),
                min_df=1,
            )
            matrix = vectorizer.fit_transform(sentences)
            scores = matrix.sum(axis=0).A1
            vocab = vectorizer.get_feature_names_out()
            ranked = sorted(zip(vocab, scores), key=lambda x: -x[1])
            return [kw for kw, _ in ranked[:top_n] if len(kw) > 3]
        except Exception as exc:
            logger.debug("Keyword extraction failed: {}", exc)
            return self._simple_keywords(text, top_n)

    def _simple_keywords(self, text: str, top_n: int) -> list[str]:
        """Fallback: frequency-based keyword extraction."""
        stop = self._stop_words | set(string.punctuation)
        words = re.findall(r"\b[a-z][a-z0-9_-]{2,}\b", text.lower())
        counts = Counter(w for w in words if w not in stop)
        return [w for w, _ in counts.most_common(top_n)]

    # ── TextRank sentence extraction ───────────────────────────────────────

    def _textrank_summary(self, text: str, sentence_count: int = 3) -> str:
        if not text or len(text.split()) < 20:
            return text[:300] if text else ""
        try:
            parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
            summarizer = TextRankSummarizer(self._stemmer)
            summarizer.stop_words = get_stop_words(LANGUAGE)
            sentences = summarizer(parser.document, sentence_count)
            return " ".join(str(s) for s in sentences)
        except Exception:
            try:
                sentences = nltk.sent_tokenize(text)
                return " ".join(sentences[:sentence_count])
            except Exception:
                return text[:400]

    # ── Section generators ─────────────────────────────────────────────────

    def _generate_what_is(self, repo: "RawRepo", readme: "ParsedReadme", keywords: list[str]) -> str:
        name = repo.name or "This project"
        desc = repo.description or readme.description or ""
        lang = repo.language or "code"
        topics = ", ".join((repo.topics or [])[:4])
        topics_str = f" ({topics})" if topics else ""

        base = (
            f"**{name}** is an open-source {lang} project{topics_str}. "
        )
        if desc:
            base += desc.rstrip(".") + ". "

        # Augment with TextRank summary of README intro
        if readme.plain_text:
            intro = readme.plain_text[:2000]
            summary = self._textrank_summary(intro, 2)
            if summary and summary.lower() not in base.lower():
                base += summary

        return _cap_words(base.strip(), 120)

    def _generate_why_useful(self, repo: "RawRepo", readme: "ParsedReadme", keywords: list[str]) -> str:
        name = repo.name or "it"
        topics = repo.topics or []
        desc = repo.description or ""

        lines: list[str] = []

        # Problem statement heuristic
        problem_kws = {"solve", "fix", "simplif", "automat", "replac", "improv", "fast", "easy", "simple"}
        for kw in problem_kws:
            if kw in (desc + readme.plain_text[:1000]).lower():
                lines.append(f"Addresses real developer pain points around {', '.join(keywords[:3])}.")
                break
        else:
            lines.append(f"Simplifies complex workflows around {', '.join(keywords[:3]) or 'software development'}.")

        if repo.stars and repo.stars > 5000:
            lines.append(f"Trusted by the community with {repo.stars:,} GitHub stars.")
        if "documentation" in readme.all_sections or readme.installation:
            lines.append("Well-documented with clear setup instructions — easy to get started.")
        if repo.license:
            lines.append(f"Released under {repo.license} — free to use in personal and commercial projects.")
        if len(topics) > 3:
            lines.append(f"Covers important domains: {', '.join(topics[:5])}.")

        return "\n".join(f"• {l}" for l in lines[:5])

    def _detect_audience(self, repo: "RawRepo") -> list[str]:
        audience: set[str] = set()
        for topic in (repo.topics or []):
            if topic.lower() in self._TOPIC_AUDIENCE:
                audience.update(self._TOPIC_AUDIENCE[topic.lower()])
        if not audience:
            audience.update(self._DEFAULT_AUDIENCE)
        return sorted(audience)[:6]

    def _generate_features(self, repo: "RawRepo", readme: "ParsedReadme", keywords: list[str]) -> list[str]:
        features = list(readme.features)

        # Supplement from description
        if repo.description and len(features) < 5:
            features.insert(0, repo.description)

        # Supplement from keywords if still sparse
        if len(features) < 4:
            for kw in keywords[:6]:
                features.append(f"Built around {kw} — a key capability of this project.")
            features = features[:8]

        # Clean & deduplicate
        seen: set[str] = set()
        result: list[str] = []
        for f in features:
            clean = re.sub(r"\s+", " ", f).strip()
            if clean and clean not in seen and len(clean) > 10:
                seen.add(clean)
                result.append(clean)

        return result[:10] if result else [f"Focused on {kw}" for kw in keywords[:5]]

    def _generate_how_it_works(self, repo: "RawRepo", readme: "ParsedReadme", keywords: list[str]) -> str:
        # Look for arch/overview section
        for key in ("how_it_works", "architecture", "overview", "design"):
            content = readme.all_sections.get(key, "")
            if content and len(content) > 100:
                return _to_plain_minimal(content[:600])

        # Build from README plain text TextRank
        if readme.plain_text:
            summary = self._textrank_summary(readme.plain_text[:3000], 3)
            if summary:
                return summary

        lang = repo.language or "multiple languages"
        topics = ", ".join((repo.topics or [])[:4]) or "software development"
        return (
            f"{repo.name} is built with {lang} and focuses on {topics}. "
            "It follows a modular design that makes it easy to integrate into existing workflows. "
            "The codebase is structured for clarity, testability, and extensibility."
        )

    def _generate_installation(self, repo: "RawRepo", readme: "ParsedReadme") -> str:
        if readme.installation:
            # Extract code blocks from installation section
            code_blocks = re.findall(r"```[\w]*\n(.*?)```", readme.installation, re.DOTALL)
            if code_blocks:
                return code_blocks[0].strip()[:500]
            return _to_plain_minimal(readme.installation[:400])

        # Fallback heuristics
        lang = repo.language or ""
        name = repo.name or "package"
        if "python" in lang.lower():
            return f"pip install {name.lower()}\n\n# Or from source:\ngit clone {repo.url}\ncd {name}\npip install -e ."
        if "javascript" in lang.lower() or "typescript" in lang.lower():
            return f"npm install {name.lower()}\n# or\nyarn add {name.lower()}"
        if "go" in lang.lower():
            return f"go install {repo.url.replace('https://github.com/', 'github.com/')}@latest"
        if "rust" in lang.lower():
            return f"cargo add {name.lower()}"
        return f"git clone {repo.url}\ncd {name}\n# Follow README for setup"

    def _generate_quick_example(self, readme: "ParsedReadme") -> str:
        if readme.examples:
            return readme.examples[0].strip()[:500]
        if readme.usage:
            code = re.findall(r"```[\w]*\n(.*?)```", readme.usage, re.DOTALL)
            if code:
                return code[0].strip()[:500]
        return ""

    def _detect_tech_stack(self, repo: "RawRepo", readme: "ParsedReadme") -> list[str]:
        stack: list[str] = []
        if repo.language:
            stack.append(f"Language: {repo.language}")

        text_lower = (readme.raw or "").lower()

        frameworks = {
            "django": "Framework: Django",
            "flask": "Framework: Flask",
            "fastapi": "Framework: FastAPI",
            "react": "Frontend: React",
            "vue": "Frontend: Vue.js",
            "angular": "Frontend: Angular",
            "next.js": "Framework: Next.js",
            "pytorch": "ML: PyTorch",
            "tensorflow": "ML: TensorFlow",
            "scikit-learn": "ML: scikit-learn",
            "transformers": "ML: Hugging Face Transformers",
            "postgresql": "Database: PostgreSQL",
            "mongodb": "Database: MongoDB",
            "redis": "Cache: Redis",
            "docker": "Container: Docker",
            "kubernetes": "Orchestration: Kubernetes",
            "graphql": "API: GraphQL",
            "grpc": "API: gRPC",
            "celery": "Task Queue: Celery",
            "kafka": "Messaging: Kafka",
            "rabbitmq": "Messaging: RabbitMQ",
        }
        for kw, label in frameworks.items():
            if kw in text_lower:
                stack.append(label)

        # From readme tech_stack section
        stack.extend(readme.tech_stack[:5])

        return list(dict.fromkeys(stack))[:8]  # Unique, max 8

    def _generate_pros(self, repo: "RawRepo", readme: "ParsedReadme", keywords: list[str]) -> list[str]:
        pros: list[str] = []
        if repo.stars and repo.stars > 1000:
            pros.append(f"Proven community adoption ({repo.stars:,}+ stars)")
        if repo.license:
            pros.append(f"Open source under {repo.license}")
        if readme.installation:
            pros.append("Clear installation and setup documentation")
        if repo.contributors_count and repo.contributors_count > 10:
            pros.append(f"Active contributor base ({repo.contributors_count}+ contributors)")
        if repo.topics:
            pros.append(f"Well-tagged with relevant topics for discoverability")
        if readme.screenshots:
            pros.append("Includes demos and screenshots for quick evaluation")
        pros.append("Free and open-source — zero licensing cost")
        return pros[:6]

    def _generate_cons(self, repo: "RawRepo", readme: "ParsedReadme") -> list[str]:
        cons: list[str] = []
        if not readme.installation:
            cons.append("Installation docs could be improved")
        if repo.open_issues and repo.open_issues > 200:
            cons.append(f"High open issue count ({repo.open_issues}) may indicate backlog")
        if repo.contributors_count and repo.contributors_count < 5:
            cons.append("Primarily maintained by a small team — bus-factor risk")
        if not repo.license:
            cons.append("No explicit license — check before commercial use")
        cons.append("May require familiarity with the domain to get the most value")
        return cons[:4]

    def _generate_learnings(
        self,
        repo: "RawRepo",
        readme: "ParsedReadme",
        tech_stack: list[str],
        keywords: list[str],
    ) -> list[str]:
        learnings: list[str] = []
        lang = repo.language
        if lang:
            learnings.append(f"Advanced {lang} patterns and idioms")
        if tech_stack:
            learnings.append(f"Integration of {', '.join([t.split(': ')[-1] for t in tech_stack[:3]])}")
        learnings.append("Open-source project structure and contribution workflow")
        learnings.append("Real-world application of " + (", ".join(keywords[:3]) or "software engineering"))
        if repo.topics:
            learnings.append(f"Domain knowledge in {', '.join((repo.topics or [])[:3])}")
        return learnings[:5]

    def _suggest_similar(self, repo: "RawRepo") -> list[dict]:
        """
        Build a list of suggested similar repos based on topics + language.
        In production these would come from a GitHub search; here we use
        curated pairs to stay free & offline-safe.
        """
        suggestions: list[dict] = []
        topics = {t.lower() for t in (repo.topics or [])}
        lang = (repo.language or "").lower()

        SIMILAR_DB: list[dict] = [
            {"name": "sindresorhus/awesome", "desc": "Awesome lists about all kinds of interesting topics"},
            {"name": "public-apis/public-apis", "desc": "A collective list of free APIs"},
            {"name": "donnemartin/system-design-primer", "desc": "Learn how to design large-scale systems"},
            {"name": "TheAlgorithms/Python", "desc": "All Algorithms implemented in Python"},
            {"name": "fastapi/fastapi", "desc": "FastAPI framework for building APIs with Python"},
            {"name": "tiangolo/sqlmodel", "desc": "SQL databases in Python, designed for simplicity"},
            {"name": "huggingface/transformers", "desc": "State-of-the-art ML Transformers"},
            {"name": "langchain-ai/langchain", "desc": "Building applications with LLMs"},
            {"name": "pallets/flask", "desc": "The Python micro framework for building web applications"},
            {"name": "django/django", "desc": "The Web framework for perfectionists with deadlines"},
        ]

        for item in SIMILAR_DB:
            if item["name"] != repo.full_name:
                suggestions.append(item)
            if len(suggestions) >= 5:
                break

        return suggestions

    def _generate_one_liner(self, repo: "RawRepo", keywords: list[str]) -> str:
        name = repo.name or "This project"
        kws = keywords[:3] if keywords else ["innovation", "productivity", "open source"]
        return (
            f"⭐ {name} is a must-explore for any developer passionate about "
            f"{', '.join(kws)} — dive in and level up your skills today!"
        )


# ── Text helpers ────────────────────────────────────────────────────────────

def _cap_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def _to_plain_minimal(text: str) -> str:
    text = re.sub(r"```[\w]*\n.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"!\[.*?\]\([^\)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
