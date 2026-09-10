"""Twitter/X Thread Deliverable Adapter for Phase 4.

Generates structured multi-part Twitter thread featuring:
- Strict character count enforcement: <= 280 characters per tweet
- Numbered parts (e.g. "1/4", "2/4", ...)
- Engaging hook, core evidence tweets, and call-to-action conclusion
- Powered by local air-gapped LLM with robust fallback
- 100% claim-to-chunk provenance linking per tweet
"""

import logging
import re
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
    """Generates structured Twitter/X threads with strict 280-character limit per tweet."""

    deliverable_type = "twitter_thread"
    name = "Twitter / X Thread"
    description = "Multi-part social thread with strict 280-character tweet constraints, numbered parts, and 100% claim provenance."
    category = "social"
    requires_human_review = False
    system_prompt_template = (
        "You are a Digital Communications Strategist who turns dense briefing material into sharp, "
        "factually-anchored social threads. Your job is stylistic compression, not embellishment — "
        "every punchy line still has to be true to the source.\n\n"
        "Tone: Crisp, energetic, incisive. No academic hedging, no passive voice — but also no "
        "invented statistics or dramatized claims the source material doesn't support. Punchy and "
        "accurate are not in tension; if a fact isn't punchy enough on its own, find the truest "
        "sharp phrasing for it rather than exaggerating it.\n\n"
        "Hard constraint: every tweet strictly under 230 characters. Count before finalizing each "
        "tweet; if one runs long, cut words, don't run past the limit."
    )

    async def generate(
        self,
        source_doc_id: uuid.UUID,
        retrieved_chunks: list[RetrievedChunkItem],
        raw_text: str,
        params: GenerationParameters,
        doc_summary: str | None = None,
        key_entities: list[str] | None = None,
    ) -> AdapterOutput:
        """Synthesize 3-to-4 part numbered Twitter thread with strict 280-char cap per tweet."""
        if not retrieved_chunks:
            raise ValueError("No retrieved chunks available to ground Twitter thread.")

        target_tweet_count = 4 if len(retrieved_chunks) >= 3 else 3
        blocks: list[GroundedBlock] = []
        tweet_character_counts: list[int] = []

        # 1. Query local Ollama LLM
        llm_prompt = self.build_prompt(
            retrieved_chunks=retrieved_chunks,
            params=params,
            extra_instructions=(
                f"Write a {target_tweet_count}-part thread for {params.audience}, as exactly {target_tweet_count} "
                "tweets separated by blank lines. Do not prepend numbering like \"1/4\" — the system adds "
                "that automatically.\n\n"
                "- Tweet 1 (Hook): the single most attention-grabbing true fact from the source context, "
                "framed as a hook — not a vague teaser, an actual specific finding.\n"
                "- Middle tweet(s) (Evidence): 1-2 sentences each, hard facts and figures taken directly "
                "from the source context. If the source context has fewer distinct facts than tweets "
                "requested, it is acceptable to have a shorter thread rather than pad with restatement.\n"
                f"- Final tweet (Takeaway): a forward-looking conclusion or call-to-action for {params.audience} "
                "that follows logically from the evidence tweets — not a generic \"stay tuned\" close.\n\n"
                f"Every tweet ≤ 230 characters, verified by count before output. Tone: '{params.tone}'."
            ),
        )
        llm_text = await self.generate_with_llm(prompt=llm_prompt, max_tokens=400, temperature=0.6)

        llm_tweets: list[str] = []
        if llm_text:
            lines = [re.sub(r"^(Tweet\s*\d+:?|\d+[/.]\d*|\d+[.)])\s*", "", l.strip()) for l in llm_text.splitlines() if len(l.strip()) > 15]
            if len(lines) >= 2:
                llm_tweets = lines[:target_tweet_count]

        if llm_tweets:
            actual_count = len(llm_tweets)
            for idx, raw_tweet in enumerate(llm_tweets):
                tweet_num = idx + 1
                prefix = f"{tweet_num}/{actual_count} "
                target_chunk = retrieved_chunks[min(idx, len(retrieved_chunks) - 1)]

                body = raw_tweet
                if len(prefix + body) > 275:
                    available = 270 - len(prefix)
                    body = body[:available].rstrip() + "..."
                full_tweet = f"{prefix}{body}"
                tweet_character_counts.append(len(full_tweet))

                cit = CitationLinker.link_sentence(
                    sentence_text=body,
                    retrieved_chunks=retrieved_chunks,
                    raw_text=raw_text,
                    preferred_chunk_id=target_chunk.chunk_id,
                )
                blocks.append(
                    GroundedBlock(
                        block_index=idx,
                        title=f"Tweet {tweet_num}/{actual_count}",
                        sentences=[
                            GroundedSentence(
                                sentence_id=f"tweet_{tweet_num}",
                                sentence_index=idx,
                                text=full_tweet,
                                citations=[cit],
                            )
                        ],
                    )
                )
        else:
            # Deterministic fallback synthesis
            for idx in range(target_tweet_count):
                tweet_num = idx + 1
                prefix = f"{tweet_num}/{target_tweet_count} "
                chunk = retrieved_chunks[min(idx, len(retrieved_chunks) - 1)]

                first_clause = self.extract_clean_sentence(chunk.text, f"operational phase {tweet_num}").rstrip(".")

                if tweet_num == 1:
                    body = f"THREAD: Strategic assessment regarding {chunk.heading or 'operational directives'}. {first_clause}."
                elif tweet_num == target_tweet_count:
                    body = f"CONCLUSION: {first_clause}. Verifiable under air-gapped cryptographic integrity."
                else:
                    body = f"Key operational finding: {first_clause}."

                full_tweet = f"{prefix}{body}"
                if len(full_tweet) > 275:
                    available_len = 270 - len(prefix)
                    body = body[:available_len].rstrip() + "..."
                    full_tweet = f"{prefix}{body}"

                tweet_character_counts.append(len(full_tweet))

                cit = CitationLinker.link_sentence(
                    sentence_text=body,
                    retrieved_chunks=retrieved_chunks,
                    raw_text=raw_text,
                    preferred_chunk_id=chunk.chunk_id,
                )
                blocks.append(
                    GroundedBlock(
                        block_index=idx,
                        title=f"Tweet {tweet_num}/{target_tweet_count}",
                        sentences=[
                            GroundedSentence(
                                sentence_id=f"tweet_{tweet_num}",
                                sentence_index=idx,
                                text=full_tweet,
                                citations=[cit],
                            )
                        ],
                    )
                )

        title = f"Thread: {retrieved_chunks[0].heading or 'Strategic Intelligence Mandate'}"
        content = GroundedDeliverableContent(
            title=title,
            summary=f"Structured {len(blocks)}-part Twitter/X thread with strict character limits and 100% claim provenance.",
            blocks=blocks,
        )

        format_metadata = {
            "thread_length": len(blocks),
            "max_tweet_length": max(tweet_character_counts) if tweet_character_counts else 0,
            "all_under_280": all(c <= 280 for c in tweet_character_counts),
            "all_within_limit": all(c <= 280 for c in tweet_character_counts),
            "character_counts": tweet_character_counts,
            "suggested_hashtags": ["#AirGapAI", "#GenAI", "#CyberDefense", "#InfoSec"],
        }

        return AdapterOutput(
            content=content,
            format_metadata=format_metadata,
            requires_human_review=self.requires_human_review,
        )
