"""Retrieval over the service team's passages: word and character n-grams, so German compounds and English
paraphrases both find their passage. Azure AI Search plays this part in the deployed version (infra/terraform)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class Passage:
    id: str
    title: str
    text: str


class Knowledge:
    def __init__(self, passages: list[Passage], min_score: float):
        self.passages = passages
        self.min_score = min_score
        docs = [f"{p.title} {p.text}" for p in passages]
        self.word = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True).fit(docs)
        self.char = TfidfVectorizer(lowercase=True, analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit(docs)
        self.wm, self.cm = self.word.transform(docs), self.char.transform(docs)

    @classmethod
    def load(cls, path: Path, min_score: float = 0.08) -> Knowledge:
        data = tomllib.loads(path.read_text())
        return cls([Passage(**p) for p in data["passage"]], min_score)

    def search(self, query: str) -> tuple[Passage | None, float]:
        s = (
            0.5 * cosine_similarity(self.word.transform([query]), self.wm)[0]
            + 0.5 * cosine_similarity(self.char.transform([query]), self.cm)[0]
        )
        best = int(s.argmax())
        return (self.passages[best], float(s[best])) if s[best] >= self.min_score else (None, float(s[best]))
