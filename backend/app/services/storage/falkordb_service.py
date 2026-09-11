"""FalkorDB Knowledge Graph Service for Phase 2.

Manages openCypher property graph operations on FalkorDB / Redis Graph:
- (:Document) nodes
- (:Chunk) nodes linked to document
- (:Entity) nodes with categorized types
- (:Topic) nodes
- [:HAS_CHUNK], [:MENTIONS], [:RELATION], [:CO_OCCURS_WITH], [:HAS_TOPIC] edges

Features an in-memory graph index fallback for test suites and offline enclaves.
"""

import logging
import uuid
from typing import Any

from app.core.config import get_settings
from app.core.falkordb_client import get_redis_client
from app.schemas.understanding import (
    EntityGraphQueryResponse,
    EntityMention,
    EntityRelationship,
    GraphEdge,
    GraphNode,
    GraphVisualizationResponse,
)
from app.services.chunking.semantic_chunker import ExtractedChunk

logger = logging.getLogger("app.services.storage.falkordb")
settings = get_settings()


class FalkorDBService:
    """Service wrapper for FalkorDB graph operations with Cypher execution and memory fallback."""

    def __init__(self, graph_name: str | None = None) -> None:
        self.graph_name = graph_name or settings.FALKORDB_GRAPH_DEFAULT
        # In-memory graph representation: nodes: id -> dict, edges: list of dict
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []
        self._live_available: bool | None = None

    async def _is_live(self) -> bool:
        """Check if live FalkorDB / Redis container is reachable via fast non-blocking probe."""
        from app.core.falkordb_client import is_falkordb_live
        if self._live_available is not None:
            return self._live_available
        self._live_available = is_falkordb_live(timeout=0.15)
        return self._live_available

    async def upsert_document_graph(
        self,
        doc_id: uuid.UUID,
        filename: str,
        chunks: list[ExtractedChunk],
        entities: list[EntityMention],
        relationships: list[EntityRelationship],
        topics: list[str],
    ) -> bool:
        """Upsert complete document graph topology into FalkorDB and memory index."""
        # 1. Update In-Memory Graph Index
        doc_str = str(doc_id)
        doc_node_id = f"doc_{doc_str}"

        # Purge any previously indexed edges for this doc to prevent edge accumulation
        self._edges = [
            e for e in self._edges
            if e.get("properties", {}).get("doc_id") != doc_str
            and e.get("source") != doc_node_id
            and e.get("target") != doc_node_id
        ]

        self._nodes[doc_node_id] = {
            "id": doc_node_id,
            "label": filename,
            "type": "Document",
            "properties": {"doc_id": doc_str, "filename": filename},
        }

        # Topics
        for topic in topics:
            t_id = f"topic_{topic}"
            self._nodes[t_id] = {
                "id": t_id,
                "label": topic,
                "type": "Topic",
                "properties": {"name": topic},
            }
            self._edges.append({
                "source": doc_node_id,
                "target": t_id,
                "relation": "HAS_TOPIC",
                "properties": {"doc_id": doc_str},
            })

        # Chunks
        chunk_node_map: dict[uuid.UUID, str] = {}
        for chunk in chunks:
            c_str = str(chunk.chunk_id)
            c_node_id = f"chunk_{c_str}"
            chunk_node_map[chunk.chunk_id] = c_node_id
            self._nodes[c_node_id] = {
                "id": c_node_id,
                "label": f"Chunk {chunk.chunk_index}",
                "type": "Chunk",
                "properties": {
                    "chunk_id": c_str,
                    "doc_id": doc_str,
                    "chunk_index": chunk.chunk_index,
                    "char_start": chunk.char_offset_start,
                    "char_end": chunk.char_offset_end,
                    "preview": chunk.text[:120],
                },
            }
            self._edges.append({
                "source": doc_node_id,
                "target": c_node_id,
                "relation": "HAS_CHUNK",
                "properties": {"doc_id": doc_str, "chunk_index": chunk.chunk_index},
            })

        # Sequential Chunk Links: (Chunk i)-[:NEXT_CHUNK]->(Chunk i+1)
        sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)
        for idx in range(len(sorted_chunks) - 1):
            c_curr_id = chunk_node_map[sorted_chunks[idx].chunk_id]
            c_next_id = chunk_node_map[sorted_chunks[idx + 1].chunk_id]
            self._edges.append({
                "source": c_curr_id,
                "target": c_next_id,
                "relation": "NEXT_CHUNK",
                "properties": {
                    "doc_id": doc_str,
                    "from_index": sorted_chunks[idx].chunk_index,
                    "to_index": sorted_chunks[idx + 1].chunk_index,
                },
            })

        # Entities
        entity_node_map: dict[str, str] = {}
        for ent in entities:
            e_node_id = f"entity_{ent.name}"
            entity_node_map[ent.name] = e_node_id
            self._nodes[e_node_id] = {
                "id": e_node_id,
                "label": ent.name,
                "type": "Entity",
                "properties": {"name": ent.name, "entity_type": ent.type, "count": ent.count},
            }
            # Connect chunk -> entity mentions
            for c_id in ent.chunk_ids:
                if c_id in chunk_node_map:
                    self._edges.append({
                        "source": chunk_node_map[c_id],
                        "target": e_node_id,
                        "relation": "MENTIONS",
                        "properties": {"doc_id": doc_str, "chunk_id": str(c_id)},
                    })

        # Inter-Chunk Semantic Relationships via Shared Entities (deduplicated per chunk pair)
        seen_chunk_shares: set[tuple[str, str]] = set()
        for ent in entities:
            valid_cids = [chunk_node_map[cid] for cid in ent.chunk_ids if cid in chunk_node_map]
            for i in range(len(valid_cids)):
                for j in range(i + 1, min(i + 3, len(valid_cids))):
                    pair = (valid_cids[i], valid_cids[j])
                    rev = (valid_cids[j], valid_cids[i])
                    if pair not in seen_chunk_shares and rev not in seen_chunk_shares:
                        seen_chunk_shares.add(pair)
                        self._edges.append({
                            "source": valid_cids[i],
                            "target": valid_cids[j],
                            "relation": "SHARES_ENTITY",
                            "properties": {
                                "doc_id": doc_str,
                                "entity": ent.name,
                                "entity_type": ent.type,
                            },
                        })

        # Relationships
        for rel in relationships:
            src_node = entity_node_map.get(rel.source)
            tgt_node = entity_node_map.get(rel.target)
            if src_node and tgt_node:
                self._edges.append({
                    "source": src_node,
                    "target": tgt_node,
                    "relation": rel.relation,
                    "properties": {
                        "chunk_id": str(rel.chunk_id) if rel.chunk_id else None,
                        "confidence": rel.confidence,
                        "doc_id": doc_str,
                    },
                })

        # Inter-Chunk Semantic Bridges via Entity Relationships (deduplicated per chunk pair)
        seen_chunk_bridges: set[tuple[str, str]] = set()
        ent_chunks_map: dict[str, set[str]] = {}
        for ent in entities:
            ent_chunks_map[ent.name] = {
                chunk_node_map[cid] for cid in ent.chunk_ids if cid in chunk_node_map
            }

        for rel in relationships:
            src_chunks = ent_chunks_map.get(rel.source, set())
            tgt_chunks = ent_chunks_map.get(rel.target, set())
            for sc in src_chunks:
                for tc in tgt_chunks:
                    if sc != tc:
                        pair = (sc, tc)
                        rev = (tc, sc)
                        if pair not in seen_chunk_bridges and rev not in seen_chunk_bridges:
                            seen_chunk_bridges.add(pair)
                            self._edges.append({
                                "source": sc,
                                "target": tc,
                                "relation": "CROSS_CHUNK_RELATION",
                                "properties": {
                                    "doc_id": doc_str,
                                    "source_entity": rel.source,
                                    "target_entity": rel.target,
                                    "relation": rel.relation,
                                },
                            })

        # 2. Synchronize to Live FalkorDB if reachable
        is_live = await self._is_live()
        if not is_live:
            logger.debug("FalkorDB not connected. Document graph cached in memory index.")
            return True

        client = get_redis_client()
        try:
            # Upsert Document node
            escaped_fn = filename.replace("'", "\\'")
            cypher_doc = f"MERGE (d:Document {{id: '{doc_str}'}}) SET d.filename = '{escaped_fn}'"
            await client.execute_command("GRAPH.QUERY", self.graph_name, cypher_doc)

            # Upsert Topics
            for topic in topics:
                esc_top = topic.replace("'", "\\'")
                cypher_topic = (
                    f"MERGE (t:Topic {{name: '{esc_top}'}}) "
                    f"WITH t MATCH (d:Document {{id: '{doc_str}'}}) "
                    f"MERGE (d)-[:HAS_TOPIC]->(t)"
                )
                await client.execute_command("GRAPH.QUERY", self.graph_name, cypher_topic)

            # Upsert Chunks
            for chunk in chunks:
                c_str = str(chunk.chunk_id)
                esc_prev = chunk.text[:80].replace("'", "\\'").replace("\n", " ")
                cypher_chunk = (
                    f"MERGE (c:Chunk {{id: '{c_str}'}}) "
                    f"SET c.doc_id = '{doc_str}', c.chunk_index = {chunk.chunk_index}, c.preview = '{esc_prev}' "
                    f"WITH c MATCH (d:Document {{id: '{doc_str}'}}) "
                    f"MERGE (d)-[:HAS_CHUNK]->(c)"
                )
                await client.execute_command("GRAPH.QUERY", self.graph_name, cypher_chunk)

            # Upsert Entities & Mentions
            for ent in entities:
                esc_name = ent.name.replace("'", "\\'")
                esc_type = ent.type.replace("'", "\\'")
                cypher_ent = (
                    f"MERGE (e:Entity {{name: '{esc_name}'}}) "
                    f"SET e.type = '{esc_type}'"
                )
                await client.execute_command("GRAPH.QUERY", self.graph_name, cypher_ent)

                for c_id in ent.chunk_ids:
                    c_str = str(c_id)
                    cypher_mention = (
                        f"MATCH (c:Chunk {{id: '{c_str}'}}), (e:Entity {{name: '{esc_name}'}}) "
                        f"MERGE (c)-[:MENTIONS]->(e)"
                    )
                    await client.execute_command("GRAPH.QUERY", self.graph_name, cypher_mention)

            # Upsert Relationships
            for rel in relationships:
                esc_s = rel.source.replace("'", "\\'")
                esc_t = rel.target.replace("'", "\\'")
                esc_r = rel.relation.replace("'", "\\'")
                c_prop = f", chunk_id: '{rel.chunk_id}'" if rel.chunk_id else ""
                cypher_rel = (
                    f"MATCH (s:Entity {{name: '{esc_s}'}}), (t:Entity {{name: '{esc_t}'}}) "
                    f"MERGE (s)-[:RELATION {{relation: '{esc_r}'{c_prop}}}]->(t)"
                )
                await client.execute_command("GRAPH.QUERY", self.graph_name, cypher_rel)

            # Upsert Inter-Chunk Sequential NEXT_CHUNK edges
            for idx in range(len(sorted_chunks) - 1):
                c1_id = str(sorted_chunks[idx].chunk_id)
                c2_id = str(sorted_chunks[idx + 1].chunk_id)
                cypher_next = (
                    f"MATCH (c1:Chunk {{id: '{c1_id}'}}), (c2:Chunk {{id: '{c2_id}'}}) "
                    f"MERGE (c1)-[:NEXT_CHUNK {{doc_id: '{doc_str}', from_index: {sorted_chunks[idx].chunk_index}, to_index: {sorted_chunks[idx + 1].chunk_index}}}]->(c2)"
                )
                await client.execute_command("GRAPH.QUERY", self.graph_name, cypher_next)

            # Upsert Inter-Chunk SHARES_ENTITY edges (deduplicated)
            seen_cypher_shares: set[tuple[str, str]] = set()
            for ent in entities:
                esc_ent = ent.name.replace("'", "\\'")
                valid_cids = [str(cid) for cid in ent.chunk_ids if cid in chunk_node_map]
                for i in range(len(valid_cids)):
                    for j in range(i + 1, min(i + 3, len(valid_cids))):
                        c_pair = (valid_cids[i], valid_cids[j])
                        rev_c_pair = (valid_cids[j], valid_cids[i])
                        if c_pair not in seen_cypher_shares and rev_c_pair not in seen_cypher_shares:
                            seen_cypher_shares.add(c_pair)
                            cypher_se = (
                                f"MATCH (c1:Chunk {{id: '{valid_cids[i]}'}}), (c2:Chunk {{id: '{valid_cids[j]}'}}) "
                                f"MERGE (c1)-[:SHARES_ENTITY {{doc_id: '{doc_str}', entity: '{esc_ent}'}}]->(c2)"
                            )
                            await client.execute_command("GRAPH.QUERY", self.graph_name, cypher_se)

            # Upsert Inter-Chunk CROSS_CHUNK_RELATION edges (deduplicated)
            seen_cypher_bridges: set[tuple[str, str]] = set()
            raw_ent_chunks: dict[str, set[str]] = {}
            for ent in entities:
                raw_ent_chunks[ent.name] = {
                    str(cid) for cid in ent.chunk_ids if cid in chunk_node_map
                }
            for rel in relationships:
                esc_rel = rel.relation.replace("'", "\\'")
                s_chunks = raw_ent_chunks.get(rel.source, set())
                t_chunks = raw_ent_chunks.get(rel.target, set())
                for sc in s_chunks:
                    for tc in t_chunks:
                        if sc != tc:
                            b_pair = (sc, tc)
                            rev_b_pair = (tc, sc)
                            if b_pair not in seen_cypher_bridges and rev_b_pair not in seen_cypher_bridges:
                                seen_cypher_bridges.add(b_pair)
                                cypher_ccr = (
                                    f"MATCH (c1:Chunk {{id: '{sc}'}}), (c2:Chunk {{id: '{tc}'}}) "
                                    f"MERGE (c1)-[:CROSS_CHUNK_RELATION {{doc_id: '{doc_str}', relation: '{esc_rel}'}}]->(c2)"
                                )
                                await client.execute_command("GRAPH.QUERY", self.graph_name, cypher_ccr)

            logger.info("Successfully upserted document graph topology to FalkorDB for doc %s", doc_id)
            return True
        except Exception as exc:
            logger.warning("FalkorDB Cypher execution failed (%s). Kept in memory graph index.", exc)
            return False
        finally:
            await client.aclose()

    async def query_entity_graph(self, entity_name: str) -> EntityGraphQueryResponse:
        """Query knowledge graph for an entity, its relations, and grounding chunk IDs."""
        normalized_name = entity_name.strip()

        # 1. Try live FalkorDB query first if available
        if await self._is_live():
            client = get_redis_client()
            try:
                esc_name = normalized_name.replace("'", "\\'")
                query = (
                    f"MATCH (e:Entity) WHERE toLower(e.name) = toLower('{esc_name}') "
                    f"OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(e) "
                    f"OPTIONAL MATCH (e)-[r:RELATION]-(other:Entity) "
                    f"RETURN e.name, e.type, c.id, other.name, r.relation, other.type"
                )
                raw_res = await client.execute_command("GRAPH.QUERY", self.graph_name, query)
                if raw_res and len(raw_res) > 1 and raw_res[1]:
                    # Parse FalkorDB tabular response
                    entity_type = "UNKNOWN"
                    referenced_chunks: set[uuid.UUID] = set()
                    connected_entities: dict[str, dict[str, Any]] = {}
                    direct_relations: list[dict[str, Any]] = []

                    for row in raw_res[1]:
                        if len(row) >= 2:
                            normalized_name = str(row[0])
                            entity_type = str(row[1])
                        if len(row) >= 3 and row[2]:
                            try:
                                referenced_chunks.add(uuid.UUID(str(row[2])))
                            except ValueError:
                                pass
                        if len(row) >= 5 and row[3] and row[4]:
                            other_name = str(row[3])
                            rel_name = str(row[4])
                            other_type = str(row[5]) if len(row) >= 6 and row[5] else "Entity"
                            connected_entities[other_name] = {"name": other_name, "type": other_type}
                            direct_relations.append({"target": other_name, "relation": rel_name})

                    return EntityGraphQueryResponse(
                        entity_name=normalized_name,
                        entity_type=entity_type,
                        connected_entities=list(connected_entities.values()),
                        referenced_chunks=list(referenced_chunks),
                        direct_relations=direct_relations,
                    )
            except Exception as exc:
                logger.warning("FalkorDB query failed (%s). Falling back to memory index.", exc)
            finally:
                await client.aclose()

        # 2. In-Memory Graph Index Query
        # Find matching node (case-insensitive)
        matched_node = None
        for _n_id, n_data in self._nodes.items():
            if n_data["type"] == "Entity" and n_data["properties"].get("name", "").lower() == normalized_name.lower():
                matched_node = n_data
                break

        if not matched_node:
            return EntityGraphQueryResponse(
                entity_name=normalized_name,
                entity_type="UNKNOWN",
                connected_entities=[],
                referenced_chunks=[],
                direct_relations=[],
            )

        ent_props = matched_node["properties"]
        target_name = ent_props.get("name", normalized_name)
        ent_type = ent_props.get("entity_type", "ENTITY")
        curr_node_id = matched_node["id"]

        referenced_chunks_set: set[uuid.UUID] = set()
        connected_dict: dict[str, dict[str, Any]] = {}
        direct_relations_list: list[dict[str, Any]] = []

        for edge in self._edges:
            # Check Chunk -> Entity mentions
            if edge["target"] == curr_node_id and edge["relation"] == "MENTIONS":
                c_id_str = edge["properties"].get("chunk_id")
                if c_id_str:
                    try:
                        referenced_chunks_set.add(uuid.UUID(c_id_str))
                    except ValueError:
                        pass

            # Check Entity -> Entity relations
            if edge["source"] == curr_node_id and edge["target"] != curr_node_id:
                other = self._nodes.get(edge["target"])
                if other and other["type"] == "Entity":
                    o_name = other["properties"].get("name", "")
                    o_type = other["properties"].get("entity_type", "")
                    connected_dict[o_name] = {"name": o_name, "type": o_type}
                    direct_relations_list.append({
                        "target": o_name,
                        "relation": edge["relation"],
                        "chunk_id": edge["properties"].get("chunk_id"),
                    })

            if edge["target"] == curr_node_id and edge["source"] != curr_node_id:
                other = self._nodes.get(edge["source"])
                if other and other["type"] == "Entity":
                    o_name = other["properties"].get("name", "")
                    o_type = other["properties"].get("entity_type", "")
                    connected_dict[o_name] = {"name": o_name, "type": o_type}
                    direct_relations_list.append({
                        "source": o_name,
                        "relation": edge["relation"],
                        "chunk_id": edge["properties"].get("chunk_id"),
                    })

        return EntityGraphQueryResponse(
            entity_name=target_name,
            entity_type=ent_type,
            connected_entities=list(connected_dict.values()),
            referenced_chunks=list(referenced_chunks_set),
            direct_relations=direct_relations_list,
        )

    def get_document_graph(self, doc_id: uuid.UUID) -> GraphVisualizationResponse:
        """Return graph nodes and edges for visualization filtered by document."""
        doc_str = str(doc_id)
        doc_node_id = f"doc_{doc_str}"

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        # Find all edges belonging to this doc
        doc_edges = [
            e for e in self._edges
            if e["properties"].get("doc_id") == doc_str or e["source"] == doc_node_id or e["target"] == doc_node_id
        ]

        # Gather node IDs involved
        relevant_node_ids = {doc_node_id}
        for e in doc_edges:
            relevant_node_ids.add(e["source"])
            relevant_node_ids.add(e["target"])

        for nid in relevant_node_ids:
            n = self._nodes.get(nid)
            if n:
                nodes.append(GraphNode(
                    id=n["id"],
                    label=n["label"],
                    type=n["type"],
                    properties=n["properties"],
                ))

        for e in doc_edges:
            edges.append(GraphEdge(
                source=e["source"],
                target=e["target"],
                relation=e["relation"],
                properties=e["properties"],
            ))

        return GraphVisualizationResponse(
            doc_id=doc_id,
            nodes=nodes,
            edges=edges,
        )

    async def clear_all(self) -> bool:
        """Clear all nodes and edges from FalkorDB and in-memory index."""
        self._nodes.clear()
        self._edges.clear()
        if await self._is_live():
            from app.core.falkordb_client import get_redis_client
            client = get_redis_client()
            try:
                await client.execute_command("GRAPH.DELETE", self.graph_name)
                logger.info("FalkorDB graph '%s' deleted successfully.", self.graph_name)
                return True
            except Exception as exc:
                logger.warning("Failed to delete FalkorDB graph: %s", exc)
                return False
            finally:
                await client.aclose()
        return True


_falkordb_service_instance: FalkorDBService | None = None


def get_falkordb_service() -> FalkorDBService:
    global _falkordb_service_instance
    if _falkordb_service_instance is None:
        _falkordb_service_instance = FalkorDBService()
    return _falkordb_service_instance
