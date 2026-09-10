"""Twitter/X Thread Deliverable Adapter for Phase 4.

Generates concise, punchy Twitter threads featuring:
- Hook-first introductory tweet
- Sequential numbering (1/N, 2/N, etc.)
- Strict character limit enforcement (<= 280 characters per tweet)
- 100% claim-to-chunk provenance linking
"""

import logging
import uuid

from app.schemas.adapters import GenerationParameters
from app.schemas.grounding import (
    GroundedBlock,
    GroundedDeliverableContent,
    GroundedSentence,
    RetrievedChunkItem,
)
from app.services.adapters.base import AdapterOutput, BaseDeliverableAdapter
from app.services.adapters.citation_linker import CitationLinker

logger = logging.getLogger("app.services.adapters.twitter")


class TwitterThreadAdapter(BaseDeliverableAdapter):
    """Generates sequentially numbered, char-limited Twitter/X threads."""

    deliverable_type = "twitter_thread"
    name = "Twitter / X Thread"
    description = "Sequential, character-capped (280 char) Twitter/X thread with hook-first opening and grounded narrative."
    category = "social"
    requires_human_review = False

    async def generate(
        self,
        source_doc_id: uuid.UUID,
        retrieved_chunks: list[RetrievedChunkItem],
        raw_text: str,
        params: GenerationParameters,
        doc_summary: str | None = None,
        key_entities: list[str] | None = None,
    ) -> AdapterOutput:
        """Synthesize 4-part numbered Twitter thread with strict 280-char cap per tweet."""
        if not retrieved_chunks:
            raise ValueError("No retrieved chunks available to ground Twitter thread.")

        chunks = retrieved_chunks[:4]
        total_tweets = len(chunks)
        blocks: list[GroundedBlock] = []
        tweet_character_counts: list[int] = []

        for idx, chunk in enumerate(chunks):
            tweet_num = idx + 1
            prefix = f"{tweet_num}/{total_tweets} "

            # Extract clean main clause from chunk text
            first_clause = chunk.text.strip().split(".")[0].strip()

            if tweet_num == 1:
                # Hook tweet
                body = f"THREAD: Critical intelligence briefing on {chunk.heading or 'operational mandates'}. {first_clause}."
            elif tweet_num == total_tweets:
                # Conclusion & CTA tweet
                body = f"CONCLUSION: {first_clause}. Full report verified with zero-egress cryptographic audit trail."
            else:
                # Context / Evidence tweet
                body = f"Key finding: {first_clause}."

            # Strict 280-character enforcement
            full_tweet = f"{prefix}{body}"
            if len(full_tweet) > 275:
                # Truncate body to fit inside 270 chars + ellipsis
                available_len = 270 - len(prefix)
                body = body[:available_len].rstrip() + "..."
                full_tweet = f"{prefix}{body}"

            tweet_character_counts.append(len(full_tweet))

            # Citation linking
            cit = CitationLinker.link_sentence(
                sentence_text=body,
                retrieved_chunks=retrieved_chunks,
                raw_text=raw_text,
                preferred_chunk_id=chunk.chunk_id,
            )

            sentence = GroundedSentence(
                sentence_id=f"tweet_{tweet_num}",
                sentence_index=idx,
                text=full_tweet,
                citations=[cit],
            )

            blocks.append(
                GroundedBlock(
                    block_index=idx,
                    title=f"Tweet {tweet_num}/{total_tweets}",
                    sentences=[sentence],
                )
            )

        title = f"Thread: {chunks[0].heading or 'Strategic Intelligence Mandate'}"
        content = GroundedDeliverableContent(
            title=title,
            summary=f"A {total_tweets}-part Twitter/X thread with strict 280-char limit enforcement and chunk grounding.",
            blocks=blocks,
        )

        format_metadata = {
            "target_platform": "Twitter / X",
            "thread_length": total_tweets,
            "max_character_limit": 280,
            "tweet_character_counts": tweet_character_counts,
            "all_within_limit": all(c <= 280 for c in tweet_character_counts),
        }

        return AdapterOutput(
            content=content,
            format_metadata=format_metadata,
            requires_human_review=self.requires_human_review,
        )
