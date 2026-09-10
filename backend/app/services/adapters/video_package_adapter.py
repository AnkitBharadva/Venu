"""Video Package Deliverable Adapter for Phase 4.

Generates complete multimedia production packages featuring:
- Script & narration text powered by local air-gapped LLM
- Storyboard beats & scene descriptions
- Subtitles (SRT-style) text
- Visual recommendations & b-roll direction
- Explicitly NOT a rendered video binary file (adheres strictly to specification)
- 100% claim-to-chunk provenance linking
"""

import logging
import re
import uuid
from typing import Any

from app.schemas.adapters import GenerationParameters
from app.schemas.grounding import (
    GroundedBlock,
    GroundedDeliverableContent,
    GroundedSentence,
    RetrievedChunkItem,
)
from app.services.adapters.base import AdapterOutput, BaseDeliverableAdapter
from app.services.adapters.citation_linker import CitationLinker

logger = logging.getLogger("app.services.adapters.video_package")


class VideoPackageAdapter(BaseDeliverableAdapter):
    """Generates video production packages: script, storyboard beats, narration, subtitles, and visual prompts."""

    deliverable_type = "video_package"
    name = "Video Package (Script & Storyboard)"
    description = "Complete video production package with narration script, storyboard beats, visual recommendations, and SRT subtitles."
    category = "multimedia"
    requires_human_review = False
    system_prompt_template = (
        "You are a Producer writing voiceover narration scripts for briefing videos. You write for "
        "the ear, not the eye — natural spoken cadence, no dense clause-stacking that reads fine on "
        "a page but is unspeakable aloud.\n\n"
        "Tone: Compelling, authoritative, spoken-word cadence — grounded strictly in the source "
        "material, not dramatized beyond what it supports."
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
        """Synthesize 4-scene storyboard and narration script with SRT subtitles."""
        if not retrieved_chunks:
            raise ValueError("No retrieved chunks available to ground Video Package.")

        scene_configs = [
            ("Scene 1: Title & Hook Sequence", "Cinematic drone shot descending toward fortified enclave", "Fast kinetic text overlay with low-frequency atmospheric audio"),
            ("Scene 2: Operational Context & Challenge", "Technical UI schematic demonstrating isolation perimeter", "Split screen showing air-gap boundary and protected nodes"),
            ("Scene 3: Deep Technical Breakdown", "3D animated visualization of encrypted data flow and KMS", "Glowing cryptographic data streams with zero egress indicator"),
            ("Scene 4: Strategic Takeaway & Outro", "Command center dashboard showing 100% verification badge", "Final slate with defense badge and audit verification hash"),
        ]

        blocks: list[GroundedBlock] = []
        scenes_metadata: list[dict[str, Any]] = []
        srt_subtitles: list[str] = []

        # 1. Attempt LLM generation
        llm_prompt = self.build_prompt(
            retrieved_chunks=retrieved_chunks,
            params=params,
            extra_instructions=(
                f"Write a 4-scene voiceover narration for {params.audience}, exactly 4 scenes separated by blank "
                "lines, no scene labels or camera directions in the text:\n\n"
                "Scene 1 — Opening: establish the context and why it matters, from the source material.\n"
                "Scene 2 — Problem/Challenge: the operational or technical challenge described in the source material.\n"
                "Scene 3 — Mechanism: how the system or approach addresses it, per the source material.\n"
                f"Scene 4 — Outcome & Close: the result or current status, plus a closing line for {params.audience} — "
                "only state an outcome if the source material actually describes one.\n\n"
                f"Each scene: 1-2 fluent sentences, written to be read aloud. Tone: '{params.tone}'."
            ),
        )
        llm_text = await self.generate_with_llm(prompt=llm_prompt, max_tokens=500, temperature=0.4)

        narrations: list[str] = []
        if llm_text:
            lines = [re.sub(r"^(Scene\s*\d+:?|\d+[.)])\s*", "", l.strip()) for l in llm_text.splitlines() if len(l.strip()) > 20]
            if len(lines) >= 2:
                narrations = lines[:4]

        sent_counter = 0
        total_duration = 0.0

        if len(narrations) >= 2:
            num_scenes = min(len(narrations), len(scene_configs))
            for i in range(num_scenes):
                scene_title, scene_visual, visual_rec = scene_configs[i]
                narration = narrations[i]
                target_chunk = retrieved_chunks[min(i, len(retrieved_chunks) - 1)]

                duration = max(len(narration.split()) / 2.5, 6.0)
                start_ts = total_duration
                end_ts = total_duration + duration
                total_duration = end_ts

                cit = CitationLinker.link_sentence(narration, retrieved_chunks, raw_text, target_chunk.chunk_id)

                sent = GroundedSentence(
                    sentence_id=f"scene_{i+1}_narration",
                    sentence_index=sent_counter,
                    text=narration,
                    citations=[cit],
                )
                sent_counter += 1

                blocks.append(
                    GroundedBlock(
                        block_index=i,
                        title=scene_title,
                        sentences=[sent],
                    )
                )

                start_srt = self._format_srt_timestamp(start_ts)
                end_srt = self._format_srt_timestamp(end_ts)
                srt_subtitles.append(f"{i+1}\n{start_srt} --> {end_srt}\n{narration}\n")

                scenes_metadata.append({
                    "scene_number": i + 1,
                    "title": scene_title,
                    "narration_text": narration,
                    "duration_seconds": round(duration, 1),
                    "timestamp_start": round(start_ts, 1),
                    "timestamp_end": round(end_ts, 1),
                    "scene_description": scene_visual,
                    "visual_recommendation": visual_rec,
                    "source_chunk_index": target_chunk.chunk_index,
                })
        else:
            # Deterministic fallback synthesis using clean extracted sentences
            num_scenes = min(4, max(2, len(retrieved_chunks)))
            for i in range(num_scenes):
                scene_title, scene_visual, visual_rec = scene_configs[i]
                chunk = retrieved_chunks[min(i, len(retrieved_chunks) - 1)]

                clean_text = self.extract_clean_sentence(chunk.text, f"operational phase {i+1}")
                if i == 0:
                    narration = f"In mission-critical defense environments, operational continuity hinges on robust intelligence: {clean_text}"
                elif i == num_scenes - 1:
                    narration = f"Decisive operational readiness demands uncompromising standards: {clean_text}"
                else:
                    narration = f"Core operational integrity is maintained through structured protocols: {clean_text}"

                duration = max(len(narration.split()) / 2.5, 6.0)
                start_ts = total_duration
                end_ts = total_duration + duration
                total_duration = end_ts

                cit = CitationLinker.link_sentence(narration, retrieved_chunks, raw_text, chunk.chunk_id)

                sent = GroundedSentence(
                    sentence_id=f"scene_{i+1}_narration",
                    sentence_index=sent_counter,
                    text=narration,
                    citations=[cit],
                )
                sent_counter += 1

                blocks.append(
                    GroundedBlock(
                        block_index=i,
                        title=scene_title,
                        sentences=[sent],
                    )
                )

                start_srt = self._format_srt_timestamp(start_ts)
                end_srt = self._format_srt_timestamp(end_ts)
                srt_subtitles.append(f"{i+1}\n{start_srt} --> {end_srt}\n{narration}\n")

                scenes_metadata.append({
                    "scene_number": i + 1,
                    "title": scene_title,
                    "narration_text": narration,
                    "duration_seconds": round(duration, 1),
                    "timestamp_start": round(start_ts, 1),
                    "timestamp_end": round(end_ts, 1),
                    "scene_description": scene_visual,
                    "visual_recommendation": visual_rec,
                    "source_chunk_index": chunk.chunk_index,
                })

        title = f"Video Production Package: {retrieved_chunks[0].heading or 'Strategic Briefing'}"
        content = GroundedDeliverableContent(
            title=title,
            summary=f"Full {len(blocks)}-scene video production package with voiceover narration, storyboard visual direction, and timecoded SRT subtitles.",
            blocks=blocks,
        )

        format_metadata = {
            "media_type": "Video Package (Non-rendered metadata & script)",
            "total_scenes": len(blocks),
            "total_estimated_duration_seconds": round(total_duration, 1),
            "aspect_ratio": "16:9",
            "scenes": scenes_metadata,
            "subtitles_srt": "\n".join(srt_subtitles),
        }

        return AdapterOutput(
            content=content,
            format_metadata=format_metadata,
            requires_human_review=self.requires_human_review,
        )

    @staticmethod
    def _format_srt_timestamp(seconds: float) -> str:
        """Format seconds into HH:MM:SS,mmm SRT format."""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"
