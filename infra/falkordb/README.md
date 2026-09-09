# FalkorDB Graph Store Infrastructure

## Role in Architecture
FalkorDB is a low-latency, Redis-compatible Graph Database engine designed for complex Cypher queries.
In the GenAI Content Transformation Platform, FalkorDB powers:
- **Entity-Relationship Grounding**: Mapping named entities extracted from chunks.
- **Cross-Document Linking**: Preserving knowledge graph edges across multi-modal ingested sources.
- **Traceability Verification**: Querying path reachability between source document chunks and downstream generated claims.

## Default Connection Specs
- **Host**: `falkordb` (within docker network) or `localhost` (when running locally)
- **Port**: `6379` (standard Redis protocol)
- **Persistence**: Append-Only File (AOF) / RDB snapshot mounted to persistent volume `falkordb_data:/data`.

## Health Check
Redis `PING` command returns `PONG`:
```bash
redis-cli -p 6379 ping
```
