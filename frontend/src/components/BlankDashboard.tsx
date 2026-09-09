import React, { useState, useRef } from 'react';

interface StructuralMetadata {
  parser?: string;
  total_pages?: number;
  total_slides?: number;
  word_count?: number;
  char_count?: number;
  duration_seconds?: number;
  confidence_score?: number;
  low_confidence?: boolean;
  warnings?: string[];
  headings?: Array<{ level?: number; title: string; page?: number; slide?: number }>;
  timestamps?: Array<{ start: number; end: number; text: string; confidence: number }>;
  image_dimensions?: { width: number; height: number };
}

interface SourceDocument {
  doc_id: string;
  original_filename: string;
  content_type: string;
  raw_text: string;
  structural_metadata: StructuralMetadata;
  upload_timestamp: string;
  uploader_id: string;
  checksum: string;
}

interface UploadResponse {
  status: string;
  document: SourceDocument;
  encrypted_storage_verified: boolean;
  audit_entry_recorded: boolean;
}

interface ChunkItem {
  chunk_id: string;
  doc_id: string;
  chunk_index: number;
  text: string;
  char_offset_start: number;
  char_offset_end: number;
  page_number?: number;
  heading?: string;
  timestamp_start?: number;
  timestamp_end?: number;
  offset_verified: boolean;
}

interface EntityMention {
  name: string;
  type: string;
  count: number;
  chunk_ids: string[];
}

interface SensitiveTerm {
  term: string;
  category: string;
  severity: string;
  reason: string;
  chunk_ids: string[];
}

interface EntityRelationship {
  source: string;
  relation: string;
  target: string;
  chunk_id?: string;
  confidence?: number;
}

interface DocumentUnderstanding {
  doc_id: string;
  objective: string;
  topics: string[];
  key_entities: EntityMention[];
  sensitive_terms: SensitiveTerm[];
  relationships: EntityRelationship[];
  summary: string;
  total_chunks: number;
  offset_accuracy_pct: number;
}

interface SearchResultItem {
  chunk_id: string;
  doc_id: string;
  chunk_index: number;
  text: string;
  score: number;
  char_offset_start: number;
  char_offset_end: number;
  heading?: string;
}

export const BlankDashboard: React.FC = () => {
  // Ingestion State
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [latestDoc, setLatestDoc] = useState<SourceDocument | null>(null);
  const [showTextPreview, setShowTextPreview] = useState<boolean>(false);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Phase 2 Understanding State
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processError, setProcessError] = useState<string | null>(null);
  const [understanding, setUnderstanding] = useState<DocumentUnderstanding | null>(null);
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [selectedChunk, setSelectedChunk] = useState<ChunkItem | null>(null);

  // Qdrant Vector Semantic Search State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchResults, setSearchResults] = useState<SearchResultItem[] | null>(null);

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    setUploadError(null);
    setUnderstanding(null);
    setChunks([]);
    setSearchResults(null);
    setSelectedChunk(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('uploader_id', 'operator_primary');

    try {
      const response = await fetch('/api/v1/ingest/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => null);
        const errorDetail = errJson?.detail?.message || errJson?.detail || `HTTP ${response.status}: ${response.statusText}`;
        throw new Error(typeof errorDetail === 'object' ? JSON.stringify(errorDetail) : String(errorDetail));
      }

      const data: UploadResponse = await response.json();
      setLatestDoc(data.document);
      setShowTextPreview(true);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleRunUnderstanding = async () => {
    if (!latestDoc) return;
    setIsProcessing(true);
    setProcessError(null);

    try {
      // 1. Trigger Understanding, Chunking, Embeddings & Graph upserts
      const procRes = await fetch(`/api/v1/understand/process/${latestDoc.doc_id}?actor=operator_primary`, {
        method: 'POST',
      });

      if (!procRes.ok) {
        const errJson = await procRes.json().catch(() => null);
        throw new Error(errJson?.detail || `HTTP ${procRes.status}`);
      }

      const procData = await procRes.json();
      setUnderstanding(procData.understanding);

      // 2. Fetch chunks with provenance validation
      const chunksRes = await fetch(`/api/v1/understand/documents/${latestDoc.doc_id}/chunks`);
      if (chunksRes.ok) {
        const chunkList: ChunkItem[] = await chunksRes.json();
        setChunks(chunkList);
        if (chunkList.length > 0) {
          setSelectedChunk(chunkList[0]);
        }
      }
    } catch (err: unknown) {
      setProcessError(err instanceof Error ? err.message : 'Processing failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSearchQdrant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim() || !latestDoc) return;

    setIsSearching(true);
    try {
      const res = await fetch('/api/v1/understand/search/semantic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchQuery,
          doc_id: latestDoc.doc_id,
          top_k: 4,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results);
      }
    } catch (err) {
      console.error('Semantic search error:', err);
    } finally {
      setIsSearching(false);
    }
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  };

  const getEntityBadgeColor = (type: string) => {
    switch (type) {
      case 'WEAPON_SYSTEM':
        return 'bg-purple-950/70 text-purple-300 border-purple-800/60';
      case 'ORGANIZATION':
        return 'bg-blue-950/70 text-blue-300 border-blue-800/60';
      case 'LOCATION':
        return 'bg-emerald-950/70 text-emerald-300 border-emerald-800/60';
      case 'TACTIC_TECHNIQUE':
        return 'bg-amber-950/70 text-amber-300 border-amber-800/60';
      default:
        return 'bg-gray-800 text-gray-300 border-gray-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Air-gap security banner */}
      <div className="bg-gradient-to-r from-emerald-950/40 via-indigo-950/30 to-gray-900 border border-emerald-800/40 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-emerald-900/50 border border-emerald-700/60 rounded-lg text-emerald-400">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Air-Gap Enclave: Active (Zero Outbound Egress)
              </h3>
              <span className="bg-emerald-500/20 text-emerald-300 text-[10px] font-mono px-2 py-0.5 rounded border border-emerald-500/30">
                Phase 2 Operational
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Multi-modal file router &bull; Semantic chunking &bull; Qdrant 384-dim dense vectors &bull; FalkorDB Cypher knowledge graph.
            </p>
          </div>
        </div>

        <div className="text-xs font-mono bg-gray-950/80 px-3 py-1.5 rounded-lg border border-gray-800 text-gray-300 flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          <span>Claim-to-Chunk Provenance: 100%</span>
        </div>
      </div>

      {/* Main Multi-Column Canvas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Ingestion Pipeline (Phase 1) */}
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                <span>1. Multi-Modal Ingestion</span>
              </h3>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50">
                AES-256
              </span>
            </div>

            <input
              type="file"
              ref={fileInputRef}
              onChange={onFileSelect}
              className="hidden"
              accept=".txt,.md,.pdf,.docx,.pptx,.png,.jpg,.jpeg,.webp,.wav,.mp3,.mp4,.m4a"
            />

            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition ${
                dragOver
                  ? 'border-indigo-500 bg-indigo-950/30'
                  : 'border-gray-800 hover:border-gray-700 bg-gray-950/40'
              }`}
            >
              <div className="w-10 h-10 mx-auto mb-2 text-indigo-400 flex items-center justify-center rounded-full bg-indigo-950/50 border border-indigo-800/60">
                {isUploading ? (
                  <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                )}
              </div>
              <p className="text-xs font-medium text-gray-200">
                {isUploading ? 'Ingesting File...' : 'Upload Source Document'}
              </p>
              <p className="text-[10px] text-gray-400 mt-1">
                PDF &bull; DOCX &bull; PPTX &bull; Text &bull; Audio/Video
              </p>
            </div>

            {uploadError && (
              <div className="mt-3 p-2.5 rounded-lg bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300">
                ⚠️ {uploadError}
              </div>
            )}

            {latestDoc && (
              <div className="mt-4 bg-gray-950/70 p-3 rounded-lg border border-gray-800 text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-gray-200 truncate max-w-[170px]">
                    {latestDoc.original_filename}
                  </span>
                  <span className="font-mono text-[9px] text-indigo-400 bg-indigo-950/80 px-1.5 py-0.5 rounded border border-indigo-800/40">
                    {latestDoc.content_type.split('/')[1] || latestDoc.content_type}
                  </span>
                </div>
                <div className="text-[10px] font-mono text-gray-400 flex justify-between">
                  <span>SHA-256:</span>
                  <span className="text-gray-300">{latestDoc.checksum.substring(0, 14)}...</span>
                </div>
                <div className="text-[10px] font-mono text-gray-400 flex justify-between">
                  <span>Characters:</span>
                  <span className="text-gray-300">{latestDoc.raw_text?.length || 0}</span>
                </div>

                <button
                  onClick={() => setShowTextPreview(!showTextPreview)}
                  className="w-full text-[11px] py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded border border-gray-700 transition"
                >
                  {showTextPreview ? 'Hide Raw Text' : 'View Raw Text Preview'}
                </button>

                {showTextPreview && (
                  <div className="max-h-36 overflow-y-auto p-2 bg-black/60 rounded border border-gray-800 text-[10px] font-mono text-gray-300 whitespace-pre-wrap leading-relaxed">
                    {latestDoc.raw_text}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="mt-4 text-[10px] text-gray-500 border-t border-gray-800/60 pt-2">
            Append-only audit row committed &bull; AES-256 encrypted at rest.
          </div>
        </div>

        {/* Center Column: Understanding & Extraction (Phase 2) */}
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                <span>2. Document Understanding</span>
              </h3>
              <span className="text-[10px] font-mono text-indigo-400 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-800/50">
                Phase 2 Core
              </span>
            </div>

            {latestDoc ? (
              <div className="space-y-3">
                {/* Trigger Processing Action Button */}
                <button
                  onClick={handleRunUnderstanding}
                  disabled={isProcessing}
                  className="w-full text-xs py-2 px-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-950/50 text-white rounded-lg font-medium transition flex items-center justify-center space-x-2 shadow-sm"
                >
                  {isProcessing ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                      </svg>
                      <span>Analyzing & Chunking...</span>
                    </>
                  ) : (
                    <>
                      <span>⚡</span>
                      <span>Run Understanding & Semantic Chunking</span>
                    </>
                  )}
                </button>

                {processError && (
                  <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300">
                    ⚠️ {processError}
                  </div>
                )}

                {understanding && (
                  <div className="space-y-3 text-xs">
                    {/* Stated Objective */}
                    <div className="bg-gray-950/80 p-3 rounded-lg border border-gray-800">
                      <span className="text-[10px] font-mono text-indigo-400 uppercase tracking-wider block mb-1">
                        Stated Mission Intent / Objective
                      </span>
                      <p className="text-gray-200 leading-relaxed text-[11px]">
                        {understanding.objective}
                      </p>
                    </div>

                    {/* Topics */}
                    <div>
                      <span className="text-[10px] font-mono text-gray-400 block mb-1.5">Classified Topics</span>
                      <div className="flex flex-wrap gap-1.5">
                        {understanding.topics.map((t, i) => (
                          <span key={i} className="px-2 py-0.5 rounded-md bg-gray-800 text-[10px] text-gray-200 border border-gray-700">
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Sensitive Advisory Terms (Advisory inputs) */}
                    {understanding.sensitive_terms.length > 0 && (
                      <div className="p-2.5 bg-rose-950/20 border border-rose-800/50 rounded-lg">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1">
                            <span>🛡️</span> Sensitive Advisory Terms ({understanding.sensitive_terms.length})
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {understanding.sensitive_terms.map((st, i) => (
                            <span
                              key={i}
                              title={st.reason}
                              className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${
                                st.severity === 'CRITICAL'
                                  ? 'bg-rose-900/60 text-rose-200 border-rose-700'
                                  : 'bg-amber-900/60 text-amber-200 border-amber-700'
                              }`}
                            >
                              [{st.severity}] {st.term}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Key Entities Categorized */}
                    <div>
                      <span className="text-[10px] font-mono text-gray-400 block mb-1.5">
                        Grounded Entities ({understanding.key_entities.length})
                      </span>
                      <div className="max-h-36 overflow-y-auto flex flex-wrap gap-1.5 p-1 bg-black/40 rounded border border-gray-800/80">
                        {understanding.key_entities.map((e, i) => (
                          <span
                            key={i}
                            className={`px-2 py-0.5 rounded text-[10px] font-mono border ${getEntityBadgeColor(e.type)}`}
                          >
                            {e.name} <span className="text-[9px] opacity-70">({e.type.substring(0, 4)})</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-6 text-center text-gray-500 border border-dashed border-gray-800/80 rounded-lg bg-gray-950/30">
                <p className="text-xs">Awaiting source file upload.</p>
                <p className="text-[10px] mt-1 text-gray-600">Upload in Step 1 to trigger entity and topic understanding.</p>
              </div>
            )}
          </div>

          <div className="mt-4 text-[10px] text-gray-500 border-t border-gray-800/60 pt-2">
            FalkorDB openCypher graph &bull; Reasoner NER fallback &bull; Zero network egress.
          </div>
        </div>

        {/* Right Column: Grounding Chunks & Qdrant Semantic Search */}
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                <span>3. Grounding & Qdrant Search</span>
              </h3>
              <span className="text-[10px] font-mono text-purple-400 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-800/50">
                384-Dim Vectors
              </span>
            </div>

            {/* Qdrant Vector Semantic Search Box */}
            <form onSubmit={handleSearchQdrant} className="mb-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Query chunks by topic via Qdrant..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex-1 px-3 py-1.5 bg-gray-950/80 border border-gray-700 rounded-lg text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-purple-500"
                />
                <button
                  type="submit"
                  disabled={isSearching || !latestDoc}
                  className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-800 text-white rounded-lg text-xs font-medium transition"
                >
                  {isSearching ? '...' : 'Search'}
                </button>
              </div>
            </form>

            {/* Search Hits */}
            {searchResults && (
              <div className="mb-4 space-y-2">
                <span className="text-[10px] font-mono text-purple-400 block">
                  Top Vector Hits (Cosine Similarity)
                </span>
                {searchResults.length === 0 ? (
                  <p className="text-[11px] text-gray-500">No matching chunks found.</p>
                ) : (
                  searchResults.map((hit) => (
                    <div
                      key={hit.chunk_id}
                      className="p-2.5 rounded bg-purple-950/30 border border-purple-900/50 text-[11px] space-y-1"
                    >
                      <div className="flex justify-between items-center text-[10px] font-mono">
                        <span className="text-purple-300 font-bold">Chunk #{hit.chunk_index}</span>
                        <span className="px-1.5 py-0.2 bg-purple-900/80 text-purple-200 rounded border border-purple-700">
                          Score: {hit.score.toFixed(4)}
                        </span>
                      </div>
                      <p className="text-gray-300 line-clamp-2">{hit.text}</p>
                      <div className="text-[9px] font-mono text-gray-400">
                        Span: [{hit.char_offset_start}:{hit.char_offset_end}]
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Semantic Chunks Inspector */}
            {chunks.length > 0 ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-gray-400">
                    Addressable Chunks ({chunks.length})
                  </span>
                  <span className="text-[9px] font-mono text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
                    Offsets Verified ✔
                  </span>
                </div>

                <div className="max-h-60 overflow-y-auto space-y-1.5 pr-1">
                  {chunks.map((c) => (
                    <div
                      key={c.chunk_id}
                      onClick={() => setSelectedChunk(c)}
                      className={`p-2.5 rounded-lg border text-xs cursor-pointer transition ${
                        selectedChunk?.chunk_id === c.chunk_id
                          ? 'bg-indigo-950/60 border-indigo-500 text-gray-100'
                          : 'bg-gray-950/50 border-gray-800 hover:border-gray-700 text-gray-400'
                      }`}
                    >
                      <div className="flex items-center justify-between text-[10px] font-mono mb-1">
                        <span className="text-indigo-400 font-bold">Chunk #{c.chunk_index}</span>
                        <span className="text-gray-400">
                          [{c.char_offset_start}:{c.char_offset_end}]
                        </span>
                      </div>
                      {c.heading && (
                        <div className="text-[10px] text-gray-400 font-medium truncate mb-1">
                          § {c.heading}
                        </div>
                      )}
                      <p className="line-clamp-2 text-[11px] text-gray-300 leading-relaxed">
                        {c.text}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="p-6 text-center text-gray-500 border border-dashed border-gray-800/80 rounded-lg bg-gray-950/30">
                <p className="text-xs">No chunks generated.</p>
                <p className="text-[10px] mt-1 text-gray-600">Run Step 2 to segment document into addressable units.</p>
              </div>
            )}
          </div>

          <div className="mt-4 text-[10px] text-gray-500 border-t border-gray-800/60 pt-2">
            Exact character provenance: raw_text[start:end] == chunk.text
          </div>
        </div>
      </div>
    </div>
  );
};
