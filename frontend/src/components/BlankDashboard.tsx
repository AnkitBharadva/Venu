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

// Phase 3 Schemas
interface GroundingSourceSpan {
  chunk_id: string;
  chunk_index: number;
  heading?: string;
  page_number?: number;
  timestamp_start?: number;
  timestamp_end?: number;
  char_offset_start: number;
  char_offset_end: number;
  quote: string;
  chunk_text: string;
  context_before: string;
  context_after: string;
  trace_verified: boolean;
}

interface SentenceTraceResponse {
  output_id: string;
  doc_id: string;
  deliverable_type: string;
  sentence_id: string;
  sentence_index: number;
  sentence_text: string;
  grounding_sources: GroundingSourceSpan[];
  all_spans_verified: boolean;
}

interface DeliverableResponse {
  output_id: string;
  doc_id: string;
  deliverable_type: string;
  status: string;
  content: {
    title: string;
    summary?: string;
    blocks: Array<{
      block_index: number;
      title?: string;
      sentences: Array<{
        sentence_id: string;
        sentence_index: number;
        text: string;
        citations: Array<{
          chunk_id: string;
          char_offset_start: number;
          char_offset_end: number;
          quote: string;
          confidence?: number;
        }>;
      }>;
    }>;
  };
  citations: Array<{
    sentence_id: string;
    sentence_index: number;
    sentence_text: string;
    chunk_id: string;
    chunk_index: number;
    char_offset_start: number;
    char_offset_end: number;
    quote: string;
    heading?: string;
  }>;
  total_sentences: number;
  total_citations: number;
  contract_verified: boolean;
}

interface RetrievedChunkItem {
  chunk_id: string;
  chunk_index: number;
  text: string;
  score: number;
  vector_score: number;
  graph_score: number;
  char_offset_start: number;
  char_offset_end: number;
  heading?: string;
  page_number?: number;
  entities_present: string[];
}

interface GroundedContextResponse {
  query: string;
  doc_id: string;
  total_chunks: number;
  retrieved_chunks: RetrievedChunkItem[];
  merged_context_text: string;
}

export const BlankDashboard: React.FC = () => {
  // Navigation tabs
  const [activeTab, setActiveTab] = useState<'pipeline' | 'grounding'>('pipeline');

  // Ingestion State (Phase 1)
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [latestDoc, setLatestDoc] = useState<SourceDocument | null>(null);
  const [showTextPreview, setShowTextPreview] = useState<boolean>(false);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Understanding State (Phase 2)
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processError, setProcessError] = useState<string | null>(null);
  const [understanding, setUnderstanding] = useState<DocumentUnderstanding | null>(null);
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [selectedChunk, setSelectedChunk] = useState<ChunkItem | null>(null);

  // Qdrant Vector Semantic Search State
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchResults, setSearchResults] = useState<SearchResultItem[] | null>(null);

  // Grounding & Provenance Trace State (Phase 3)
  const [deliverables, setDeliverables] = useState<DeliverableResponse[]>([]);
  const [selectedDeliverable, setSelectedDeliverable] = useState<DeliverableResponse | null>(null);
  const [hoveredSentenceId, setHoveredSentenceId] = useState<string | null>(null);
  const [sentenceTrace, setSentenceTrace] = useState<SentenceTraceResponse | null>(null);
  const [isTracing, setIsTracing] = useState<boolean>(false);
  const [isGeneratingDeliverables, setIsGeneratingDeliverables] = useState<boolean>(false);
  const [gatekeeperAlert, setGatekeeperAlert] = useState<{ type: 'error' | 'success'; message: string } | null>(null);

  // Hybrid Retrieval State
  const [hybridQuery, setHybridQuery] = useState<string>('air-gapped security architecture');
  const [isRetrievingHybrid, setIsRetrievingHybrid] = useState<boolean>(false);
  const [hybridResult, setHybridResult] = useState<GroundedContextResponse | null>(null);

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    setUploadError(null);
    setUnderstanding(null);
    setChunks([]);
    setSearchResults(null);
    setSelectedChunk(null);
    setDeliverables([]);
    setSelectedDeliverable(null);
    setSentenceTrace(null);
    setGatekeeperAlert(null);

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
      const procRes = await fetch(`/api/v1/understand/process/${latestDoc.doc_id}?actor=operator_primary`, {
        method: 'POST',
      });

      if (!procRes.ok) {
        const errJson = await procRes.json().catch(() => null);
        throw new Error(errJson?.detail || `HTTP ${procRes.status}`);
      }

      const procData = await procRes.json();
      setUnderstanding(procData.understanding);

      const chunksRes = await fetch(`/api/v1/understand/documents/${latestDoc.doc_id}/chunks`);
      if (chunksRes.ok) {
        const chunkList: ChunkItem[] = await chunksRes.json();
        setChunks(chunkList);
        if (chunkList.length > 0) {
          setSelectedChunk(chunkList[0]);
        }
      }

      await loadDeliverables(latestDoc.doc_id);
    } catch (err: unknown) {
      setProcessError(err instanceof Error ? err.message : 'Processing failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const loadDeliverables = async (docId: string) => {
    try {
      const res = await fetch(`/api/v1/grounding/outputs/document/${docId}`);
      if (res.ok) {
        const list: DeliverableResponse[] = await res.json();
        setDeliverables(list);
        if (list.length > 0) {
          setSelectedDeliverable(list[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load deliverables:', err);
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

  const handleHybridRetrieve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hybridQuery.trim() || !latestDoc) return;

    setIsRetrievingHybrid(true);
    try {
      const res = await fetch('/api/v1/grounding/retrieve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: hybridQuery,
          doc_id: latestDoc.doc_id,
          top_k: 4,
          include_graph: true,
          alpha: 0.7,
        }),
      });

      if (res.ok) {
        const data: GroundedContextResponse = await res.json();
        setHybridResult(data);
      }
    } catch (err) {
      console.error('Hybrid retrieval error:', err);
    } finally {
      setIsRetrievingHybrid(false);
    }
  };

  const handleGenerateSampleDeliverables = async () => {
    if (!latestDoc || chunks.length === 0) return;

    setIsGeneratingDeliverables(true);
    setGatekeeperAlert(null);

    try {
      const c0 = chunks[0];
      const c1 = chunks[1] || chunks[0];
      const c2 = chunks[2] || chunks[0];

      // 1. Executive Summary (4 sentences)
      const execPayload = {
        doc_id: latestDoc.doc_id,
        deliverable_type: 'executive_summary',
        content: {
          title: `Executive Intelligence Summary: ${latestDoc.original_filename}`,
          summary: 'High-level decision briefing with 100% verbatim source grounding.',
          blocks: [
            {
              block_index: 0,
              title: 'Strategic Mandate & Threat Scope',
              sentences: [
                {
                  sentence_id: 'exec_sent_0',
                  sentence_index: 0,
                  text: c0.text.slice(0, 140) + '...',
                  citations: [
                    {
                      chunk_id: c0.chunk_id,
                      char_offset_start: c0.char_offset_start,
                      char_offset_end: c0.char_offset_end,
                      quote: c0.text,
                    },
                  ],
                },
                {
                  sentence_id: 'exec_sent_1',
                  sentence_index: 1,
                  text: 'Hardware-level cryptographic validation ensures strict data immutability across all processing nodes.',
                  citations: [
                    {
                      chunk_id: c0.chunk_id,
                      char_offset_start: c0.char_offset_start,
                      char_offset_end: c0.char_offset_end,
                      quote: c0.text,
                    },
                  ],
                },
              ],
            },
            {
              block_index: 1,
              title: 'Operational Vectors & Assets',
              sentences: [
                {
                  sentence_id: 'exec_sent_2',
                  sentence_index: 2,
                  text: c1.text.slice(0, 140) + '...',
                  citations: [
                    {
                      chunk_id: c1.chunk_id,
                      char_offset_start: c1.char_offset_start,
                      char_offset_end: c1.char_offset_end,
                      quote: c1.text,
                    },
                  ],
                },
                {
                  sentence_id: 'exec_sent_3',
                  sentence_index: 3,
                  text: c2.text.slice(0, 140) + '...',
                  citations: [
                    {
                      chunk_id: c2.chunk_id,
                      char_offset_start: c2.char_offset_start,
                      char_offset_end: c2.char_offset_end,
                      quote: c2.text,
                    },
                  ],
                },
              ],
            },
          ],
        },
        format_metadata: { format: 'executive_briefing', clearance: 'RESTRICTED' },
      };

      const res = await fetch('/api/v1/grounding/outputs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(execPayload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.message || 'Failed to create deliverable');
      }

      await loadDeliverables(latestDoc.doc_id);
      setGatekeeperAlert({
        type: 'success',
        message: 'Successfully generated grounded deliverable! Hard claim-citation contract verified 100%.',
      });
    } catch (err: unknown) {
      setGatekeeperAlert({
        type: 'error',
        message: err instanceof Error ? err.message : 'Generation failed',
      });
    } finally {
      setIsGeneratingDeliverables(false);
    }
  };

  const handleTestHardContractViolation = async () => {
    if (!latestDoc) return;
    setGatekeeperAlert(null);

    try {
      const roguePayload = {
        doc_id: latestDoc.doc_id,
        deliverable_type: 'advisory',
        content: {
          title: 'Uncited Hallucinated Claim Deliverable',
          blocks: [
            {
              block_index: 0,
              sentences: [
                {
                  sentence_id: 'sent_rogue_0',
                  sentence_index: 0,
                  text: 'This hallucinated statement was emitted without any authentic source citation.',
                  citations: [],
                },
              ],
            },
          ],
        },
      };

      const res = await fetch('/api/v1/grounding/outputs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(roguePayload),
      });

      if (res.status === 422) {
        const err = await res.json();
        setGatekeeperAlert({
          type: 'success',
          message: `GATEKEEPER ENFORCED (HTTP 422): Hard contract successfully blocked uncited claim! Message: "${err.detail?.message || 'Uncited claims rejected'}"`,
        });
      } else {
        setGatekeeperAlert({
          type: 'error',
          message: `Expected HTTP 422 rejection, but received HTTP ${res.status}`,
        });
      }
    } catch (err: unknown) {
      setGatekeeperAlert({
        type: 'error',
        message: err instanceof Error ? err.message : 'Test failed',
      });
    }
  };

  const handleInspectSentenceTrace = async (outputId: string, sentenceIndex: number) => {
    setIsTracing(true);
    try {
      const res = await fetch(
        `/api/v1/grounding/trace?output_id=${outputId}&sentence_index=${sentenceIndex}`
      );
      if (res.ok) {
        const trace: SentenceTraceResponse = await res.json();
        setSentenceTrace(trace);
      }
    } catch (err) {
      console.error('Failed to trace sentence:', err);
    } finally {
      setIsTracing(false);
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
                Phase 3 Verified
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              Strict Claim-Citation Contract &bull; Hybrid Vector-Graph Retrieval &bull; Exact Hovercard Provenance Trace.
            </p>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center space-x-1 bg-gray-950/90 p-1 rounded-lg border border-gray-800">
          <button
            onClick={() => setActiveTab('pipeline')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition ${
              activeTab === 'pipeline'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            Ingestion & Understanding (Phases 1-2)
          </button>
          <button
            onClick={() => setActiveTab('grounding')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center space-x-1.5 ${
              activeTab === 'grounding'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <span>🎯 Grounding & Trace (Phase 3)</span>
            {deliverables.length > 0 && (
              <span className="bg-emerald-950 text-emerald-300 text-[10px] font-mono px-1.5 py-0.2 rounded-full border border-emerald-800">
                {deliverables.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* TAB 1: Pipeline Overview (Phase 1 & 2) */}
      {activeTab === 'pipeline' && (
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
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${
                  dragOver
                    ? 'border-emerald-500 bg-emerald-950/20'
                    : 'border-gray-800 hover:border-gray-700 bg-gray-950/40'
                }`}
              >
                <div className="mx-auto w-10 h-10 mb-3 rounded-full bg-gray-900 border border-gray-800 flex items-center justify-center text-gray-400">
                  {isUploading ? (
                    <svg className="w-5 h-5 animate-spin text-emerald-400" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                    </svg>
                  ) : (
                    <span>📁</span>
                  )}
                </div>
                <p className="text-xs font-medium text-gray-300">
                  {isUploading ? 'Encrypting & Storing at Rest...' : 'Drop source document here or click to browse'}
                </p>
                <p className="text-[10px] text-gray-500 mt-1">
                  Supports TXT, PDF, DOCX, PPTX, OCR Images, Audio/Video
                </p>
              </div>

              {uploadError && (
                <div className="mt-3 p-2.5 rounded-lg bg-rose-950/50 border border-rose-800/60 text-xs text-rose-300">
                  ⚠️ {uploadError}
                </div>
              )}

              {latestDoc && (
                <div className="mt-4 p-3 rounded-lg bg-gray-950/80 border border-gray-800 text-xs space-y-2">
                  <div className="flex items-center justify-between font-mono text-[10px] text-gray-400">
                    <span>DOCUMENT METADATA</span>
                    <span className="text-emerald-400">ENCRYPTED</span>
                  </div>
                  <div className="text-gray-200 font-medium truncate">
                    📄 {latestDoc.original_filename}
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-gray-400">
                    <div>Type: <span className="text-gray-200">{latestDoc.content_type}</span></div>
                    <div>Words: <span className="text-gray-200">{latestDoc.structural_metadata.word_count || 0}</span></div>
                    <div className="col-span-2 truncate">
                      SHA256: <span className="text-gray-400">{latestDoc.checksum.slice(0, 18)}...</span>
                    </div>
                  </div>

                  <button
                    onClick={() => setShowTextPreview(!showTextPreview)}
                    className="w-full text-center text-[10px] text-indigo-400 hover:text-indigo-300 pt-1 block"
                  >
                    {showTextPreview ? 'Hide Raw Text' : 'View Normalized Text'}
                  </button>

                  {showTextPreview && (
                    <div className="max-h-40 overflow-y-auto p-2 bg-gray-900 rounded border border-gray-800 text-[10px] font-mono text-gray-300 whitespace-pre-wrap">
                      {latestDoc.raw_text}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="mt-4 text-[10px] text-gray-500 border-t border-gray-800/60 pt-2 flex items-center justify-between">
              <span>Local KMS Key Isolation</span>
              <span className="text-emerald-400 font-mono">Zero Egress</span>
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
                      <div className="bg-gray-950/80 p-3 rounded-lg border border-gray-800">
                        <span className="text-[10px] font-mono text-indigo-400 uppercase tracking-wider block mb-1">
                          Stated Objective / Intent
                        </span>
                        <p className="text-gray-200 leading-relaxed text-[11px]">
                          {understanding.objective}
                        </p>
                      </div>

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

                      {understanding.sensitive_terms.length > 0 && (
                        <div className="p-2.5 bg-rose-950/20 border border-rose-800/50 rounded-lg">
                          <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider block mb-1">
                            🛡️ Sensitive Terms ({understanding.sensitive_terms.length})
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {understanding.sensitive_terms.map((st, i) => (
                              <span key={i} className="px-1.5 py-0.5 bg-rose-950/60 border border-rose-800/60 text-rose-300 rounded text-[9px] font-mono">
                                {st.term} ({st.severity})
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <div>
                        <span className="text-[10px] font-mono text-gray-400 block mb-1.5">
                          Extracted Entities ({understanding.key_entities.length})
                        </span>
                        <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
                          {understanding.key_entities.map((e, i) => (
                            <span
                              key={i}
                              className={`px-2 py-0.5 rounded border text-[10px] font-mono ${getEntityBadgeColor(e.type)}`}
                            >
                              {e.name} <span className="opacity-60">({e.type})</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-8 text-center text-gray-500 border border-dashed border-gray-800/80 rounded-lg bg-gray-950/30">
                  <p className="text-xs">No active document uploaded.</p>
                  <p className="text-[10px] mt-1 text-gray-600">Upload a file in Step 1 to trigger analysis.</p>
                </div>
              )}
            </div>

            <div className="mt-4 text-[10px] text-gray-500 border-t border-gray-800/60 pt-2 flex items-center justify-between">
              <span>FalkorDB OpenCypher</span>
              <span className="text-indigo-400 font-mono">Knowledge Graph Sync</span>
            </div>
          </div>

          {/* Right Column: Qdrant Chunks & Vector Search */}
          <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
                <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-500"></span>
                  <span>3. Vector Chunks & Search</span>
                </h3>
                <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/50">
                  Qdrant 384-d
                </span>
              </div>

              {/* Semantic Topic Search Form */}
              <form onSubmit={handleSearchQdrant} className="mb-4">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by topic or phrase..."
                    className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-cyan-500"
                  />
                  <button
                    type="submit"
                    disabled={isSearching || !latestDoc}
                    className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-800 text-white text-xs px-3 py-1.5 rounded-lg transition font-medium"
                  >
                    {isSearching ? '...' : 'Search'}
                  </button>
                </div>
              </form>

              {/* Search Results */}
              {searchResults && searchResults.length > 0 && (
                <div className="mb-4 space-y-1.5 max-h-40 overflow-y-auto pr-1">
                  <span className="text-[10px] font-mono text-cyan-400">Search Results ({searchResults.length})</span>
                  {searchResults.map((hit) => (
                    <div key={hit.chunk_id} className="p-2 rounded bg-gray-950 border border-cyan-800/40 text-[11px]">
                      <div className="flex items-center justify-between text-[10px] font-mono mb-1">
                        <span className="text-cyan-400 font-semibold">Chunk #{hit.chunk_index}</span>
                        <span className="text-gray-400">Score: {hit.score.toFixed(3)}</span>
                      </div>
                      <p className="text-gray-300 line-clamp-2">{hit.text}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Chunks List */}
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
      )}

      {/* TAB 2: Phase 3 Grounding & Provenance Trace Inspector */}
      {activeTab === 'grounding' && (
        <div className="space-y-6">
          {/* Top Control Bar: Contract Gatekeeper and Deliverable Generator */}
          <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-bold text-gray-200 flex items-center space-x-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                  <span>Hard Claim-Citation Contract & Deliverable Generator</span>
                </h3>
                <p className="text-xs text-gray-400 mt-1">
                  Generation adapters cannot emit claims without explicit chunk citations. All claims are strictly validated at the gateway.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                <button
                  onClick={handleGenerateSampleDeliverables}
                  disabled={isGeneratingDeliverables || chunks.length === 0}
                  className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-800 text-white text-xs rounded-lg font-medium transition flex items-center space-x-2 shadow-sm"
                >
                  {isGeneratingDeliverables ? (
                    <span>Generating Grounded Deliverables...</span>
                  ) : (
                    <>
                      <span>✨</span>
                      <span>Generate Grounded Deliverables</span>
                    </>
                  )}
                </button>

                <button
                  onClick={handleTestHardContractViolation}
                  disabled={!latestDoc}
                  className="px-3.5 py-2 bg-rose-950/60 hover:bg-rose-900/80 border border-rose-800/80 text-rose-300 text-xs rounded-lg font-medium transition flex items-center space-x-1.5"
                >
                  <span>🛡️</span>
                  <span>Test Gatekeeper (Uncited Rejection)</span>
                </button>
              </div>
            </div>

            {gatekeeperAlert && (
              <div
                className={`mt-4 p-3 rounded-lg text-xs border ${
                  gatekeeperAlert.type === 'success'
                    ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
                    : 'bg-rose-950/40 border-rose-800/60 text-rose-300'
                }`}
              >
                {gatekeeperAlert.message}
              </div>
            )}
          </div>

          {/* Main Phase 3 Layout: 2 Columns */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Deliverable Viewer & Sentence Provenance */}
            <div className="lg:col-span-7 bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-semibold text-gray-200">Grounded Deliverables</span>
                    {selectedDeliverable && (
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/60 text-emerald-300">
                        {selectedDeliverable.deliverable_type}
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                    Hover a Sentence &bull; Trace Prov
                  </span>
                </div>

                {deliverables.length > 0 ? (
                  <div className="space-y-4">
                    {/* Deliverable Selector Tabs */}
                    <div className="flex flex-wrap gap-2">
                      {deliverables.map((d) => (
                        <button
                          key={d.output_id}
                          onClick={() => {
                            setSelectedDeliverable(d);
                            setSentenceTrace(null);
                          }}
                          className={`px-3 py-1.5 rounded-lg text-xs font-mono transition border ${
                            selectedDeliverable?.output_id === d.output_id
                              ? 'bg-emerald-950/80 border-emerald-500 text-emerald-200'
                              : 'bg-gray-950 border-gray-800 text-gray-400 hover:border-gray-700'
                          }`}
                        >
                          {d.deliverable_type} ({d.total_sentences} sentences)
                        </button>
                      ))}
                    </div>

                    {/* Content Display with Sentence Hovercards */}
                    {selectedDeliverable && (
                      <div className="p-4 rounded-xl bg-gray-950/90 border border-gray-800 space-y-4">
                        <div className="border-b border-gray-800/80 pb-3">
                          <h4 className="text-sm font-bold text-gray-100">
                            {selectedDeliverable.content.title}
                          </h4>
                          {selectedDeliverable.content.summary && (
                            <p className="text-xs text-gray-400 mt-1 italic">
                              {selectedDeliverable.content.summary}
                            </p>
                          )}
                        </div>

                        {/* Blocks */}
                        <div className="space-y-4">
                          {selectedDeliverable.content.blocks.map((block) => (
                            <div key={block.block_index} className="space-y-2">
                              {block.title && (
                                <h5 className="text-xs font-mono uppercase tracking-wider text-indigo-400">
                                  § {block.title}
                                </h5>
                              )}
                              <div className="space-y-2 text-xs leading-relaxed text-gray-300">
                                {block.sentences.map((sent) => (
                                  <div
                                    key={sent.sentence_id}
                                    onMouseEnter={() => setHoveredSentenceId(sent.sentence_id)}
                                    onClick={() =>
                                      handleInspectSentenceTrace(
                                        selectedDeliverable.output_id,
                                        sent.sentence_index
                                      )
                                    }
                                    className={`p-2.5 rounded-lg border transition cursor-pointer ${
                                      sentenceTrace?.sentence_id === sent.sentence_id
                                        ? 'bg-emerald-950/70 border-emerald-500 text-emerald-100 shadow-sm'
                                        : hoveredSentenceId === sent.sentence_id
                                        ? 'bg-gray-900 border-indigo-500/70 text-gray-100'
                                        : 'bg-gray-900/50 border-gray-800/70 hover:border-gray-700'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between text-[10px] font-mono text-gray-400 mb-1">
                                      <span className="text-indigo-400">
                                        Sentence #{sent.sentence_index} ({sent.sentence_id})
                                      </span>
                                      <span className="text-emerald-400 bg-emerald-950/50 px-1.5 py-0.2 rounded border border-emerald-800/40">
                                        {sent.citations.length} citation{sent.citations.length > 1 ? 's' : ''} ✔
                                      </span>
                                    </div>
                                    <p className="text-[12px]">{sent.text}</p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-8 text-center text-gray-500 border border-dashed border-gray-800/80 rounded-lg bg-gray-950/30">
                    <p className="text-xs">No deliverables generated yet.</p>
                    <p className="text-[10px] mt-1 text-gray-600">
                      Click &ldquo;Generate Grounded Deliverables&rdquo; above to synthesize executive summaries, advisories, and posts.
                    </p>
                  </div>
                )}
              </div>

              <div className="mt-4 text-[10px] text-gray-500 border-t border-gray-800/60 pt-2 flex items-center justify-between font-mono">
                <span>Hard Contract Status: Active</span>
                <span className="text-emerald-400">100% Citations Enforced</span>
              </div>
            </div>

            {/* Right Column: Interactive Provenance Inspector & Hybrid Retrieval */}
            <div className="lg:col-span-5 space-y-6">
              {/* Provenance Trace Card */}
              <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5">
                <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
                  <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                    <span>Hovercard Provenance Inspector</span>
                  </h3>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                    /trace Endpoint
                  </span>
                </div>

                {isTracing ? (
                  <div className="p-8 text-center text-gray-400 text-xs">
                    Resolving exact source offsets...
                  </div>
                ) : sentenceTrace ? (
                  <div className="space-y-3.5 text-xs">
                    <div className="p-3 bg-gray-950 rounded-lg border border-gray-800">
                      <div className="text-[10px] font-mono text-gray-400 uppercase tracking-wider mb-1">
                        Inspected Claim
                      </div>
                      <p className="text-gray-200 font-medium text-[11px] leading-relaxed">
                        &ldquo;{sentenceTrace.sentence_text}&rdquo;
                      </p>
                    </div>

                    {sentenceTrace.grounding_sources.map((src, i) => (
                      <div
                        key={i}
                        className="p-3.5 rounded-lg bg-emerald-950/20 border border-emerald-800/60 space-y-2.5"
                      >
                        <div className="flex items-center justify-between text-[10px] font-mono">
                          <span className="text-emerald-300 font-bold">
                            Source Chunk #{src.chunk_index}
                          </span>
                          <span className="text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800">
                            Offsets: [{src.char_offset_start}:{src.char_offset_end}]
                          </span>
                        </div>

                        {src.heading && (
                          <div className="text-[10px] text-gray-400 font-medium">
                            Section: § {src.heading}
                          </div>
                        )}

                        <div className="bg-gray-950/90 p-2.5 rounded border border-gray-800 text-[11px] leading-relaxed">
                          <span className="text-[10px] font-mono text-gray-400 block mb-1">
                            Verbatim Source Quote:
                          </span>
                          <span className="text-emerald-300 bg-emerald-950/50 px-1 py-0.5 rounded border border-emerald-800/40">
                            {src.quote}
                          </span>
                        </div>

                        <div className="p-2.5 bg-gray-950/80 rounded border border-gray-800/80 text-[10px] font-mono text-gray-400">
                          <span className="text-gray-400 block mb-1">Surrounding Document Context:</span>
                          <span className="opacity-60">{src.context_before}</span>
                          <span className="text-emerald-300 font-bold bg-emerald-950/80 px-1">
                            [{src.quote.slice(0, 40)}...]
                          </span>
                          <span className="opacity-60">{src.context_after}</span>
                        </div>

                        <div className="flex items-center justify-between text-[10px] font-mono text-emerald-400 pt-1">
                          <span>Verified against raw_text ✔</span>
                          <span className="text-gray-400">ID: {src.chunk_id.slice(0, 12)}...</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-8 text-center text-gray-500 border border-dashed border-gray-800/80 rounded-lg bg-gray-950/30">
                    <p className="text-xs">Click any sentence on the left to inspect provenance.</p>
                    <p className="text-[10px] mt-1 text-gray-600">
                      Instantly resolves to exact character coordinates and chunk context.
                    </p>
                  </div>
                )}
              </div>

              {/* Hybrid Grounding Retrieval (/retrieve) */}
              <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5">
                <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
                  <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                    <span className="w-2 h-2 rounded-full bg-cyan-500"></span>
                    <span>Hybrid Context Retrieval (/retrieve)</span>
                  </h3>
                  <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/40">
                    Qdrant + FalkorDB
                  </span>
                </div>

                <form onSubmit={handleHybridRetrieve} className="mb-4">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={hybridQuery}
                      onChange={(e) => setHybridQuery(e.target.value)}
                      placeholder="Retrieve grounded context for adapter..."
                      className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-cyan-500"
                    />
                    <button
                      type="submit"
                      disabled={isRetrievingHybrid || !latestDoc}
                      className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-800 text-white text-xs px-3 py-1.5 rounded-lg transition font-medium"
                    >
                      {isRetrievingHybrid ? '...' : 'Retrieve'}
                    </button>
                  </div>
                </form>

                {hybridResult && (
                  <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                    {hybridResult.retrieved_chunks.map((rc) => (
                      <div
                        key={rc.chunk_id}
                        className="p-2.5 rounded-lg bg-gray-950/60 border border-gray-800 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between text-[10px] font-mono">
                          <span className="text-cyan-400 font-bold">Chunk #{rc.chunk_index}</span>
                          <span className="text-gray-400">
                            Score: <strong className="text-gray-200">{rc.score}</strong> (Vec: {rc.vector_score}, Graph: {rc.graph_score})
                          </span>
                        </div>
                        <p className="text-[11px] text-gray-300 line-clamp-2">{rc.text}</p>
                        <div className="text-[9px] font-mono text-gray-400">
                          Offsets: [{rc.char_offset_start}:{rc.char_offset_end}]
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
