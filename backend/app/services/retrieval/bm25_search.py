"""BM25 Lexical Keyword Ranking and Reciprocal Rank Fusion (RRF).

Provides deterministic, offline lexical information retrieval tailored for
technical codes, acronyms, weapon IDs, and exact verbatim phrase matching.
Operates completely offline with zero external network dependencies.
"""

import math
import re
from collections import Counter
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def tokenize_for_bm25(text: str) -> list[str]:
    """Tokenize text into normalized unigrams and hyphenated technical identifiers.

    Preserves alphanumeric codes like 'cve-2024-38077', 's-400', 'mq-9', 'defcon-2'.
    """
    if not text:
        return []
    # Match alphanumeric words or hyphenated identifiers
    tokens = re.findall(r"\b[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*\b", text.lower())
    return [t for t in tokens if len(t) > 1 or t.isdigit()]


class BM25Ranker:
    """Okapi BM25 ranking model with exact technical identifier boosting."""

    def __init__(
        self,
        corpus: Sequence[str],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lens = [len(tokenize_for_bm25(doc)) for doc in corpus]
        self.avg_doc_len = sum(self.doc_lens) / max(self.corpus_size, 1)

        # Document frequencies and term frequencies per document
        self.doc_freqs: dict[str, int] = Counter()
        self.doc_tfs: list[dict[str, int]] = []

        for doc in corpus:
            tf = Counter(tokenize_for_bm25(doc))
            self.doc_tfs.append(tf)
            for token in tf.keys():
                self.doc_freqs[token] += 1

        # Precompute IDF for all terms in vocabulary
        self.idfs: dict[str, float] = {}
        for token, freq in self.doc_freqs.items():
            # Standard Lucene / Robertson-Spärck-Jones IDF
            idf = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            self.idfs[token] = max(idf, 0.05)

    def score(self, query: str) -> list[float]:
        """Compute BM25 scores for all documents against the query.

        Applies extra reward for exact hyphenated technical terms and multi-word phrase matches.
        """
        query_tokens = tokenize_for_bm25(query)
        if not query_tokens or self.corpus_size == 0:
            return [0.0] * self.corpus_size

        # Identify technical identifiers in query (e.g. cve-..., alphanumeric with digits)
        technical_terms = {t for t in query_tokens if "-" in t or any(c.isdigit() for c in t)}

        scores = [0.0] * self.corpus_size

        for i in range(self.corpus_size):
            doc_len = self.doc_lens[i]
            doc_tf = self.doc_tfs[i]
            score = 0.0

            # 1. Okapi BM25 Term Matching
            for q_term in query_tokens:
                if q_term not in doc_tf:
                    continue
                tf = doc_tf[q_term]
                idf = self.idfs.get(q_term, 0.1)

                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / max(self.avg_doc_len, 1.0)))
                term_score = idf * (numerator / max(denominator, 1e-9))

                # Technical term boost (e.g. CVE codes, weapon models)
                if q_term in technical_terms:
                    term_score *= 2.0

                score += term_score

            scores[i] = score

        # Normalize scores to [0.0, 1.0] if max > 0
        max_score = max(scores) if scores else 0.0
        if max_score > 1e-6:
            return [round(s / max_score, 4) for s in scores]
        return scores


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[T, float]]],
    k: int = 60,
    weights: list[float] | None = None,
) -> list[tuple[T, float]]:
    """Merge multiple ranked candidate lists using Reciprocal Rank Fusion (RRF).

    Formula:
        RRF_score(d) = sum_{m in M} ( w_m / (k + rank_m(d)) )

    Args:
        ranked_lists: List of rankings, each ranking is a list of (item_id, original_score).
        k: Smoothing constant, standard default is 60.
        weights: Optional relative weighting factor per ranked list (e.g. [1.0, 0.8]).

    Returns:
        Consolidated list of (item_id, rrf_score) sorted descending by rrf_score.
    """
    if not ranked_lists:
        return []

    if weights is None:
        weights = [1.0] * len(ranked_lists)
    elif len(weights) != len(ranked_lists):
        weights = [1.0] * len(ranked_lists)

    scores: dict[T, float] = {}

    for ranking, weight in zip(ranked_lists, weights, strict=False):
        for rank_idx, (item_id, _) in enumerate(ranking):
            rank = rank_idx + 1  # 1-based rank
            rrf_contrib = weight / (k + rank)
            scores[item_id] = scores.get(item_id, 0.0) + rrf_contrib

    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_items
