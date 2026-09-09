"""Entity, Topic, Intent, and Sensitive Terms Extractor for Phase 2.

Extracts:
1. Key entities (ORGANIZATION, PERSON, LOCATION, TACTIC_TECHNIQUE, WEAPON_SYSTEM, DEFENSE_PROGRAM, DATE_TIME)
2. Document stated objective / intent
3. Thematic topics
4. Sensitive terms for advisory/defense inputs (Classification, CVEs, Threat levels)
5. Entity co-occurrence and semantic relationships grounded in chunk_ids

Operates completely offline with zero external network calls.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.schemas.understanding import (
    EntityMention,
    EntityRelationship,
    SensitiveTerm,
)
from app.services.chunking.semantic_chunker import ExtractedChunk

logger = logging.getLogger("app.services.extraction")


@dataclass
class ExtractionResult:
    """Internal container for document understanding extraction."""

    objective: str
    topics: list[str]
    key_entities: list[EntityMention]
    sensitive_terms: list[SensitiveTerm]
    relationships: list[EntityRelationship]
    summary: str


class EntityExtractor:
    """Extracts entities, topics, intent, sensitive terms, and graph relationships."""

    # Defense, Aerospace, Tech, and Government Organizations
    KNOWN_ORGS = {
        "NATO", "DARPA", "ISRO", "DRDO", "NASA", "DOD", "MOD", "IAF", "INDIAN AIR FORCE",
        "INDIAN NAVY", "INDIAN ARMY", "USAF", "US NAVY", "LOCKHEED MARTIN", "BOEING",
        "RAYTHEON", "NORTHROP GRUMMAN", "BAE SYSTEMS", "THALES", "AIRBUS", "DASSAULT",
        "CERT-IN", "CISA", "NSA", "FBI", "RAW", "IB", "MICROSOFT", "GOOGLE", "AMAZON",
        "APPLE", "NVIDIA", "PALANTIR", "ANDURIL", "CROWDSTRIKE", "MANDIANT",
    }

    # Weapon Systems & Defense Programs
    KNOWN_SYSTEMS = {
        "RAFALE", "SU-30MKI", "TEJAS", "F-35", "F-22", "S-400", "S-500", "PATRIOT",
        "IRON DOME", "BRAHMOS", "AGNI-V", "PRITHVI", "MQ-9 REAPER", "MQ-9B", "PREDATOR",
        "HERON TP", "BAYRAKTAR TB2", "AEGIS", "HARPOON", "TOMAHAWK", "JAVELIN",
        "HIMARS", "LEOPARD 2", "ABRAMS", "T-90", "INS VIKRANT", "INS ARIHANT",
    }

    # Tactical & Cybersecurity Techniques
    KNOWN_TACTICS = {
        "PHISHING", "SPEAR PHISHING", "LATERAL MOVEMENT", "CREDENTIAL DUMPING",
        "PRIVILEGE ESCALATION", "ZERO-DAY EXPLOIT", "REMOTE CODE EXECUTION", "RCE",
        "SQL INJECTION", "CROSS-SITE SCRIPTING", "DENIAL OF SERVICE", "DDOS",
        "MAN-IN-THE-MIDDLE", "GPS SPOOFING", "ELECTRONIC JAMMING", "RADAR COUNTERMEASURES",
        "DRONE SWARM", "SATCOM INTERCEPTION", "AIR-GAP JUMPING", "RANSOMWARE",
    }

    # Strategic & Geopolitical Locations
    KNOWN_LOCATIONS = {
        "LADAKH", "SOUTH CHINA SEA", "TAIWAN STRAIT", "INDO-PACIFIC", "ARCTIC",
        "NEW DELHI", "WASHINGTON", "BEIJING", "MOSCOW", "LONDON", "TOKYO", "SEOUL",
        "KYIV", "CRIMEA", "PERSIAN GULF", "STRAIT OF HORMUZ", "MALACCA STRAIT",
        "DIEGO GARCIA", "ANDAMAN AND NICOBAR", "LINE OF ACTUAL CONTROL", "LAC", "LOC",
    }

    # Classification & Advisory Markers
    SENSITIVE_PATTERNS = [
        (r"\b(TOP\s+SECRET|SECRET|CONFIDENTIAL|RESTRICTED|NOFORN|SECRET//NOFORN)\b", "CLASSIFICATION", "CRITICAL", "Document or section bears national defense classification markings."),
        (r"\b(CVE-\d{4}-\d{4,})\b", "CYBER_VULNERABILITY", "CRITICAL", "Identified Common Vulnerabilities and Exposures code subject to active advisory."),
        (r"\b(CRITICAL\s+VULNERABILITY|ZERO-DAY|ACTIVE\s+EXPLOITATION|REMOTE\s+CODE\s+EXECUTION|UNAUTHENTICATED\s+RCE)\b", "CYBER_VULNERABILITY", "HIGH", "High-severity cyber threat vector requiring mitigation."),
        (r"\b(CBRN|CHEMICAL\s+WEAPON|BIOLOGICAL\s+AGENT|RADIOLOGICAL|NUCLEAR\s+WARHEAD)\b", "CBRN", "CRITICAL", "CBRN (Chemical, Biological, Radiological, Nuclear) strategic risk terminology."),
        (r"\b(ITAR|EXPORT\s+CONTROLLED|EAR99|DEFENSE\s+ARTICLE)\b", "EXPORT_CONTROL", "HIGH", "International Traffic in Arms Regulations or dual-use export control restriction."),
        (r"\b(DEFCON\s+[1-5]|FORCE\s+PROTECTION\s+CONDITION|THREATCON)\b", "OPERATIONAL_SECURITY", "HIGH", "Military readiness alert condition or defense readiness posture."),
    ]

    def extract(
        self,
        raw_text: str,
        chunks: list[ExtractedChunk],
        structural_metadata: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        """Run full extraction over document and grounded chunks."""
        # 1. Objective / Intent Extraction
        objective = self._extract_stated_objective(raw_text, structural_metadata)

        # 2. Topic Categorization
        topics = self._extract_topics(raw_text)

        # 3. Entity Extraction grounded in chunks
        entities = self._extract_entities_grounded(raw_text, chunks)

        # 4. Sensitive Advisory Terms grounded in chunks
        sensitive_terms = self._extract_sensitive_terms_grounded(raw_text, chunks)

        # 5. Entity Relationships & Co-occurrences
        relationships = self._extract_relationships(chunks, entities)

        # 6. Executive Summary
        summary = self._generate_summary(raw_text, objective, topics, entities)

        return ExtractionResult(
            objective=objective,
            topics=topics,
            key_entities=entities,
            sensitive_terms=sensitive_terms,
            relationships=relationships,
            summary=summary,
        )

    def _extract_stated_objective(
        self, raw_text: str, metadata: dict[str, Any] | None
    ) -> str:
        """Extract primary stated purpose or mission objective of the document."""
        # Look for explicit objective headings or introductory declarations
        objective_patterns = [
            r"(?:OBJECTIVE|PURPOSE|MISSION|EXECUTIVE SUMMARY|SCOPE)[:\s-]+\s*([^\n\.\r]{20,300}[\.\n])",
            r"(?:This document (?:defines|specifies|details|outlines|establishes|proposes))\s+([^\n\.\r]{20,300}[\.\n])",
            r"(?:The primary goal of this (?:system|protocol|operation|advisory) is to)\s+([^\n\.\r]{20,300}[\.\n])",
            r"(?:In response to|To address|In order to)\s+([^\n\.\r]{20,300}[\.\n])",
        ]

        for pat in objective_patterns:
            m = re.search(pat, raw_text, re.IGNORECASE)
            if m:
                clean = m.group(1).strip().replace("\n", " ")
                return f"Stated Objective: {clean}"

        # Fallback to first non-heading sentence
        lines = [line.strip() for line in raw_text.split("\n") if line.strip() and not line.startswith(("#", "---", "="))]
        if lines:
            first_para = lines[0]
            if len(first_para) > 15:
                return f"Primary Focus: {first_para[:200].strip()}..."

        return "Operational analysis and content transformation mandate."

    def _extract_topics(self, raw_text: str) -> list[str]:
        """Classify document topics based on domain lexicon."""
        text_lower = raw_text.lower()
        topic_rules = [
            ("Air Defense & Aerospace", ["radar", "aircraft", "rafale", "fighter", "air defense", "airspace", "s-400", "air force"]),
            ("Border Security & Surveillance", ["border", "surveillance", "patrol", "lac", "loc", "reconnaissance", "sensor", "perimeter"]),
            ("Cyber Defense & Vulnerabilities", ["cve-", "vulnerability", "malware", "exploit", "cybersecurity", "rce", "phishing", "firewall"]),
            ("Autonomous & Unmanned Systems", ["drone", "uav", "unmanned", "autonomous", "swarm", "payload", "reaper", "robotics"]),
            ("Maritime & Naval Operations", ["naval", "navy", "vessel", "submarine", "maritime", "corvette", "frigate", "strait"]),
            ("Communications & Electronic Warfare", ["jamming", "satcom", "frequency", "electronic warfare", "sigint", "telemetry", "rf"]),
            ("Strategic Policy & Advisory", ["advisory", "defense", "ministry", "compliance", "itar", "directive", "protocol"]),
            ("Logistics & Supply Chain", ["procurement", "supply chain", "depot", "logistics", "maintenance", "inventory"]),
        ]

        detected_topics: list[str] = []
        for topic_name, keywords in topic_rules:
            count = sum(text_lower.count(kw) for kw in keywords)
            if count >= 2 or (count >= 1 and len(keywords) <= 4):
                detected_topics.append(topic_name)

        if not detected_topics:
            detected_topics.append("General Defense & Security Intelligence")

        return detected_topics

    def _extract_entities_grounded(
        self, raw_text: str, chunks: list[ExtractedChunk]
    ) -> list[EntityMention]:
        """Extract structured named entities and ground them in matching chunk IDs."""
        found_entities: dict[tuple[str, str], list[uuid.UUID]] = {}

        # 1. Match known domain catalogs
        catalog_mappings = [
            (self.KNOWN_ORGS, "ORGANIZATION"),
            (self.KNOWN_SYSTEMS, "WEAPON_SYSTEM"),
            (self.KNOWN_TACTICS, "TACTIC_TECHNIQUE"),
            (self.KNOWN_LOCATIONS, "LOCATION"),
        ]

        for chunk in chunks:
            chunk_upper = chunk.text.upper()
            for catalog, ent_type in catalog_mappings:
                for entry in catalog:
                    # Match whole word
                    pattern = rf"\b{re.escape(entry)}\b"
                    if re.search(pattern, chunk_upper):
                        key = (entry.title(), ent_type)
                        found_entities.setdefault(key, []).append(chunk.chunk_id)

            # 2. Extract capitalized proper nouns (People / Program names)
            for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", chunk.text):
                phrase = m.group(1).strip()
                phrase_upper = phrase.upper()
                # Exclude common sentence starters or phrases matching known catalogs
                if phrase.lower() in {"the following", "in order", "for example", "as stated", "in accordance", "key weapon", "additionally the", "for autonomous"}:
                    continue
                if any(phrase_upper == k or phrase_upper.startswith(k) or k in phrase_upper for cat, _ in catalog_mappings for k in cat):
                    continue
                if any(phrase.title() == existing_name for existing_name, _ in found_entities):
                    continue
                if len(phrase) > 4:
                    key = (phrase, "PERSON")
                    found_entities.setdefault(key, []).append(chunk.chunk_id)

            # 3. Extract dates / operational periods
            for m in re.finditer(r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|Q[1-4]\s+\d{4})\b", chunk.text, re.IGNORECASE):
                key = (m.group(1).strip(), "DATE_TIME")
                found_entities.setdefault(key, []).append(chunk.chunk_id)

        # Build final EntityMention objects
        entities_list: list[EntityMention] = []
        for (name, ent_type), chunk_id_list in found_entities.items():
            unique_chunks = list(dict.fromkeys(chunk_id_list))
            entities_list.append(
                EntityMention(
                    name=name,
                    type=ent_type,
                    count=len(chunk_id_list),
                    chunk_ids=unique_chunks,
                )
            )

        # Sort by mention frequency descending
        entities_list.sort(key=lambda x: x.count, reverse=True)
        return entities_list[:40]

    def _extract_sensitive_terms_grounded(
        self, raw_text: str, chunks: list[ExtractedChunk]
    ) -> list[SensitiveTerm]:
        """Detect sensitive indicators, classification codes, and CVEs, mapped to chunk IDs."""
        detected_map: dict[str, dict[str, Any]] = {}

        for chunk in chunks:
            for pattern, category, severity, reason in self.SENSITIVE_PATTERNS:
                for match in re.finditer(pattern, chunk.text, re.IGNORECASE):
                    term = match.group(1).strip().upper()
                    if term not in detected_map:
                        detected_map[term] = {
                            "category": category,
                            "severity": severity,
                            "reason": reason,
                            "chunks": [chunk.chunk_id],
                        }
                    else:
                        if chunk.chunk_id not in detected_map[term]["chunks"]:
                            detected_map[term]["chunks"].append(chunk.chunk_id)

        results: list[SensitiveTerm] = []
        for term, data in detected_map.items():
            results.append(
                SensitiveTerm(
                    term=term,
                    category=data["category"],
                    severity=data["severity"],
                    chunk_ids=data["chunks"],
                    reason=data["reason"],
                )
            )

        # Sort by severity (CRITICAL > HIGH > MEDIUM > LOW)
        sev_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}
        results.sort(key=lambda x: sev_rank.get(x.severity, 5))
        return results

    def _extract_relationships(
        self, chunks: list[ExtractedChunk], entities: list[EntityMention]
    ) -> list[EntityRelationship]:
        """Extract entity relationship tuples grounded in chunk IDs."""
        relationships: list[EntityRelationship] = []
        seen_triples: set[tuple[str, str, str]] = set()

        # Build lookup from chunk_id -> list of entity names in that chunk
        chunk_entity_map: dict[uuid.UUID, list[EntityMention]] = {}
        for ent in entities:
            for c_id in ent.chunk_ids:
                chunk_entity_map.setdefault(c_id, []).append(ent)

        for chunk in chunks:
            ents_in_chunk = chunk_entity_map.get(chunk.chunk_id, [])
            if len(ents_in_chunk) < 2:
                continue

            chunk_text = chunk.text

            # Co-occurrence and semantic relations
            for i in range(len(ents_in_chunk)):
                for j in range(i + 1, min(i + 4, len(ents_in_chunk))):
                    e1 = ents_in_chunk[i]
                    e2 = ents_in_chunk[j]

                    if e1.name == e2.name:
                        continue

                    # Infer relation based on entity types and text context
                    rel_type = self._infer_relation_type(e1, e2, chunk_text)
                    triple = (e1.name, rel_type, e2.name)

                    if triple not in seen_triples:
                        seen_triples.add(triple)
                        relationships.append(
                            EntityRelationship(
                                source=e1.name,
                                relation=rel_type,
                                target=e2.name,
                                chunk_id=chunk.chunk_id,
                                confidence=0.92,
                            )
                        )

        return relationships[:50]

    def _infer_relation_type(
        self, e1: EntityMention, e2: EntityMention, context: str
    ) -> str:
        """Infer relation predicate between two entities."""
        ctx_lower = context.lower()

        if e1.type == "WEAPON_SYSTEM" and e2.type == "ORGANIZATION":
            return "OPERATED_BY"
        if e1.type == "ORGANIZATION" and e2.type == "WEAPON_SYSTEM":
            return "DEPLOYS"
        if (e1.type == "WEAPON_SYSTEM" or e1.type == "ORGANIZATION") and e2.type == "LOCATION":
            return "STATIONED_AT"
        if e1.type == "TACTIC_TECHNIQUE" and (e2.type == "WEAPON_SYSTEM" or e2.type == "ORGANIZATION"):
            return "TARGETS"
        if "cooperat" in ctx_lower or "joint" in ctx_lower or "partner" in ctx_lower:
            return "COLLABORATES_WITH"
        if "deploy" in ctx_lower or "station" in ctx_lower:
            return "DEPLOYED_WITH"

        return "CO_OCCURS_WITH"

    def _generate_summary(
        self,
        raw_text: str,
        objective: str,
        topics: list[str],
        entities: list[EntityMention],
    ) -> str:
        """Synthesize high-level abstract of document."""
        top_ents = [e.name for e in entities[:5]]
        ent_str = ", ".join(top_ents) if top_ents else "key defense entities"
        topic_str = ", ".join(topics[:3])

        return (
            f"Document encompasses {topic_str}. {objective} "
            f"Key focal entities include: {ent_str}. "
            f"Character length: {len(raw_text)} chars across grounded semantic units."
        )


_extractor_instance: EntityExtractor | None = None


def get_entity_extractor() -> EntityExtractor:
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = EntityExtractor()
    return _extractor_instance
