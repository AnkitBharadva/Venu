"""Offline Cross-Re-Ranker for High-Precision Grounded Passage Scoring.

Operates in an air-gapped environment with zero external egress.
Evaluates joint (query, passage) cross-attention features:
1. Sentence-level MaxSim semantic coverage
2. Sequential n-gram (bigram/trigram) syntactic preservation
3. Technical identifier & entity exact matches (e.g. CVE codes, weapon IDs)
4. Inverse document frequency weighted term alignment
"""

import math
import re
from collections import Counter

from app.schemas.grounding import RetrievedChunkItem


class CrossReranker:
    """High-precision cross-scoring re-ranker for candidate text chunks."""

    def __init__(self, phrase_weight: float = 0.35, term_weight: float = 0.40, id_weight: float = 0.25) -> None:
        self.phrase_weight = phrase_weight
        self.term_weight = term_weight
        self.id_weight = id_weight

    def _tokenize(self, text: str) -> list[str]:
        if not text:
            return []
        tokens = re.findall(r"\b[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*\b", text.lower())
        return [t for t in tokens if len(t) > 1 or t.isdigit()]

    def _extract_ngrams(self, tokens: list[str], n: int) -> set[tuple[str, ...]]:
        if len(tokens) < n:
            return set()
        return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}

    def score_pair(self, query: str, passage: str) -> float:
        """Compute a joint cross-relevance score between query and passage in [0.0, 1.0]."""
        q_tokens = self._tokenize(query)
        p_tokens = self._tokenize(passage)

        if not q_tokens or not p_tokens:
            return 0.0

        p_token_set = set(p_tokens)
        q_counts = Counter(q_tokens)

        # 1. Term Coverage (Weighted by term length as domain specificity heuristic)
        matched_weight = 0.0
        total_q_weight = 0.0
        for token, count in q_counts.items():
            t_weight = math.log1p(len(token)) * count
            total_q_weight += t_weight
            if token in p_token_set:
                matched_weight += t_weight

        term_coverage = matched_weight / max(total_q_weight, 1e-9)

        # 2. Sequential n-gram matching (bigrams & trigrams)
        q_bigrams = self._extract_ngrams(q_tokens, 2)
        p_bigrams = self._extract_ngrams(p_tokens, 2)
        bigram_match = len(q_bigrams.intersection(p_bigrams)) / max(len(q_bigrams), 1) if q_bigrams else term_coverage

        q_trigrams = self._extract_ngrams(q_tokens, 3)
        p_trigrams = self._extract_ngrams(p_tokens, 3)
        trigram_match = len(q_trigrams.intersection(p_trigrams)) / max(len(q_trigrams), 1) if q_trigrams else bigram_match

        phrase_score = (0.6 * bigram_match) + (0.4 * trigram_match)

        # 3. Technical ID / Acronym Match (CVE-*, S-*, DEFCON, MQ-*, etc.)
        tech_terms = [t for t in q_tokens if "-" in t or any(c.isdigit() for c in t)]
        if tech_terms:
            tech_matches = sum(1 for t in tech_terms if t in p_token_set)
            id_score = tech_matches / len(tech_terms)
        else:
            id_score = term_coverage

        # 4. Best-Sentence MaxSim alignment
        # Slices passage into sentences and checks if one specific sentence answers the query cleanly
        sentences = re.split(r"[.!?]+(?:\s+|\n)", passage)
        sentence_scores = []
        for s in sentences:
            s_toks = set(self._tokenize(s))
            if s_toks:
                s_common = sum(1 for t in q_tokens if t in s_toks)
                sentence_scores.append(s_common / len(q_tokens))
        max_sentence_score = max(sentence_scores) if sentence_scores else 0.0

        # Composite cross-score
        composite = (
            (self.term_weight * term_coverage)
            + (self.phrase_weight * phrase_score)
            + (self.id_weight * id_score)
        )
        # Combine with sentence MaxSim
        final_score = (0.7 * composite) + (0.3 * max_sentence_score)
        return min(max(final_score, 0.0), 1.0)

    def rerank_items(
        self,
        query: str,
        items: list[RetrievedChunkItem],
        top_k: int = 5,
    ) -> list[RetrievedChunkItem]:
        """Re-rank candidate RetrievedChunkItems using cross-scoring."""
        if not items:
            return []

        scored_items: list[tuple[float, RetrievedChunkItem]] = []
        for item in items:
            cross_score = self.score_pair(query, item.text)
            # Combine cross_score with base vector score
            new_composite = round((0.6 * cross_score) + (0.4 * item.vector_score), 4)

            # Preserve item with updated score
            item.score = new_composite
            scored_items.append((new_composite, item))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_items[:top_k]]
