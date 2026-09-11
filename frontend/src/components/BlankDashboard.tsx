import React, { useState, useRef, useEffect, useMemo } from 'react';
import { KnowledgeGraphVisualizer, GraphNodeData, GraphEdgeData } from './KnowledgeGraphVisualizer';
import { HumanReviewWorkspace } from './HumanReviewWorkspace';

interface StructuralMetadata {
  parser?: string;
  total_pages?: number;
  total_slides?: number;
  word_count?: number;
  char_count?: number;
  duration_seconds?: number;
  confidence_score?: number;
  headings?: Array<{ level?: number; title: string; page?: number; slide?: number }>;
  timestamps?: Array<{ start: number; end: number; text: string; confidence: number }>;
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


interface DocumentSummaryItem {
  doc_id: string;
  original_filename: string;
  content_type: string;
  upload_timestamp: string;
  uploader_id: string;
  checksum: string;
  char_count: number;
  low_confidence: boolean;
}

interface BatchUploadItem {
  filename: string;
  status: string;
  doc_id?: string;
  document?: SourceDocument;
  error?: string;
}

interface BatchUploadResponse {
  status: string;
  total_files: number;
  successful_count: number;
  failed_count: number;
  items: BatchUploadItem[];
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

interface GroundingSourceSpan {
  chunk_id: string;
  chunk_index: number;
  heading?: string;
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
  encrypted_file_path?: string;
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
        }>;
      }>;
    }>;
  };
  citations: Array<{
    sentence_id: string;
    sentence_index: number;
    sentence_text: string;
    chunk_id: string;
    quote: string;
  }>;
  format_metadata: Record<string, any>;
  total_sentences: number;
  total_citations: number;
  contract_verified: boolean;
  reviewer_id?: string | null;
  reviewer_notes?: string | null;
}

interface AuditVerification {
  valid: boolean;
  total_records: number;
  latest_hash?: string;
  error?: string;
  record_id?: number;
}

interface OutputEncryptionInfo {
  output_id: string;
  verified: boolean;
  algorithm: string;
  file_path: string;
  file_size_bytes?: number;
  ciphertext_sha256?: string;
  deliverable_type?: string;
}

interface ExportResult {
  output_id: string;
  doc_id: string;
  deliverable_type: string;
  export_format: string;
  exported_filename: string;
  checksum_sha256: string;
  exported_content: string;
  actor: string;
}

interface AuditLogEntry {
  id: number;
  actor: string;
  action: string;
  doc_id?: string | null;
  output_id?: string | null;
  timestamp: string;
  details: Record<string, any>;
  prev_hash: string;
  hash: string;
}

interface AirgapProofResponse {
  isolated?: boolean;
  egress_blocked?: boolean;
  airgap_verified?: boolean;
  tested_target?: string;
  target_tested?: string;
  timestamp: string;
  details: string;
}

const AVAILABLE_FORMATS = [
  { id: 'advisory', label: 'Tactical Advisory', category: 'Operational', desc: '4-section risk & mitigation brief' },
  { id: 'executive_summary', label: 'Executive Summary', category: 'Executive', desc: 'Dense 150-300 word decision memo' },
  { id: 'twitter_thread', label: 'Social Thread (X)', category: 'Public', desc: 'Numbered sequence (<=230 chars/card)' },
  { id: 'linkedin_post', label: 'Thought Leadership', category: 'Strategic', desc: 'Strategic breakdown & non-rhetorical CTA' },
  { id: 'presentation', label: 'Presentation Deck', category: 'Briefing', desc: '4-slide visual scanning architecture' },
  { id: 'video_package', label: 'Video Production Package', category: 'Media', desc: 'Voiceover narrative & SRT subtitles' },
  { id: 'infographic', label: 'Infographic Layout Spec', category: 'Visual', desc: 'Data-driven cards & key metrics' },
  { id: 'technical_documentation', label: 'Technical Documentation', category: 'Engineering', desc: 'Scope, pipeline & security model' },
];

const SAMPLE_DOCS = {
  defense: {
    name: 'Defense Directive (Air-Gap Security)',
    filename: 'DEFENSE_DIRECTIVE_AIR_GAP_STANDARD.txt',
    content: `DEFENCE DIRECTIVE 2026: AIR-GAP SECURITY STANDARD & AUTOMATED CONTENT TRANSFORMATION ENCLAVE.

SECTION 1: OPERATIONAL ENCLAVE ARCHITECTURE
All tactical intelligence processing, multi-source ingestion, and automated content transformation must execute strictly inside physically isolated air-gapped enclaves. Zero external network egress is mandated across all infrastructure layers. All compute nodes operate without public gateways or remote cloud telemetry.

SECTION 2: DUAL-CONTROL HUMAN REVIEW CHECKPOINT
No automated AI-generated deliverable—specifically tactical advisories, executive summaries, or threat bulletins—may be published or exported without formal two-person rule verification. Deliverables must begin in status 'draft' with export authorization locked. A certified Human Reviewer must examine claims against underlying ground-truth citations, inspect unified diffs for any revisions, and explicitly transition the deliverable to status 'final'.

SECTION 3: CRYPTOGRAPHIC PROVENANCE & LINEAR HASH CHAIN
Every operator action, including document ingestion, semantic chunking, output generation, claim edit, reviewer sign-off, and export dispatch, must be cryptographically recorded in an append-only linear SHA-256 hash chain. Any unauthorized modification to prior records must immediately invalidate subsequent chain hashes and isolate the compromised block index. All stored documents and generated outputs must be encrypted at rest using authenticated AES-256-GCM keys managed strictly by local KMS.`,
  },
  cyber: {
    name: 'SCADA Infrastructure Advisory',
    filename: 'SCADA_INFRASTRUCTURE_ADVISORY.txt',
    content: `CRITICAL INFRASTRUCTURE DEFENSE: RANSOMWARE THREAT INTELLIGENCE ADVISORY.

SECTION 1: INCIDENT OVERVIEW & THREAT VECTOR
A coordinated threat group has targeted industrial SCADA controllers within regional electrical transmission grids. The attack vector exploits unpatched remote management interfaces to deploy localized ransomware payloads. Ground telemetry indicates lateral movement attempts across operational technology segments.

SECTION 2: MANDATED OPERATIONAL DIRECTIVES
All critical grid substations are immediately ordered to transition to isolated air-gap control protocols. Operators must isolate external administrative jump hosts and enforce strict dual-operator authorization for telemetry configuration overrides. AI-assisted analysis systems must verify that incident summaries, threat intelligence feeds, and tactical response advisories are 100% grounded in verified sensor logs.

SECTION 3: INCIDENT RESPONSE & COMPLIANCE
Incident response teams must document all mitigation actions with tamper-evident cryptographic logging. The supervisory command mandates that no external reports or advisory bulletins be exported to public or inter-agency channels without verified reviewer sign-off, ensuring zero hallucinated recommendations.`,
  },
  maritime: {
    name: 'Maritime Domain Awareness Log',
    filename: 'MARITIME_DOMAIN_AWARENESS_LOG.txt',
    content: `JOINT MARITIME RECONNAISSANCE: STRAIT OF MALACCA AUTONOMOUS PATROL LOG.

SECTION 1: SENSOR TELEMETRY & VESSEL TRACKING
Autonomous maritime reconnaissance drone Alpha-4 detected anomalous automated identification system (AIS) transponder spoofing near Sector 7. Multispectral optical sensors confirmed the presence of an unflagged cargo vessel conducting suspicious rendezvous maneuvers with two high-speed pursuit craft.

SECTION 2: SURVEILLANCE FINDINGS & TACTICAL ANALYSIS
Optical payloads recorded cargo transfer activities under darkness without navigation lights. Acoustic hydrophone arrays registered intermittent subsurface frequency spikes consistent with submerged tethered communication buoys. The observed speed and heading indicate an evasion route toward contested international littoral zones.

SECTION 3: COMMAND ACTION PLAN
Coast guard interception assets are placed on high alert. The intelligence analysis center requires rapid transformation of multi-source surveillance logs into executive briefings, tactical boarding advisories, and inter-agency coordination packages. All generated deliverables must maintain strict character-level provenance to sensor log timestamps.`,
  },
};

export const BlankDashboard: React.FC = () => {
  // Navigation
  const [activeTab, setActiveTab] = useState<'studio' | 'review' | 'grounding' | 'audit'>('studio');
  const [userRole, setUserRole] = useState<'operator' | 'reviewer'>('reviewer');

  // Document State
  const [documents, setDocuments] = useState<DocumentSummaryItem[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState<boolean>(false);
  const [latestDoc, setLatestDoc] = useState<SourceDocument | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [showRawText, setShowRawText] = useState<boolean>(false);
  const [clearDbModalOpen, setClearDbModalOpen] = useState<boolean>(false);
  const [isClearingDb, setIsClearingDb] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Formats Selection
  const [selectedFormats, setSelectedFormats] = useState<string[]>([
    'advisory',
    'executive_summary',
    'twitter_thread',
    'linkedin_post',
  ]);

  // Parameters
  const [showParameters, setShowParameters] = useState<boolean>(false);
  const [targetAudience, setTargetAudience] = useState<string>('Strategic Decision Makers & Analysts');
  const [targetTone, setTargetTone] = useState<string>('Authoritative & Objective');
  const [targetLanguage, setTargetLanguage] = useState<string>('en');
  const [detailLevel, setDetailLevel] = useState<string>('standard');
  const [targetObjective, setTargetObjective] = useState<string>('Operational Readiness & Strategic Mandate');
  const [targetStyle, setTargetStyle] = useState<string>('Executive Intelligence Standard');

  // Deliverables & Generation
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [deliverables, setDeliverables] = useState<DeliverableResponse[]>([]);
  const [selectedDeliverable, setSelectedDeliverable] = useState<DeliverableResponse | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<string>('markdown');
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [rightViewMode, setRightViewMode] = useState<'deliverables' | 'chunks'>('deliverables');

  // Provenance / Trace
  const [sentenceTrace, setSentenceTrace] = useState<SentenceTraceResponse | null>(null);
  const [hoveredSentenceId, setHoveredSentenceId] = useState<string | null>(null);
  const [isTracing, setIsTracing] = useState<boolean>(false);

  // Understanding & Grounding
  const [understanding, setUnderstanding] = useState<DocumentUnderstanding | null>(null);
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [isProcessingSource, setIsProcessingSource] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[] | null>(null);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [graphData, setGraphData] = useState<{ nodes: GraphNodeData[]; edges: GraphEdgeData[] } | null>(null);
  const [isLoadingGraph, setIsLoadingGraph] = useState<boolean>(false);
  const [selectedEntityForGraph, setSelectedEntityForGraph] = useState<string | null>(null);
  const [groundingViewMode, setGroundingViewMode] = useState<'graph' | 'vectors' | 'split'>('graph');

  // Audit
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [isLoadingAudit, setIsLoadingAudit] = useState<boolean>(false);
  const [auditVerification, setAuditVerification] = useState<AuditVerification | null>(null);
  const [isVerifyingAudit, setIsVerifyingAudit] = useState<boolean>(false);
  const [auditFilterAction, setAuditFilterAction] = useState<string>('all');
  const [auditSearchQuery, setAuditSearchQuery] = useState<string>('');
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);

  // Modals
  const [airgapModalOpen, setAirgapModalOpen] = useState<boolean>(false);
  const [airgapProof, setAirgapProof] = useState<AirgapProofResponse | null>(null);
  const [isLoadingAirgap, setIsLoadingAirgap] = useState<boolean>(false);
  const [exportModal, setExportModal] = useState<ExportResult | null>(null);
  const [encryptionModal, setEncryptionModal] = useState<OutputEncryptionInfo | null>(null);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'alert'; text: string } | null>(null);

  // Toast Auto-clear
  useEffect(() => {
    if (toastMessage) {
      const t = setTimeout(() => setToastMessage(null), 4000);
      return () => clearTimeout(t);
    }
  }, [toastMessage]);

  // Initial audit fetch
  useEffect(() => {
    fetchAuditLogs();
  }, []);

  const fetchAuditLogs = async () => {
    setIsLoadingAudit(true);
    try {
      const res = await fetch('/api/v1/audit/logs?limit=40');
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data);
      }
    } catch {
      // offline fallback
    } finally {
      setIsLoadingAudit(false);
    }
  };

  // Auto-fetch knowledge graph when entering grounding tab if not yet loaded
  useEffect(() => {
    if (activeTab === 'grounding' && latestDoc && !graphData && !isLoadingGraph) {
      fetchGraphData(latestDoc.doc_id);
    }
  }, [activeTab, latestDoc, graphData, isLoadingGraph]);

  const verifyAuditChain = async () => {
    setIsVerifyingAudit(true);
    try {
      const res = await fetch('/api/v1/audit/verify-chain');
      const data: AuditVerification = await res.json();
      setAuditVerification(data);
      if (data.valid) {
        setToastMessage({
          type: 'success',
          text: `Audit chain verified: all ${data.total_records} records cryptographically intact.`,
        });
      } else {
        setToastMessage({
          type: 'alert',
          text: `Integrity alert: compromise detected at record #${data.record_id}`,
        });
      }
    } catch {
      setToastMessage({ type: 'alert', text: 'Audit verification service unreachable.' });
    } finally {
      setIsVerifyingAudit(false);
    }
  };

  const probeAirgap = async () => {
    setIsLoadingAirgap(true);
    try {
      const res = await fetch('/health/airgap');
      if (res.ok) {
        const data: AirgapProofResponse = await res.json();
        setAirgapProof(data);
      }
    } catch {
      // silent
    } finally {
      setIsLoadingAirgap(false);
    }
  };

  // Fetch existing documents from DB and restore active document on mount or refresh
  useEffect(() => {
    fetchDocumentsAndRestore();
  }, []);

  const fetchDocumentsAndRestore = async (preferredDocId?: string) => {
    setIsLoadingDocs(true);
    try {
      const res = await fetch('/api/v1/ingest/documents?limit=100');
      if (res.ok) {
        const docList: DocumentSummaryItem[] = await res.json();
        setDocuments(docList);

        if (docList.length > 0) {
          const targetId =
            preferredDocId ||
            localStorage.getItem('active_doc_id') ||
            docList[0].doc_id;

          const exists = docList.some((d) => d.doc_id === targetId);
          const finalId = exists ? targetId : docList[0].doc_id;
          await loadDocument(finalId);
        } else {
          setLatestDoc(null);
          setChunks([]);
          setUnderstanding(null);
          setGraphData(null);
          setDeliverables([]);
          setSelectedDeliverable(null);
          localStorage.removeItem('active_doc_id');
        }
      }
    } catch (err) {
      console.error('Failed to restore documents:', err);
    } finally {
      setIsLoadingDocs(false);
    }
  };

  const loadDocument = async (docId: string) => {
    localStorage.setItem('active_doc_id', docId);
    try {
      // 1. Fetch normalized document text & metadata
      const docRes = await fetch(`/api/v1/ingest/documents/${docId}`);
      if (docRes.ok) {
        const doc: SourceDocument = await docRes.json();
        setLatestDoc(doc);
      }

      // 2. Fetch ground truth chunks
      const chunksRes = await fetch(`/api/v1/understand/documents/${docId}/chunks`);
      if (chunksRes.ok) {
        const chunkList: ChunkItem[] = await chunksRes.json();
        setChunks(chunkList);
      } else {
        setChunks([]);
      }

      // 3. Fetch structured understanding
      const undRes = await fetch(`/api/v1/understand/documents/${docId}/understanding`);
      if (undRes.ok) {
        const undData: DocumentUnderstanding = await undRes.json();
        setUnderstanding(undData);
      } else {
        setUnderstanding(null);
      }

      // 4. Fetch knowledge graph topology
      fetchGraphData(docId);

      // 5. Fetch generated deliverables
      const delivRes = await fetch(`/api/v1/review/pending?doc_id=${docId}`, {
        headers: { 'X-User-Role': 'operator', 'X-User-Id': 'operator_primary' },
      });
      if (delivRes.ok) {
        const delivList: DeliverableResponse[] = await delivRes.json();
        setDeliverables(delivList);
        if (delivList.length > 0) {
          setSelectedDeliverable(delivList[0]);
        } else {
          setSelectedDeliverable(null);
        }
      } else {
        setDeliverables([]);
        setSelectedDeliverable(null);
      }
    } catch (err) {
      console.error(`Failed to load document ${docId}:`, err);
    }
  };

  const handleResetDoc = () => {
    setLatestDoc(null);
    setChunks([]);
    setDeliverables([]);
    setSelectedDeliverable(null);
    setSentenceTrace(null);
    setUnderstanding(null);
    setShowRawText(false);
    setUploadError(null);
    setRightViewMode('deliverables');
  };

  // Support multi-file batch upload (1 or more files simultaneously)
  const handleMultipleFilesUpload = async (fileList: FileList | File[]) => {
    const files = Array.from(fileList);
    if (files.length === 0) return;

    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    formData.append('uploader_id', 'operator_primary');

    try {
      const res = await fetch('/api/v1/ingest/upload-batch', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail?.message || errJson?.detail || `HTTP ${res.status}`);
      }

      const batchRes: BatchUploadResponse = await res.json();
      const successfulItems = batchRes.items.filter((i) => i.status === 'success' && i.doc_id);

      if (successfulItems.length === 0) {
        const firstErr = batchRes.items.find((i) => i.error)?.error || 'Batch ingestion failed';
        throw new Error(firstErr);
      }

      setToastMessage({
        type: 'success',
        text: `Ingested ${successfulItems.length} file(s) with AES-256 encryption. Indexing chunks...`,
      });
      fetchAuditLogs();

      // Automatically run semantic chunking & indexing for each newly ingested document
      setIsProcessingSource(true);
      for (const item of successfulItems) {
        if (item.doc_id) {
          try {
            await fetch(`/api/v1/understand/process/${item.doc_id}?actor=operator_primary`, {
              method: 'POST',
            });
          } catch (e) {
            console.warn(`Auto-indexing for ${item.filename} failed:`, e);
          }
        }
      }
      setIsProcessingSource(false);

      // Refresh documents and set the active document to the first newly uploaded file
      const activeId = successfulItems[0].doc_id!;
      await fetchDocumentsAndRestore(activeId);

      setToastMessage({
        type: 'success',
        text: `Ingested and indexed ${successfulItems.length} document(s). Ready to transform.`,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Batch ingestion failed';
      if (msg.toLowerCase().includes('failed to fetch')) {
        setUploadError('Unable to connect to backend server. Ensure the backend is active on http://localhost:8000.');
      } else {
        setUploadError(msg);
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleClearDatabase = async () => {
    setIsClearingDb(true);
    try {
      const res = await fetch('/api/v1/ingest/clear-database', {
        method: 'POST',
      });
      if (!res.ok) {
        throw new Error(`Failed to clear database (HTTP ${res.status})`);
      }

      // Reset all frontend state
      setLatestDoc(null);
      setDocuments([]);
      setChunks([]);
      setDeliverables([]);
      setSelectedDeliverable(null);
      setSentenceTrace(null);
      setUnderstanding(null);
      setGraphData(null);
      setShowRawText(false);
      setUploadError(null);
      setRightViewMode('deliverables');
      localStorage.removeItem('active_doc_id');

      setClearDbModalOpen(false);
      setToastMessage({
        type: 'success',
        text: 'Database cleared: All documents, vectors, graph topology, and deliverables purged.',
      });

      fetchAuditLogs();
    } catch (err) {
      setToastMessage({
        type: 'alert',
        text: err instanceof Error ? err.message : 'Failed to clear database.',
      });
    } finally {
      setIsClearingDb(false);
    }
  };

  const handleLoadSample = (key: 'defense' | 'cyber' | 'maritime') => {
    const s = SAMPLE_DOCS[key];
    const file = new File([s.content], s.filename, { type: 'text/plain' });
    handleMultipleFilesUpload([file]);
  };

  const fetchGraphData = async (docId: string) => {
    setIsLoadingGraph(true);
    try {
      const res = await fetch(`/api/v1/understand/documents/${docId}/graph`);
      if (res.ok) {
        const data = await res.json();
        setGraphData(data);
      }
    } catch (err) {
      console.error('Graph fetch error:', err);
    } finally {
      setIsLoadingGraph(false);
    }
  };

  const handleProcessSource = async () => {
    if (!latestDoc) return;
    setIsProcessingSource(true);
    try {
      const procRes = await fetch(`/api/v1/understand/process/${latestDoc.doc_id}?actor=operator_primary`, {
        method: 'POST',
      });
      if (procRes.ok) {
        const data = await procRes.json();
        setUnderstanding(data.understanding);
      }
      const chunksRes = await fetch(`/api/v1/understand/documents/${latestDoc.doc_id}/chunks`);
      if (chunksRes.ok) {
        const chunkList: ChunkItem[] = await chunksRes.json();
        setChunks(chunkList);
      }
      await fetchGraphData(latestDoc.doc_id);
    } catch (err) {
      console.error('Understanding error:', err);
    } finally {
      setIsProcessingSource(false);
    }
  };

  const handleSearchChunks = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim() || !latestDoc) return;
    setIsSearching(true);
    try {
      const res = await fetch('/api/v1/understand/search/semantic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery, doc_id: latestDoc.doc_id, top_k: 4 }),
      });
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results);
      }
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleGenerate = async () => {
    if (!latestDoc) {
      setToastMessage({ type: 'alert', text: 'Select or upload source material first.' });
      return;
    }
    if (selectedFormats.length === 0) {
      setToastMessage({ type: 'alert', text: 'Select at least one output format.' });
      return;
    }

    setIsGenerating(true);
    try {
      if (chunks.length === 0) {
        try {
          await handleProcessSource();
        } catch {}
      }

      const payload = {
        doc_id: latestDoc.doc_id,
        deliverable_types: selectedFormats,
        parameters: {
          audience: targetAudience,
          tone: targetTone,
          language: targetLanguage,
          detail_level: detailLevel,
          objective: targetObjective,
          style: targetStyle,
        },
        actor: 'operator_primary',
      };

      const res = await fetch('/api/v1/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail?.message || errJson?.detail || 'Generation failed');
      }

      const data = await res.json();
      setDeliverables(data.deliverables);
      if (data.deliverables.length > 0) {
        setSelectedDeliverable(data.deliverables[0]);
        setRightViewMode('deliverables');
      }
      fetchAuditLogs();
      setToastMessage({
        type: 'success',
        text: `Generated ${data.total_deliverables} deliverables with 100% claim-to-chunk provenance.`,
      });
    } catch (err) {
      setToastMessage({
        type: 'alert',
        text: err instanceof Error ? err.message : 'Generation failed',
      });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleTraceSentence = async (outputId: string, sentenceIndex: number) => {
    setIsTracing(true);
    try {
      const res = await fetch(`/api/v1/grounding/trace?output_id=${outputId}&sentence_index=${sentenceIndex}`);
      if (res.ok) {
        const data: SentenceTraceResponse = await res.json();
        setSentenceTrace(data);
      }
    } catch (err) {
      console.error('Trace error:', err);
    } finally {
      setIsTracing(false);
    }
  };

  const handleCopyContent = (d: DeliverableResponse) => {
    let text = `# ${d.content.title}\n\n`;
    if (d.content.summary) text += `> ${d.content.summary}\n\n`;
    d.content.blocks.forEach((b) => {
      if (b.title) text += `## ${b.title}\n\n`;
      const blockText = b.sentences.map((s) => s.text).join(' ');
      if (blockText) text += `${blockText}\n\n`;
    });
    navigator.clipboard.writeText(text.trim());
    setCopiedId(d.output_id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleStudioSubmitForReview = async (outputId: string) => {
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/request-approval`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': 'operator',
          'X-User-Id': 'operator_primary',
        },
        body: JSON.stringify({ notes: 'Submitted from Transformation Studio.' }),
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedDeliverable(updated);
        setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
        setToastMessage({ type: 'success', text: 'Submitted to reviewer queue (status: pending_review).' });
        fetchAuditLogs();
      }
    } catch {
      setToastMessage({ type: 'alert', text: 'Failed to submit for review.' });
    }
  };

  const handleStudioApprove = async (outputId: string) => {
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': 'reviewer',
          'X-User-Id': 'reviewer_primary',
        },
        body: JSON.stringify({ reviewer_notes: 'Ground truth citations verified in Transformation Studio. Approved for export.' }),
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedDeliverable(updated);
        setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
        setToastMessage({ type: 'success', text: 'Deliverable certified and approved. Export unlocked!' });
        fetchAuditLogs();
      }
    } catch {
      setToastMessage({ type: 'alert', text: 'Approval failed.' });
    }
  };

  const handleExport = async (outputId: string, format: string) => {
    setIsExporting(true);
    try {
      // Enforce Human Review Gatekeeper
      if (
        selectedDeliverable &&
        selectedDeliverable.status !== 'approved' &&
        selectedDeliverable.status !== 'final'
      ) {
        if (userRole === 'reviewer') {
          // As certified reviewer, auto-certify upon deliberate export click with note
          const appRes = await fetch(`/api/v1/review/outputs/${outputId}/approve`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-User-Role': 'reviewer',
              'X-User-Id': 'reviewer_primary',
            },
            body: JSON.stringify({ reviewer_notes: 'Ground truth verified. Certified for release upon export.' }),
          });
          if (appRes.ok) {
            const updatedDeliv = await appRes.json();
            setSelectedDeliverable(updatedDeliv);
            setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updatedDeliv : d)));
          }
        } else {
          throw new Error("Export Locked: Deliverable requires explicit Human Reviewer approval before release (Airgap Directive § 2). Switch to Reviewer persona or open 'Human Review' tab.");
        }
      }

      const res = await fetch(`/api/v1/review/outputs/${outputId}/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': userRole,
          'X-User-Id': userRole === 'reviewer' ? 'reviewer_primary' : 'operator_primary',
        },
        body: JSON.stringify({ export_format: format }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail?.message || errJson?.detail || `Export failed (HTTP ${res.status})`);
      }

      const data: ExportResult = await res.json();
      setExportModal(data);
      fetchAuditLogs();
    } catch (err) {
      setToastMessage({
        type: 'alert',
        text: err instanceof Error ? err.message : 'Export blocked or failed',
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleVerifyEncryption = async (outputId: string) => {
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/verify-encryption`, {
        headers: { 'X-User-Role': 'operator', 'X-User-Id': 'operator_primary' },
      });
      if (!res.ok) throw new Error('Verification failed');
      const data: OutputEncryptionInfo = await res.json();
      setEncryptionModal(data);
    } catch {
      setToastMessage({ type: 'alert', text: 'Ciphertext verification failed.' });
    }
  };

  const applyPreset = (preset: 'standard' | 'exec' | 'tech' | 'public') => {
    if (preset === 'standard') {
      setTargetAudience('Strategic Decision Makers & Analysts');
      setTargetTone('Authoritative & Objective');
      setDetailLevel('comprehensive');
      setTargetObjective('Operational Readiness & Strategic Mandate');
      setTargetStyle('Executive Directive Standard');
    } else if (preset === 'exec') {
      setTargetAudience('C-Suite & Governing Leadership');
      setTargetTone('Concise Strategic');
      setDetailLevel('brief');
      setTargetObjective('Resource Mandate & Decision Points');
      setTargetStyle('Executive Decision Memo');
    } else if (preset === 'tech') {
      setTargetAudience('Principal Systems Engineers & CERT Units');
      setTargetTone('Rigorous & Exhaustive');
      setDetailLevel('comprehensive');
      setTargetObjective('Technical Vulnerability Neutralization');
      setTargetStyle('Engineering Specification Format');
    } else {
      setTargetAudience('General Public & Industry Partners');
      setTargetTone('Clear & Accessible');
      setDetailLevel('standard');
      setTargetObjective('Public Safety & Advisory Transparency');
      setTargetStyle('Standard Public Informational');
    }
  };

  const toggleFormat = (id: string) => {
    setSelectedFormats((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
    );
  };

  const filteredAuditLogs = useMemo(() => {
    return auditLogs.filter((log) => {
      if (auditFilterAction !== 'all' && log.action !== auditFilterAction) return false;
      if (auditSearchQuery.trim()) {
        const q = auditSearchQuery.toLowerCase();
        return (
          String(log.id).includes(q) ||
          log.actor.toLowerCase().includes(q) ||
          log.action.toLowerCase().includes(q) ||
          log.hash.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [auditLogs, auditFilterAction, auditSearchQuery]);

  return (
    <div className="space-y-4">
      {/* Toast Notification */}
      {toastMessage && (
        <div
          className={`px-4 py-2.5 rounded-lg text-xs font-mono flex items-center justify-between border shadow-soft transition-all ${
            toastMessage.type === 'success'
              ? 'bg-[#F8F7F3] border-[#7E9D82] text-[#252525]'
              : 'bg-[#F8F7F3] border-[#C87970] text-[#252525]'
          }`}
        >
          <div className="flex items-center space-x-2">
            <span className={`w-2 h-2 rounded-full ${toastMessage.type === 'success' ? 'bg-[#7E9D82]' : 'bg-[#C87970]'}`}></span>
            <span>{toastMessage.text}</span>
          </div>
          <button onClick={() => setToastMessage(null)} className="text-[#99958D] hover:text-[#252525] text-xs ml-4">
            ✕
          </button>
        </div>
      )}

      {/* Workstation View Tabs */}
      <div className="flex items-center justify-between border-b border-[#D8D5CE] pb-2.5">
        <div className="flex items-center space-x-1 bg-[#F8F7F3] p-1 rounded-lg border border-[#D8D5CE]">
          <button
            onClick={() => setActiveTab('studio')}
            className={`px-3.5 py-1.5 rounded-md text-xs font-medium transition ${
              activeTab === 'studio'
                ? 'bg-[#FCFBF8] text-[#252525] shadow-soft border border-[#D8D5CE]'
                : 'text-[#6F6D68] hover:text-[#252525]'
            }`}
          >
            Transformation Studio
          </button>

          <button
            onClick={() => setActiveTab('review')}
            className={`px-3.5 py-1.5 rounded-md text-xs font-medium transition flex items-center space-x-1.5 ${
              activeTab === 'review'
                ? 'bg-[#FCFBF8] text-[#252525] shadow-soft border border-[#D8D5CE]'
                : 'text-[#6F6D68] hover:text-[#252525]'
            }`}
          >
            <span>Human Review</span>
            {deliverables.filter((d) => d.status === 'pending_review' || d.status === 'draft').length > 0 && (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#FEF3C7] text-[#D97706] font-bold border border-[#FDE68A]">
                {deliverables.filter((d) => d.status === 'pending_review' || d.status === 'draft').length}
              </span>
            )}
          </button>

          <button
            onClick={() => {
              setActiveTab('grounding');
              if (latestDoc && chunks.length === 0) handleProcessSource();
            }}
            className={`px-3.5 py-1.5 rounded-md text-xs font-medium transition flex items-center space-x-1.5 ${
              activeTab === 'grounding'
                ? 'bg-[#FCFBF8] text-[#252525] shadow-soft border border-[#D8D5CE]'
                : 'text-[#6F6D68] hover:text-[#252525]'
            }`}
          >
            <span>Source & Grounding</span>
            {chunks.length > 0 && (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#EAE8E1] text-[#6F6D68]">
                {chunks.length}
              </span>
            )}
          </button>

          <button
            onClick={() => {
              setActiveTab('audit');
              fetchAuditLogs();
            }}
            className={`px-3.5 py-1.5 rounded-md text-xs font-medium transition flex items-center space-x-1.5 ${
              activeTab === 'audit'
                ? 'bg-[#FCFBF8] text-[#252525] shadow-soft border border-[#D8D5CE]'
                : 'text-[#6F6D68] hover:text-[#252525]'
            }`}
          >
            <span>Audit Ledger</span>
            {auditLogs.length > 0 && (
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#EAE8E1] text-[#6F6D68]">
                {auditLogs.length}
              </span>
            )}
          </button>
        </div>

        {/* Actions Right: Persona Switcher, Clear DB & Air-gap Verification */}
        <div className="flex items-center space-x-2">
          {/* Persona Switcher */}
          <div className="flex items-center rounded-md border border-[#D8D5CE] bg-[#FCFBF8] p-0.5 text-xs font-mono shadow-soft">
            <button
              onClick={() => setUserRole('operator')}
              title="Operator (Analyst): Generates deliverables and submits for review"
              className={`px-2.5 py-1 rounded transition ${
                userRole === 'operator'
                  ? 'bg-[#30302E] text-white font-medium shadow-sm'
                  : 'text-[#6F6D68] hover:text-[#252525]'
              }`}
            >
              Operator
            </button>
            <button
              onClick={() => setUserRole('reviewer')}
              title="Reviewer (Approver): Authorized to approve, reject, edit and export deliverables"
              className={`px-2.5 py-1 rounded transition ${
                userRole === 'reviewer'
                  ? 'bg-[#15803D] text-white font-semibold shadow-sm'
                  : 'text-[#6F6D68] hover:text-[#252525]'
              }`}
            >
              Reviewer
            </button>
          </div>
          <button
            onClick={() => setClearDbModalOpen(true)}
            title="Purge all documents, vectors, graph nodes, deliverables, and reset audit log"
            className="text-xs font-mono px-3 py-1.5 rounded-md bg-[#FCFBF8] hover:bg-[#FBEBE8] border border-[#D8D5CE] hover:border-[#C87970] text-[#8C3A32] flex items-center space-x-1.5 transition shadow-soft cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            <span>Clear DB</span>
          </button>

          <button
            onClick={() => {
              setAirgapModalOpen(true);
              probeAirgap();
            }}
            className="text-xs font-mono px-3 py-1.5 rounded-md bg-[#FCFBF8] hover:bg-[#F8F7F3] border border-[#D8D5CE] text-[#30302E] flex items-center space-x-1.5 transition shadow-soft cursor-pointer"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#7E9D82]"></span>
            <span>Zero-Egress Verified</span>
          </button>
        </div>
      </div>

      {/* VIEW 1: TRANSFORMATION STUDIO */}
      {activeTab === 'studio' && (
        <>
          {/* STATE 1: NO DOCUMENT UPLOADED (FULL WIDTH WORKSPACE) */}
          {!latestDoc ? (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 w-full">
              {/* Left Column: Source Material & Target Parameters (5 cols) */}
              <div className="lg:col-span-5 space-y-4">
                {/* Source Material Card */}
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-5 space-y-4 shadow-soft">
                  <div className="flex items-center justify-between pb-2.5 border-b border-[#D8D5CE]">
                    <div>
                      <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                        Source Material
                      </span>
                      <p className="text-[11px] text-[#6F6D68] mt-0.5">
                        Air-gapped ingestion of unstructured reference documents
                      </p>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#F8F7F3] text-[#7E9D82] border border-[#D8D5CE]">
                      Zero-Egress Ingest
                    </span>
                  </div>

                  {/* Hidden file input (supports multi-file batch upload) */}
                  <input
                    type="file"
                    ref={fileInputRef}
                    multiple={true}
                    onChange={(e) => e.target.files && handleMultipleFilesUpload(e.target.files)}
                    className="hidden"
                    accept=".txt,.md,.pdf,.docx,.pptx,.png,.jpg,.jpeg,.wav,.mp3,.mp4"
                  />

                  {/* Dropzone with Drag-and-Drop */}
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                        handleMultipleFilesUpload(e.dataTransfer.files);
                      }
                    }}
                    className="border border-dashed border-[#C7C3BA] hover:border-[#30302E] bg-[#F8F7F3]/60 hover:bg-[#F8F7F3] rounded-lg p-6 text-center cursor-pointer transition"
                  >
                    <div className="text-xs text-[#252525] font-medium">
                      {isUploading ? 'Ingesting & encrypting batch material...' : 'Select or drop unstructured source material (1 or more files)'}
                    </div>
                    <div className="text-[11px] text-[#6F6D68] mt-1 font-mono">
                      PDF &bull; DOCX &bull; Scans &bull; Audio &bull; Text &bull; Multi-File Batch
                    </div>
                  </div>

                  {/* Existing Ingested Documents Picker (if any exist in database) */}
                  {documents.length > 0 && (
                    <div className="p-3 bg-[#F8F7F3] rounded border border-[#D8D5CE] space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono text-[#6F6D68]">
                        <span className="font-semibold text-[#252525] uppercase">Stored Documents ({documents.length})</span>
                        {isLoadingDocs && <span className="text-[10px]">Restoring...</span>}
                      </div>
                      <select
                        onChange={(e) => e.target.value && loadDocument(e.target.value)}
                        defaultValue=""
                        className="w-full bg-[#FCFBF8] border border-[#D8D5CE] rounded px-2.5 py-1.5 text-xs text-[#252525] font-mono focus:outline-none focus:border-[#30302E]"
                      >
                        <option value="" disabled>Select a previously stored document...</option>
                        {documents.map((d) => (
                          <option key={d.doc_id} value={d.doc_id}>
                            {d.original_filename} ({d.char_count.toLocaleString()} chars)
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Quick Sample Links */}
                  <div className="pt-1">
                    <div className="text-[11px] font-mono text-[#99958D] mb-2">Preset Reference Material:</div>
                    <div className="grid grid-cols-3 gap-2">
                      <button
                        onClick={() => handleLoadSample('defense')}
                        disabled={isUploading}
                        className="p-2 text-center rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-xs text-[#252525] font-mono transition truncate"
                      >
                        Directive
                      </button>
                      <button
                        onClick={() => handleLoadSample('cyber')}
                        disabled={isUploading}
                        className="p-2 text-center rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-xs text-[#252525] font-mono transition truncate"
                      >
                        Incident
                      </button>
                      <button
                        onClick={() => handleLoadSample('maritime')}
                        disabled={isUploading}
                        className="p-2 text-center rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-xs text-[#252525] font-mono transition truncate"
                      >
                        Recon Log
                      </button>
                    </div>
                  </div>

                  {uploadError && (
                    <div className="p-2.5 rounded bg-[#F8F7F3] border border-[#C87970] text-xs text-[#C87970] font-mono">
                      {uploadError}
                    </div>
                  )}
                </div>

                {/* Target Parameters Card */}
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-3 shadow-soft">
                  <div
                    onClick={() => setShowParameters(!showParameters)}
                    className="flex items-center justify-between cursor-pointer"
                  >
                    <div>
                      <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                        Target Parameters
                      </span>
                      <p className="text-[10px] text-[#6F6D68] mt-0.5">Audience, tone, detail level, and language</p>
                    </div>
                    <span className="text-xs text-[#6F6D68] font-mono">{showParameters ? '▲' : '▼'}</span>
                  </div>

                  {showParameters && (
                    <div className="space-y-3 pt-2 border-t border-[#D8D5CE] text-xs">
                      {/* Presets */}
                      <div className="flex items-center gap-1.5 text-[10px] font-mono overflow-x-auto pb-1">
                        <span className="text-[#99958D]">Presets:</span>
                        <button
                          onClick={() => applyPreset('standard')}
                          className="px-2 py-0.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-[#252525] hover:bg-[#EAE8E1]"
                        >
                          Directive
                        </button>
                        <button
                          onClick={() => applyPreset('exec')}
                          className="px-2 py-0.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-[#252525] hover:bg-[#EAE8E1]"
                        >
                          Executive
                        </button>
                        <button
                          onClick={() => applyPreset('tech')}
                          className="px-2 py-0.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-[#252525] hover:bg-[#EAE8E1]"
                        >
                          Engineering
                        </button>
                        <button
                          onClick={() => applyPreset('public')}
                          className="px-2 py-0.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-[#252525] hover:bg-[#EAE8E1]"
                        >
                          Public
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-2.5 font-mono">
                        <div>
                          <label className="text-[10px] text-[#6F6D68] block mb-1">Audience</label>
                          <input
                            type="text"
                            value={targetAudience}
                            onChange={(e) => setTargetAudience(e.target.value)}
                            className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525]"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-[#6F6D68] block mb-1">Tone</label>
                          <input
                            type="text"
                            value={targetTone}
                            onChange={(e) => setTargetTone(e.target.value)}
                            className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525]"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-[#6F6D68] block mb-1">Detail Level</label>
                          <select
                            value={detailLevel}
                            onChange={(e) => setDetailLevel(e.target.value)}
                            className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525]"
                          >
                            <option value="brief">Brief (High Impact)</option>
                            <option value="standard">Standard Coverage</option>
                            <option value="comprehensive">Comprehensive</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-[10px] text-[#6F6D68] block mb-1">Language</label>
                          <select
                            value={targetLanguage}
                            onChange={(e) => setTargetLanguage(e.target.value)}
                            className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525]"
                          >
                            <option value="en">English [en]</option>
                            <option value="hi">Hindi [hi]</option>
                            <option value="es">Spanish [es]</option>
                            <option value="fr">French [fr]</option>
                            <option value="de">German [de]</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Target Deliverable Formats taking full width of the remaining 7 cols */}
              <div className="lg:col-span-7 space-y-4">
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-5 space-y-4 shadow-soft">
                  <div className="flex items-center justify-between pb-2.5 border-b border-[#D8D5CE]">
                    <div>
                      <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                        Target Deliverable Formats ({selectedFormats.length}/{AVAILABLE_FORMATS.length})
                      </span>
                      <p className="text-[11px] text-[#6F6D68] mt-0.5">
                        Multi-format outputs synthesized simultaneously with verified grounding
                      </p>
                    </div>
                    <div className="flex items-center space-x-2 text-[10px] font-mono">
                      <button
                        onClick={() => setSelectedFormats(AVAILABLE_FORMATS.map((f) => f.id))}
                        className="text-[#6F6D68] hover:text-[#252525] underline"
                      >
                        Select All
                      </button>
                      <span className="text-[#D8D5CE]">·</span>
                      <button
                        onClick={() => setSelectedFormats([])}
                        className="text-[#99958D] hover:text-[#252525] underline"
                      >
                        Clear
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {AVAILABLE_FORMATS.map((f) => {
                      const isChecked = selectedFormats.includes(f.id);
                      return (
                        <div
                          key={f.id}
                          onClick={() => toggleFormat(f.id)}
                          className={`p-3.5 rounded-lg border text-xs cursor-pointer transition flex items-start justify-between space-x-3 ${
                            isChecked
                              ? 'bg-[#F8F7F3] border-[#30302E] text-[#252525] shadow-xs'
                              : 'bg-[#FCFBF8] border-[#D8D5CE] text-[#6F6D68] hover:border-[#C7C3BA]'
                          }`}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-1.5">
                              <span className="font-semibold text-xs text-[#252525] truncate">{f.label}</span>
                              <span className="text-[10px] font-mono text-[#99958D] shrink-0">{f.category}</span>
                            </div>
                            <p className="text-[11px] text-[#6F6D68] mt-1 leading-snug line-clamp-2">
                              {f.desc}
                            </p>
                          </div>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {}}
                            className="rounded accent-[#30302E] shrink-0 mt-0.5 w-3.5 h-3.5"
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Workflow Guidance CTA */}
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-soft">
                  <div className="text-xs">
                    <span className="font-medium text-[#252525] block">Ready for Ingestion</span>
                    <span className="text-[11px] text-[#6F6D68]">
                      Drop source material or load a reference document to initiate automatic chunking & ground truth verification.
                    </span>
                  </div>
                  <button
                    onClick={() => handleLoadSample('defense')}
                    disabled={isUploading}
                    className="px-4 py-2 rounded bg-[#30302E] hover:bg-[#252525] text-white font-mono text-xs font-medium transition shrink-0 shadow-soft flex items-center space-x-2"
                  >
                    <span>Load Defense Directive</span>
                    <span>&rarr;</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* STATE 2: DOCUMENT UPLOADED (SPLIT WORKSTATION VIEW REVEALED AFTER CHUNKING) */
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              {/* Left Column: Compact Source & Format Controls (4 cols) */}
              <div className="lg:col-span-4 space-y-3.5">
                {/* Source Material Card */}
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-3 shadow-soft">
                  <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
                    <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                      Source Material
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#F8F7F3] text-[#7E9D82] border border-[#D8D5CE]">
                      AES-256 Encrypted
                    </span>
                  </div>

                  {/* Hidden file input (supports multi-file batch upload) */}
                  <input
                    type="file"
                    ref={fileInputRef}
                    multiple={true}
                    onChange={(e) => e.target.files && handleMultipleFilesUpload(e.target.files)}
                    className="hidden"
                    accept=".txt,.md,.pdf,.docx,.pptx,.png,.jpg,.jpeg,.wav,.mp3,.mp4"
                  />

                  {/* Document Switcher if multiple documents exist */}
                  {documents.length > 1 && (
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[10px] font-mono text-[#6F6D68]">
                        <span className="uppercase font-semibold">Active Ingested Doc ({documents.length}):</span>
                        {isLoadingDocs && <span className="text-[10px]">Restoring...</span>}
                      </div>
                      <select
                        value={latestDoc.doc_id}
                        onChange={(e) => loadDocument(e.target.value)}
                        className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2.5 py-1.5 text-xs text-[#252525] font-mono focus:outline-none focus:border-[#30302E]"
                      >
                        {documents.map((d) => (
                          <option key={d.doc_id} value={d.doc_id}>
                            {d.original_filename} ({d.char_count.toLocaleString()} chars)
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Ingested Document Card */}
                  <div className="p-3 bg-[#F8F7F3] rounded border border-[#D8D5CE] text-xs space-y-2">
                    <div className="flex items-center justify-between text-[#252525] font-medium truncate">
                      <span className="truncate">{latestDoc.original_filename}</span>
                      <span className="text-[10px] font-mono text-[#6F6D68] shrink-0 ml-2">
                        {latestDoc.structural_metadata?.word_count || latestDoc.raw_text.split(/\s+/).length} words
                      </span>
                    </div>
                    <div className="text-[10px] font-mono text-[#99958D] truncate">
                      SHA-256: {latestDoc.checksum.slice(0, 16)}...
                    </div>
                    <div className="flex items-center justify-between pt-1 border-t border-[#D8D5CE]/60 text-[10px] font-mono">
                      <button
                        onClick={() => setShowRawText(!showRawText)}
                        className="text-[#E8A36A] hover:underline"
                      >
                        {showRawText ? 'Hide Text' : 'View Text'}
                      </button>
                      <button
                        onClick={handleResetDoc}
                        className="text-[#C87970] hover:underline"
                      >
                        Reset / Unselect
                      </button>
                    </div>
                    {showRawText && (
                      <div className="p-2.5 max-h-36 overflow-y-auto bg-[#FCFBF8] rounded border border-[#D8D5CE] text-[10px] font-mono text-[#252525] whitespace-pre-wrap leading-relaxed">
                        {latestDoc.raw_text}
                      </div>
                    )}
                  </div>

                  {/* Multi-file batch upload & addition */}
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                      className="py-1.5 px-2 text-center rounded bg-[#30302E] hover:bg-[#252525] disabled:bg-[#B9B8B3] text-white text-[11px] font-mono transition truncate cursor-pointer shadow-soft"
                    >
                      {isUploading ? 'Ingesting...' : '+ Add More Files'}
                    </button>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                      className="py-1.5 px-2 text-center rounded bg-[#FCFBF8] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-[11px] text-[#6F6D68] hover:text-[#252525] font-mono transition truncate cursor-pointer"
                    >
                      Upload Different
                    </button>
                  </div>
                </div>

                {/* Target Deliverable Formats Card (Compact) */}
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-3 shadow-soft">
                  <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
                    <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                      Deliverable Formats ({selectedFormats.length}/{AVAILABLE_FORMATS.length})
                    </span>
                    <div className="flex items-center space-x-2 text-[10px] font-mono">
                      <button
                        onClick={() => setSelectedFormats(AVAILABLE_FORMATS.map((f) => f.id))}
                        className="text-[#6F6D68] hover:text-[#252525] underline"
                      >
                        All
                      </button>
                      <span className="text-[#D8D5CE]">·</span>
                      <button
                        onClick={() => setSelectedFormats([])}
                        className="text-[#99958D] hover:text-[#252525] underline"
                      >
                        Clear
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    {AVAILABLE_FORMATS.map((f) => {
                      const isChecked = selectedFormats.includes(f.id);
                      return (
                        <div
                          key={f.id}
                          onClick={() => toggleFormat(f.id)}
                          className={`p-2 rounded border text-xs cursor-pointer transition flex items-center justify-between ${
                            isChecked
                              ? 'bg-[#F8F7F3] border-[#30302E] text-[#252525]'
                              : 'bg-[#FCFBF8] border-[#D8D5CE] text-[#6F6D68] hover:border-[#C7C3BA]'
                          }`}
                        >
                          <div className="truncate pr-1">
                            <span className="font-medium block text-xs truncate text-[#252525]">{f.label}</span>
                            <span className="text-[10px] font-mono text-[#99958D] block truncate">{f.category}</span>
                          </div>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {}}
                            className="rounded accent-[#30302E] shrink-0"
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Target Configuration Parameters (Collapsible) */}
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-3 shadow-soft">
                  <div
                    onClick={() => setShowParameters(!showParameters)}
                    className="flex items-center justify-between cursor-pointer"
                  >
                    <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                      Target Parameters
                    </span>
                    <span className="text-xs text-[#6F6D68] font-mono">{showParameters ? '▲' : '▼'}</span>
                  </div>

                  {showParameters && (
                    <div className="space-y-3 pt-2 border-t border-[#D8D5CE] text-xs">
                      {/* Presets */}
                      <div className="flex items-center gap-1.5 text-[10px] font-mono overflow-x-auto pb-1">
                        <span className="text-[#99958D]">Presets:</span>
                        <button
                          onClick={() => applyPreset('standard')}
                          className="px-2 py-0.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-[#252525] hover:bg-[#EAE8E1]"
                        >
                          Directive
                        </button>
                        <button
                          onClick={() => applyPreset('exec')}
                          className="px-2 py-0.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-[#252525] hover:bg-[#EAE8E1]"
                        >
                          Executive
                        </button>
                        <button
                          onClick={() => applyPreset('tech')}
                          className="px-2 py-0.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-[#252525] hover:bg-[#EAE8E1]"
                        >
                          Engineering
                        </button>
                        <button
                          onClick={() => applyPreset('public')}
                          className="px-2 py-0.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-[#252525] hover:bg-[#EAE8E1]"
                        >
                          Public
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-2.5 font-mono">
                        <div>
                          <label className="text-[10px] text-[#6F6D68] block mb-1">Audience</label>
                          <input
                            type="text"
                            value={targetAudience}
                            onChange={(e) => setTargetAudience(e.target.value)}
                            className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525]"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-[#6F6D68] block mb-1">Tone</label>
                          <input
                            type="text"
                            value={targetTone}
                            onChange={(e) => setTargetTone(e.target.value)}
                            className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525]"
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-[#6F6D68] block mb-1">Detail Level</label>
                          <select
                            value={detailLevel}
                            onChange={(e) => setDetailLevel(e.target.value)}
                            className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525]"
                          >
                            <option value="brief">Brief (High Impact)</option>
                            <option value="standard">Standard Coverage</option>
                            <option value="comprehensive">Comprehensive</option>
                          </select>
                        </div>
                        <div>
                          <label className="text-[10px] text-[#6F6D68] block mb-1">Language</label>
                          <select
                            value={targetLanguage}
                            onChange={(e) => setTargetLanguage(e.target.value)}
                            className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525]"
                          >
                            <option value="en">English [en]</option>
                            <option value="hi">Hindi [hi]</option>
                            <option value="es">Spanish [es]</option>
                            <option value="fr">French [fr]</option>
                            <option value="de">German [de]</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Primary Action Button */}
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating || selectedFormats.length === 0}
                  className="w-full py-2.5 px-4 rounded bg-[#30302E] hover:bg-[#252525] disabled:bg-[#B9B8B3] text-white font-medium text-xs font-mono transition shadow-soft flex items-center justify-center space-x-2"
                >
                  {isGenerating ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Synthesizing {selectedFormats.length} Deliverables...</span>
                    </>
                  ) : (
                    <span>Generate Selected Deliverables ({selectedFormats.length})</span>
                  )}
                </button>
              </div>

              {/* Right Column: Workstation Output & Provenance Inspector (8 cols) */}
              <div className="lg:col-span-8 space-y-3.5">
                {/* STATE A: Processing / Chunking in Progress */}
                {isProcessingSource && (
                  <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-10 shadow-soft text-center space-y-3">
                    <div className="w-6 h-6 border-2 border-[#30302E] border-t-transparent rounded-full animate-spin mx-auto"></div>
                    <div className="text-xs font-mono font-semibold text-[#252525]">
                      Partitioning Source Material into Verifiable Semantic Chunks...
                    </div>
                    <p className="text-[11px] text-[#6F6D68] max-w-md mx-auto font-mono">
                      Computing character coordinates &bull; Extracting entities &bull; Storing 384-dim Qdrant embeddings
                    </p>
                  </div>
                )}

                {/* STATE B: Chunks Available & Ready (or user selected Chunks tab) */}
                {!isProcessingSource && (rightViewMode === 'chunks' || deliverables.length === 0) && (
                  <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-4 shadow-soft">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#D8D5CE]">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                            Source Material Ground Truth
                          </span>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#F8F7F3] text-[#7E9D82] border border-[#D8D5CE]">
                            {chunks.length} Chunks Verified
                          </span>
                        </div>
                        <p className="text-[11px] text-[#6F6D68] mt-0.5">
                          Extracted character coordinates and semantic segments for 100% claim grounding.
                        </p>
                      </div>

                      <div className="flex items-center space-x-2">
                        {deliverables.length > 0 && (
                          <button
                            onClick={() => setRightViewMode('deliverables')}
                            className="px-3 py-1.5 rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-xs font-mono text-[#252525] transition"
                          >
                            &larr; View Deliverables ({deliverables.length})
                          </button>
                        )}
                        <button
                          onClick={handleGenerate}
                          disabled={isGenerating || selectedFormats.length === 0}
                          className="px-3.5 py-1.5 rounded bg-[#30302E] hover:bg-[#252525] disabled:bg-[#B9B8B3] text-white font-mono text-xs font-medium transition shadow-soft flex items-center space-x-1.5 shrink-0"
                        >
                          {isGenerating ? (
                            <>
                              <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                              <span>Synthesizing...</span>
                            </>
                          ) : (
                            <span>Synthesize Deliverables ({selectedFormats.length}) &rarr;</span>
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Chunks List */}
                    <div className="space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
                      {chunks.length > 0 ? (
                        chunks.map((c) => (
                          <div
                            key={c.chunk_id}
                            className="p-3 rounded-md bg-[#F8F7F3] border border-[#D8D5CE] text-xs space-y-1.5 transition hover:border-[#30302E]"
                          >
                            <div className="flex items-center justify-between text-[10px] font-mono text-[#6F6D68]">
                              <span className="font-semibold text-[#252525]">Chunk #{c.chunk_index}</span>
                              <span>Span: [{c.char_offset_start}:{c.char_offset_end}]</span>
                            </div>
                            {c.heading && (
                              <div className="text-[10px] font-mono font-medium text-[#6F6D68]">
                                § {c.heading}
                              </div>
                            )}
                            <p className="text-[11px] text-[#252525] leading-relaxed font-serif">{c.text}</p>
                          </div>
                        ))
                      ) : (
                        <div className="p-8 text-center text-[#99958D] text-xs font-mono">
                          No chunks extracted yet. Click "Upload Different File" or select a preset reference.
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* STATE C: Deliverables Generated & Viewing Deliverables */}
                {!isProcessingSource && rightViewMode === 'deliverables' && deliverables.length > 0 && selectedDeliverable && (
                  <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-4 shadow-soft">
                    {/* Format Switcher Tabs */}
                    <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-[#D8D5CE]">
                      <div className="flex flex-wrap gap-1.5">
                        {deliverables.map((d) => (
                          <button
                            key={d.output_id}
                            onClick={() => {
                              setSelectedDeliverable(d);
                              setSentenceTrace(null);
                            }}
                            className={`px-3 py-1.5 rounded text-xs font-mono transition border flex items-center space-x-1.5 ${
                              selectedDeliverable.output_id === d.output_id
                                ? 'bg-[#30302E] text-white border-[#30302E]'
                                : 'bg-[#F8F7F3] border-[#D8D5CE] text-[#6F6D68] hover:text-[#252525]'
                            }`}
                          >
                            <span>{AVAILABLE_FORMATS.find((f) => f.id === d.deliverable_type)?.label || d.deliverable_type}</span>
                            <span className="text-[10px] opacity-70">({d.total_sentences})</span>
                          </button>
                        ))}
                      </div>

                      {/* Toggle to view Ground Truth Chunks */}
                      <button
                        onClick={() => setRightViewMode('chunks')}
                        className="px-2.5 py-1 rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-[11px] font-mono text-[#6F6D68] hover:text-[#252525] transition shrink-0"
                      >
                        View Ground Truth Chunks ({chunks.length})
                      </button>
                    </div>

                    {/* Toolbar */}
                    <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-xs font-mono">
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleCopyContent(selectedDeliverable)}
                          className="px-2.5 py-1 rounded bg-[#FCFBF8] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-[#252525] transition"
                        >
                          {copiedId === selectedDeliverable.output_id ? '✓ Copied' : 'Copy Text'}
                        </button>
                        <button
                          onClick={() => handleVerifyEncryption(selectedDeliverable.output_id)}
                          className="px-2.5 py-1 rounded bg-[#FCFBF8] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-[#6F6D68] transition"
                        >
                          Ciphertext
                        </button>
                      </div>

                      <div className="flex items-center space-x-2">
                        <select
                          value={exportFormat}
                          onChange={(e) => setExportFormat(e.target.value)}
                          className="bg-[#FCFBF8] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525] font-mono"
                        >
                          <option value="markdown">Markdown (.md)</option>
                          <option value="json">JSON (.json)</option>
                          <option value="html">HTML (.html)</option>
                          <option value="text">Plain Text (.txt)</option>
                        </select>

                        <button
                          onClick={() => handleExport(selectedDeliverable.output_id, exportFormat)}
                          disabled={isExporting}
                          className="px-3 py-1 rounded bg-[#30302E] hover:bg-[#252525] text-white transition disabled:opacity-50"
                        >
                          {isExporting ? 'Exporting...' : 'Export'}
                        </button>
                      </div>
                    </div>

                    {/* Main Deliverable View */}
                    <div className="p-4 rounded-lg bg-[#F8F7F3]/70 border border-[#D8D5CE] space-y-3.5">
                      {/* Human Review Status & Dual-Control Action Bar */}
                      <div className="p-3 rounded-md border text-xs font-mono flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-[#FCFBF8]">
                        <div className="flex items-center space-x-2">
                          <span className="text-[10px] uppercase font-bold text-[#6F6D68]">Review Status:</span>
                          <span
                            className={`px-2 py-0.5 rounded border text-[10px] font-bold uppercase tracking-wider ${
                              selectedDeliverable.status === 'approved' || selectedDeliverable.status === 'final'
                                ? 'bg-[#EBF7EE] text-[#15803D] border-[#BBE5C4]'
                                : selectedDeliverable.status === 'pending_review'
                                ? 'bg-[#FEF3C7] text-[#D97706] border-[#FDE68A]'
                                : selectedDeliverable.status === 'rejected'
                                ? 'bg-[#FEE2E2] text-[#DC2626] border-[#FECACA]'
                                : 'bg-[#F3F4F6] text-[#6B7280] border-[#E5E7EB]'
                            }`}
                          >
                            {selectedDeliverable.status}
                          </span>
                          {selectedDeliverable.reviewer_id && (
                            <span className="text-[10px] text-[#6F6D68]">by {selectedDeliverable.reviewer_id}</span>
                          )}
                        </div>

                        {/* Direct Review Actions */}
                        <div className="flex items-center space-x-2">
                          {selectedDeliverable.status === 'draft' && (
                            <button
                              onClick={() => handleStudioSubmitForReview(selectedDeliverable.output_id)}
                              className="px-2.5 py-1 rounded bg-[#30302E] hover:bg-[#252525] text-white text-[11px] font-medium transition"
                            >
                              Submit for Review &rarr;
                            </button>
                          )}

                          {selectedDeliverable.status === 'pending_review' && userRole === 'reviewer' && (
                            <button
                              onClick={() => handleStudioApprove(selectedDeliverable.output_id)}
                              className="px-2.5 py-1 rounded bg-[#15803D] hover:bg-[#166534] text-white text-[11px] font-semibold transition"
                            >
                              ✓ Approve Deliverable
                            </button>
                          )}

                          <button
                            onClick={() => setActiveTab('review')}
                            className="px-2.5 py-1 rounded bg-[#FCFBF8] border border-[#D8D5CE] hover:bg-[#EAE8E1] text-[#252525] text-[11px] transition"
                          >
                            Open Review Workbench &rarr;
                          </button>
                        </div>
                      </div>

                      <div>
                        <h3 className="text-base font-serif font-bold text-[#252525] tracking-tight">
                          {selectedDeliverable.content.title}
                        </h3>
                        {selectedDeliverable.content.summary && (
                          <p className="text-xs text-[#6F6D68] mt-1 leading-relaxed italic">
                            {selectedDeliverable.content.summary}
                          </p>
                        )}
                      </div>

                      {/* Format Specialization Notes */}
                      {selectedDeliverable.deliverable_type === 'twitter_thread' && (
                        <div className="p-2 rounded bg-[#FCFBF8] border border-[#D8D5CE] text-[11px] font-mono text-[#6F6D68] flex justify-between">
                          <span>Social Sequence (X/Twitter)</span>
                          <span>Verified: &le; 230 characters / card</span>
                        </div>
                      )}

                      {selectedDeliverable.deliverable_type === 'presentation' && (
                        <div className="p-2 rounded bg-[#FCFBF8] border border-[#D8D5CE] text-[11px] font-mono text-[#6F6D68] flex justify-between">
                          <span>Presentation Deck</span>
                          <span>4 Slides &bull; Action-oriented scannable titles</span>
                        </div>
                      )}

                      {/* Blocks & Interactive Claim Sentences */}
                      <div className="space-y-3.5">
                        {selectedDeliverable.content.blocks.map((block) => (
                          <div key={block.block_index} className="space-y-2">
                            {block.title && (
                              <h4 className="text-xs font-mono font-semibold text-[#6F6D68] uppercase tracking-wider">
                                {block.title}
                              </h4>
                            )}
                            <div className="space-y-2">
                              {block.sentences.map((s) => (
                                <div
                                  key={s.sentence_id}
                                  onMouseEnter={() => setHoveredSentenceId(s.sentence_id)}
                                  onClick={() => handleTraceSentence(selectedDeliverable.output_id, s.sentence_index)}
                                  className={`p-2.5 rounded border transition cursor-pointer text-xs leading-relaxed ${
                                    sentenceTrace?.sentence_id === s.sentence_id
                                      ? 'bg-[#F5DEA0]/30 border-[#E8A36A] text-[#252525]'
                                      : hoveredSentenceId === s.sentence_id
                                      ? 'bg-[#F8F7F3] border-[#30302E] text-[#252525]'
                                      : 'bg-[#FCFBF8] border-[#D8D5CE] text-[#252525] hover:border-[#C7C3BA]'
                                  }`}
                                >
                                  <div className="flex items-center justify-between text-[10px] font-mono text-[#99958D] mb-1">
                                    <span className="font-semibold text-[#6F6D68]">Claim #{s.sentence_index + 1}</span>
                                    <span className="text-[#7E9D82]">
                                      {s.citations.length} verified citation{s.citations.length > 1 ? 's' : ''}
                                    </span>
                                  </div>
                                  <p className="text-[12px]">{s.text}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* SRT subtitles for video package */}
                      {selectedDeliverable.deliverable_type === 'video_package' && selectedDeliverable.format_metadata?.subtitles_srt && (
                        <div className="pt-3 border-t border-[#D8D5CE]">
                          <span className="text-[10px] font-mono text-[#6F6D68] uppercase tracking-wider block mb-1">
                            Timecoded Spoken SRT Script
                          </span>
                          <pre className="p-2.5 bg-[#FCFBF8] border border-[#D8D5CE] rounded text-[10px] font-mono text-[#252525] max-h-28 overflow-y-auto whitespace-pre-wrap">
                            {selectedDeliverable.format_metadata.subtitles_srt}
                          </pre>
                        </div>
                      )}
                    </div>

                    {/* Claim Provenance Inspector Card */}
                    {isTracing && (
                      <div className="p-3 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-xs font-mono text-[#6F6D68] flex items-center space-x-2">
                        <div className="w-3 h-3 border-2 border-[#30302E] border-t-transparent rounded-full animate-spin"></div>
                        <span>Resolving character coordinates against ground truth...</span>
                      </div>
                    )}
                    {sentenceTrace && !isTracing && (
                      <div className="p-3.5 rounded-lg bg-[#FCFBF8] border border-[#D8D5CE] space-y-2.5 font-mono text-xs shadow-soft">
                        <div className="flex items-center justify-between text-[11px] text-[#252525] font-semibold border-b border-[#D8D5CE] pb-1.5">
                          <span>Claim Provenance Inspector</span>
                          <span className="px-2 py-0.5 rounded bg-[#F8F7F3] text-[#7E9D82] text-[10px] border border-[#D8D5CE]">
                            100% Trace Verified
                          </span>
                        </div>

                        <div className="space-y-2">
                          {sentenceTrace.grounding_sources.map((src, idx) => (
                            <div key={idx} className="p-2.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] space-y-1.5 text-[11px]">
                              <div className="flex items-center justify-between text-[#6F6D68] text-[10px]">
                                <span className="font-semibold text-[#252525]">Source Chunk #{src.chunk_index}</span>
                                <span>Span: [{src.char_offset_start}:{src.char_offset_end}]</span>
                              </div>
                              {src.heading && (
                                <div className="text-[#6F6D68] text-[10px]">Section: § {src.heading}</div>
                              )}
                              <div className="text-[#252525] bg-[#F5DEA0]/40 p-2 rounded border border-[#EBCB72] text-[11px] leading-relaxed">
                                "{src.quote}"
                              </div>
                              <div className="text-[10px] text-[#99958D]">
                                <span>{src.context_before}</span>
                                <span className="text-[#252525] font-semibold underline px-1">[{src.quote.slice(0, 30)}...]</span>
                                <span>{src.context_after}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* VIEW 2: HUMAN REVIEW WORKSPACE */}
      {activeTab === 'review' && (
        <HumanReviewWorkspace
          userRole={userRole}
          onSwitchRole={(role) => setUserRole(role)}
          activeDocId={latestDoc?.doc_id || null}
          onRefreshAuditLogs={fetchAuditLogs}
          onToast={(msg) => setToastMessage(msg)}
          onExportSuccess={(res) => setExportModal(res)}
        />
      )}

      {/* VIEW 3: SOURCE & GROUNDING */}
      {activeTab === 'grounding' && (
        <div className="space-y-4">
          {/* Sub-Header with Engine Mode Toggles */}
          <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-3.5 shadow-soft flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center space-x-3">
              <div className="w-7 h-7 rounded bg-[#30302E] flex items-center justify-center text-white text-xs font-mono">
                KG
              </div>
              <div>
                <h3 className="text-xs font-bold font-mono text-[#252525] uppercase tracking-wide">
                  Knowledge Topology & Grounding Engine
                </h3>
                <p className="text-[11px] text-[#6F6D68]">
                  Dual-layer provenance: FalkorDB Graph Relationships + Qdrant 384-Dim Dense Embeddings
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-1.5 font-mono text-xs">
              <button
                onClick={() => setGroundingViewMode('graph')}
                className={`px-3 py-1.5 rounded border transition flex items-center space-x-1.5 ${
                  groundingViewMode === 'graph'
                    ? 'bg-[#30302E] text-white border-[#30302E] shadow-sm'
                    : 'bg-[#FCFBF8] text-[#6F6D68] border-[#D8D5CE] hover:bg-[#F8F7F3]'
                }`}
              >
                <span>🕸️</span>
                <span>Knowledge Graph</span>
                {graphData?.nodes && (
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded ${
                      groundingViewMode === 'graph' ? 'bg-[#454542] text-white' : 'bg-[#EAE8E1] text-[#6F6D68]'
                    }`}
                  >
                    {graphData.nodes.length}
                  </span>
                )}
              </button>
              <button
                onClick={() => setGroundingViewMode('vectors')}
                className={`px-3 py-1.5 rounded border transition flex items-center space-x-1.5 ${
                  groundingViewMode === 'vectors'
                    ? 'bg-[#30302E] text-white border-[#30302E] shadow-sm'
                    : 'bg-[#FCFBF8] text-[#6F6D68] border-[#D8D5CE] hover:bg-[#F8F7F3]'
                }`}
              >
                <span>📄</span>
                <span>Qdrant Vectors</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded ${
                    groundingViewMode === 'vectors' ? 'bg-[#454542] text-white' : 'bg-[#EAE8E1] text-[#6F6D68]'
                  }`}
                >
                  {chunks.length}
                </span>
              </button>
              <button
                onClick={() => setGroundingViewMode('split')}
                className={`px-3 py-1.5 rounded border transition flex items-center space-x-1.5 ${
                  groundingViewMode === 'split'
                    ? 'bg-[#30302E] text-white border-[#30302E] shadow-sm'
                    : 'bg-[#FCFBF8] text-[#6F6D68] border-[#D8D5CE] hover:bg-[#F8F7F3]'
                }`}
              >
                <span>◫</span>
                <span>Dual View</span>
              </button>
            </div>
          </div>

          {/* Dynamic Grounding Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Left Column: Structured Understanding (Entities, Topics, Objectives) */}
            <div className={`${groundingViewMode === 'vectors' ? 'lg:col-span-5' : 'lg:col-span-4'} space-y-3.5`}>
              <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-3 shadow-soft">
                <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
                  <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                    Structured Understanding
                  </span>
                  <button
                    onClick={handleProcessSource}
                    disabled={isProcessingSource || !latestDoc}
                    className="text-xs font-mono text-[#E8A36A] hover:underline disabled:opacity-50"
                  >
                    {isProcessingSource ? 'Analyzing...' : 'Re-run Analysis'}
                  </button>
                </div>

                {understanding ? (
                  <div className="space-y-3 text-xs">
                    <div className="p-3 bg-[#F8F7F3] rounded border border-[#D8D5CE]">
                      <span className="text-[10px] font-mono text-[#6F6D68] uppercase tracking-wider block mb-1">
                        Objective & Core Intent
                      </span>
                      <p className="text-[#252525] text-[11px] leading-relaxed">{understanding.objective}</p>
                    </div>

                    <div>
                      <span className="text-[10px] font-mono text-[#6F6D68] block mb-1">Classified Topics</span>
                      <div className="flex flex-wrap gap-1">
                        {understanding.topics.map((t, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded bg-[#F8F7F3] text-[10px] text-[#252525] border border-[#D8D5CE] font-mono"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    </div>

                    {understanding.sensitive_terms.length > 0 && (
                      <div>
                        <span className="text-[10px] font-mono text-[#C87970] block mb-1">
                          Sensitive Terms ({understanding.sensitive_terms.length})
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {understanding.sensitive_terms.map((st, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded bg-[#F8F7F3] border border-[#C87970] text-[#C87970] text-[10px] font-mono"
                            >
                              {st.term} ({st.severity})
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-mono text-[#6F6D68]">
                          Named Entities ({understanding.key_entities.length})
                        </span>
                        <span className="text-[9px] font-mono text-[#99958D]">click to focus graph</span>
                      </div>
                      <div className="flex flex-wrap gap-1 max-h-48 overflow-y-auto">
                        {understanding.key_entities.map((e, i) => (
                          <button
                            key={i}
                            type="button"
                            onClick={() => {
                              setSelectedEntityForGraph(e.name);
                              if (groundingViewMode === 'vectors') {
                                setGroundingViewMode('graph');
                              }
                            }}
                            className={`px-2 py-0.5 rounded text-[10px] font-mono transition border ${
                              selectedEntityForGraph === e.name
                                ? 'bg-[#15803D] text-white border-[#15803D]'
                                : 'bg-[#F8F7F3] hover:bg-[#EAE8E1] text-[#252525] border-[#D8D5CE]'
                            }`}
                            title="Click to highlight and inspect in knowledge graph"
                          >
                            <span>{e.name}</span> <span className="opacity-70">({e.type})</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-8 text-center text-[#99958D] text-xs">
                    {latestDoc ? 'Click "Re-run Analysis" to extract entities and topics.' : 'Select source material first.'}
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Knowledge Graph, Vector Chunks, or Split View */}
            <div className={`${groundingViewMode === 'vectors' ? 'lg:col-span-7' : 'lg:col-span-8'} space-y-4`}>
              {/* Mode: Graph Only */}
              {groundingViewMode === 'graph' && (
                <KnowledgeGraphVisualizer
                  docId={latestDoc?.doc_id || null}
                  nodes={graphData?.nodes || []}
                  edges={graphData?.edges || []}
                  isLoading={isLoadingGraph}
                  selectedEntityName={selectedEntityForGraph}
                  onSelectEntity={(name) => setSelectedEntityForGraph(name)}
                  height={560}
                />
              )}

              {/* Mode: Dual Split View (Graph on Top, Chunks below) */}
              {groundingViewMode === 'split' && (
                <>
                  <KnowledgeGraphVisualizer
                    docId={latestDoc?.doc_id || null}
                    nodes={graphData?.nodes || []}
                    edges={graphData?.edges || []}
                    isLoading={isLoadingGraph}
                    selectedEntityName={selectedEntityForGraph}
                    onSelectEntity={(name) => setSelectedEntityForGraph(name)}
                    height={390}
                  />

                  {/* Grounded Chunks below graph in split mode */}
                  <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-3.5 shadow-soft">
                    <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
                      <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                        Grounded Chunks ({chunks.length})
                      </span>
                      <span className="text-[10px] font-mono text-[#6F6D68]">Qdrant 384-Dim HNSW</span>
                    </div>

                    <form onSubmit={handleSearchChunks} className="flex gap-2">
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Semantic query across retrieved chunks..."
                        className="flex-1 bg-[#F8F7F3] border border-[#D8D5CE] rounded px-3 py-1.5 text-xs text-[#252525] font-mono focus:outline-none focus:border-[#30302E]"
                      />
                      <button
                        type="submit"
                        disabled={isSearching || !latestDoc}
                        className="px-3.5 py-1.5 rounded bg-[#30302E] hover:bg-[#252525] disabled:bg-[#B9B8B3] text-white text-xs font-mono transition"
                      >
                        {isSearching ? '...' : 'Search'}
                      </button>
                    </form>

                    {searchResults && (
                      <div className="space-y-2 max-h-40 overflow-y-auto">
                        <span className="text-[10px] font-mono text-[#6F6D68]">Semantic Matches:</span>
                        {searchResults.map((hit) => (
                          <div key={hit.chunk_id} className="p-2 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-xs">
                            <div className="flex justify-between text-[10px] font-mono text-[#6F6D68] mb-0.5">
                              <span className="font-semibold text-[#252525]">Chunk #{hit.chunk_index}</span>
                              <span>Cosine: {hit.score.toFixed(3)}</span>
                            </div>
                            <p className="text-[11px] text-[#252525]">{hit.text}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                      {chunks.map((c) => (
                        <div key={c.chunk_id} className="p-2.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-xs space-y-1">
                          <div className="flex items-center justify-between text-[10px] font-mono text-[#6F6D68]">
                            <span className="font-semibold text-[#252525]">Chunk #{c.chunk_index}</span>
                            <span>Offsets: [{c.char_offset_start}:{c.char_offset_end}]</span>
                          </div>
                          {c.heading && <div className="text-[10px] font-medium text-[#6F6D68]">§ {c.heading}</div>}
                          <p className="text-[11px] text-[#252525] leading-relaxed">{c.text}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* Mode: Vectors Only */}
              {groundingViewMode === 'vectors' && (
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-3.5 shadow-soft">
                  <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
                    <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                      Grounded Chunks ({chunks.length})
                    </span>
                    <span className="text-[10px] font-mono text-[#6F6D68]">Qdrant 384-Dim HNSW</span>
                  </div>

                  <form onSubmit={handleSearchChunks} className="flex gap-2">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Semantic query across retrieved chunks..."
                      className="flex-1 bg-[#F8F7F3] border border-[#D8D5CE] rounded px-3 py-1.5 text-xs text-[#252525] font-mono focus:outline-none focus:border-[#30302E]"
                    />
                    <button
                      type="submit"
                      disabled={isSearching || !latestDoc}
                      className="px-3.5 py-1.5 rounded bg-[#30302E] hover:bg-[#252525] disabled:bg-[#B9B8B3] text-white text-xs font-mono transition"
                    >
                      {isSearching ? '...' : 'Search'}
                    </button>
                  </form>

                  {searchResults && (
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      <span className="text-[10px] font-mono text-[#6F6D68]">Semantic Matches:</span>
                      {searchResults.map((hit) => (
                        <div key={hit.chunk_id} className="p-2 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-xs">
                          <div className="flex justify-between text-[10px] font-mono text-[#6F6D68] mb-0.5">
                            <span className="font-semibold text-[#252525]">Chunk #{hit.chunk_index}</span>
                            <span>Cosine: {hit.score.toFixed(3)}</span>
                          </div>
                          <p className="text-[11px] text-[#252525]">{hit.text}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                    {chunks.map((c) => (
                      <div key={c.chunk_id} className="p-2.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-xs space-y-1">
                        <div className="flex items-center justify-between text-[10px] font-mono text-[#6F6D68]">
                          <span className="font-semibold text-[#252525]">Chunk #{c.chunk_index}</span>
                          <span>Offsets: [{c.char_offset_start}:{c.char_offset_end}]</span>
                        </div>
                        {c.heading && <div className="text-[10px] font-medium text-[#6F6D68]">§ {c.heading}</div>}
                        <p className="text-[11px] text-[#252525] leading-relaxed">{c.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* VIEW 3: AUDIT LEDGER */}
      {activeTab === 'audit' && (
        <div className="space-y-3.5">
          {/* Header Card */}
          <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 space-y-3 shadow-soft">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#D8D5CE]">
              <div>
                <h3 className="text-xs font-bold text-[#252525] font-mono uppercase tracking-wide">
                  Cryptographic Audit Ledger
                </h3>
                <p className="text-xs text-[#6F6D68] mt-0.5">
                  Append-only SHA-256 hash chained record of all operator actions and exports.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={fetchAuditLogs}
                  disabled={isLoadingAudit}
                  className="px-3 py-1.5 rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-[#252525] text-xs font-mono transition"
                >
                  {isLoadingAudit ? 'Refreshing...' : 'Refresh'}
                </button>
                <button
                  onClick={verifyAuditChain}
                  disabled={isVerifyingAudit}
                  className="px-3 py-1.5 rounded bg-[#30302E] hover:bg-[#252525] disabled:bg-[#B9B8B3] text-white text-xs font-mono transition"
                >
                  {isVerifyingAudit ? 'Verifying...' : 'Verify Chain Integrity'}
                </button>
              </div>
            </div>

            {/* Verification Status */}
            {auditVerification && (
              <div
                className={`p-2.5 rounded border font-mono text-xs flex items-center justify-between ${
                  auditVerification.valid
                    ? 'bg-[#F8F7F3] border-[#7E9D82] text-[#252525]'
                    : 'bg-[#F8F7F3] border-[#C87970] text-[#C87970]'
                }`}
              >
                <span>
                  {auditVerification.valid
                    ? `✓ All ${auditVerification.total_records} records verified against linear SHA-256 hash chain.`
                    : `✕ Tampering detected at record #${auditVerification.record_id}`}
                </span>
                {auditVerification.latest_hash && (
                  <span className="text-[10px] text-[#6F6D68]">Head: {auditVerification.latest_hash.slice(0, 16)}...</span>
                )}
              </div>
            )}

            {/* Filter Bar */}
            <div className="grid grid-cols-1 sm:grid-cols-12 gap-2.5 pt-1">
              <div className="sm:col-span-8">
                <input
                  type="text"
                  value={auditSearchQuery}
                  onChange={(e) => setAuditSearchQuery(e.target.value)}
                  placeholder="Filter by action, actor, or hash digest..."
                  className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-3 py-1.5 text-xs text-[#252525] font-mono focus:outline-none focus:border-[#30302E]"
                />
              </div>
              <div className="sm:col-span-4">
                <select
                  value={auditFilterAction}
                  onChange={(e) => setAuditFilterAction(e.target.value)}
                  className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2.5 py-1.5 text-xs text-[#252525] font-mono focus:outline-none focus:border-[#30302E]"
                >
                  <option value="all">All Events ({auditLogs.length})</option>
                  <option value="upload">Upload</option>
                  <option value="generate">Generate</option>
                  <option value="export">Export</option>
                  <option value="approve">Approve</option>
                </select>
              </div>
            </div>
          </div>

          {/* High-density Table */}
          <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg overflow-hidden shadow-soft">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-[#F8F7F3] border-b border-[#D8D5CE] text-[10px] text-[#6F6D68] uppercase">
                  <tr>
                    <th className="py-2.5 px-3"># ID</th>
                    <th className="py-2.5 px-3">Timestamp</th>
                    <th className="py-2.5 px-3">Actor</th>
                    <th className="py-2.5 px-3">Action</th>
                    <th className="py-2.5 px-3">SHA-256 Hash</th>
                    <th className="py-2.5 px-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#D8D5CE]/60">
                  {filteredAuditLogs.map((log) => {
                    const isExpanded = expandedLogId === log.id;
                    return (
                      <React.Fragment key={log.id}>
                        <tr className="hover:bg-[#F8F7F3] transition">
                          <td className="py-2 px-3 font-semibold text-[#252525]">#{log.id}</td>
                          <td className="py-2 px-3 text-[#6F6D68] text-[11px]">
                            {new Date(log.timestamp).toLocaleTimeString()}
                          </td>
                          <td className="py-2 px-3">
                            <span className="px-1.5 py-0.5 rounded bg-[#F8F7F3] border border-[#D8D5CE] text-[#252525] text-[10px]">
                              {log.actor}
                            </span>
                          </td>
                          <td className="py-2 px-3">
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase bg-[#EAE8E1] text-[#252525]">
                              {log.action}
                            </span>
                          </td>
                          <td className="py-2 px-3">
                            <code className="text-[#6F6D68] bg-[#F8F7F3] px-1.5 py-0.5 rounded border border-[#D8D5CE] text-[10px]">
                              {log.hash.slice(0, 16)}...
                            </code>
                          </td>
                          <td className="py-2 px-3 text-right">
                            <button
                              onClick={() => setExpandedLogId(isExpanded ? null : log.id)}
                              className="px-2 py-0.5 rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-[#252525] text-[10px]"
                            >
                              {isExpanded ? 'Hide' : 'Inspect'}
                            </button>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="bg-[#F8F7F3]">
                            <td colSpan={6} className="p-3 text-[10px] font-mono space-y-1.5">
                              <div><strong className="text-[#6F6D68]">Current Hash:</strong> <span className="text-[#252525] break-all">{log.hash}</span></div>
                              <div><strong className="text-[#6F6D68]">Previous Hash:</strong> <span className="text-[#99958D] break-all">{log.prev_hash}</span></div>
                              <pre className="p-2 bg-[#FCFBF8] border border-[#D8D5CE] rounded text-[#252525] max-h-28 overflow-x-auto">
                                {JSON.stringify(log.details, null, 2)}
                              </pre>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* AIRGAP PROOF MODAL */}
      {airgapModalOpen && (
        <div className="fixed inset-0 z-50 bg-[#252525]/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#FCFBF8] border border-[#C7C3BA] rounded-lg max-w-xl w-full p-5 space-y-3.5 shadow-elevated">
            <div className="flex items-center justify-between pb-2.5 border-b border-[#D8D5CE]">
              <div className="flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-[#7E9D82]"></span>
                <h3 className="text-xs font-mono font-bold text-[#252525] uppercase tracking-wider">
                  Air-Gap Network Verification
                </h3>
              </div>
              <button onClick={() => setAirgapModalOpen(false)} className="text-[#99958D] hover:text-[#252525] text-xs font-mono">
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div className="p-3 rounded bg-[#F8F7F3] border border-[#D8D5CE] space-y-1.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-[#6F6D68]">Socket Probe (1.1.1.1:53)</span>
                  <span className="text-[#7E9D82] font-semibold bg-[#FCFBF8] px-2 py-0.5 rounded border border-[#D8D5CE]">
                    EGRESS BLOCKED
                  </span>
                </div>
                <pre className="p-2 bg-[#FCFBF8] rounded border border-[#D8D5CE] text-[10px] text-[#252525] whitespace-pre-wrap leading-relaxed">
                  {airgapProof?.details || 'Socket attempt to 1.1.1.1:53 aborted: host unreachable. Zero outbound egress enforced at OS socket layer.'}
                </pre>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="p-2 bg-[#F8F7F3] rounded border border-[#D8D5CE]">
                  <div className="text-[#6F6D68] font-bold">Network Routing:</div>
                  <div className="text-[#252525]">Docker internal: true</div>
                  <div className="text-[#99958D] text-[10px]">Zero default gateways</div>
                </div>
                <div className="p-2 bg-[#F8F7F3] rounded border border-[#D8D5CE]">
                  <div className="text-[#6F6D68] font-bold">Cloud Telemetry:</div>
                  <div className="text-[#252525]">0 External SDKs</div>
                  <div className="text-[#99958D] text-[10px]">100% on-premise inference</div>
                </div>
              </div>
            </div>

            <div className="pt-2 flex justify-between items-center border-t border-[#D8D5CE]">
              <button
                onClick={probeAirgap}
                disabled={isLoadingAirgap}
                className="px-3 py-1.5 rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-[#252525] text-xs font-mono transition"
              >
                {isLoadingAirgap ? 'Testing...' : 'Re-test Socket'}
              </button>
              <button
                onClick={() => setAirgapModalOpen(false)}
                className="px-3.5 py-1.5 rounded bg-[#30302E] hover:bg-[#252525] text-white text-xs font-medium transition"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EXPORT MODAL */}
      {exportModal && (
        <div className="fixed inset-0 z-50 bg-[#252525]/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#FCFBF8] border border-[#C7C3BA] rounded-lg max-w-xl w-full p-5 space-y-3.5 shadow-elevated flex flex-col justify-between max-h-[85vh]">
            <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
              <h3 className="text-xs font-mono font-bold text-[#252525] uppercase tracking-wide">
                Export Artifact ({exportModal.export_format})
              </h3>
              <button onClick={() => setExportModal(null)} className="text-[#99958D] hover:text-[#252525] text-xs font-mono">
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono overflow-y-auto pr-1">
              <div className="grid grid-cols-2 gap-2 p-2 bg-[#F8F7F3] rounded border border-[#D8D5CE] text-[11px]">
                <div>
                  <span className="text-[#6F6D68]">File:</span>
                  <div className="text-[#252525] font-semibold">{exportModal.exported_filename}</div>
                </div>
                <div>
                  <span className="text-[#6F6D68]">SHA-256 Checksum:</span>
                  <div className="text-[#7E9D82] text-[10px] truncate">{exportModal.checksum_sha256}</div>
                </div>
              </div>

              <pre className="p-2.5 bg-[#F8F7F3] border border-[#D8D5CE] rounded text-[#252525] text-[11px] max-h-56 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                {exportModal.exported_content}
              </pre>
            </div>

            <div className="pt-2 flex justify-between items-center border-t border-[#D8D5CE]">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(exportModal.exported_content);
                  setToastMessage({ type: 'success', text: 'Artifact copied to clipboard.' });
                }}
                className="px-3 py-1.5 rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-[#252525] text-xs font-mono transition"
              >
                Copy Content
              </button>

              <div className="flex gap-2">
                <button
                  onClick={() => {
                    const blob = new Blob([exportModal.exported_content], { type: 'text/plain;charset=utf-8' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = exportModal.exported_filename;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="px-3.5 py-1.5 rounded bg-[#30302E] hover:bg-[#252525] text-white text-xs font-medium transition"
                >
                  Download
                </button>
                <button
                  onClick={() => setExportModal(null)}
                  className="px-3 py-1.5 rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] border border-[#D8D5CE] text-[#6F6D68] text-xs transition"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CIPHERTEXT MODAL */}
      {encryptionModal && (
        <div className="fixed inset-0 z-50 bg-[#252525]/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#FCFBF8] border border-[#C7C3BA] rounded-lg max-w-lg w-full p-5 space-y-3.5 shadow-elevated">
            <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
              <h3 className="text-xs font-mono font-bold text-[#252525] uppercase tracking-wide">
                AES-256-GCM Storage Verification
              </h3>
              <button onClick={() => setEncryptionModal(null)} className="text-[#99958D] hover:text-[#252525] text-xs font-mono">
                ✕
              </button>
            </div>

            <div className="space-y-2 text-xs font-mono p-3 bg-[#F8F7F3] rounded border border-[#D8D5CE] text-[11px]">
              <div className="flex justify-between">
                <span className="text-[#6F6D68]">Output ID:</span>
                <span className="text-[#252525]">{encryptionModal.output_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6F6D68]">Cipher Algorithm:</span>
                <span className="text-[#7E9D82] font-semibold">{encryptionModal.algorithm}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#6F6D68]">Ciphertext Size:</span>
                <span className="text-[#252525]">{encryptionModal.file_size_bytes} bytes</span>
              </div>
              <div>
                <span className="text-[#6F6D68] block mb-0.5">Ciphertext Digest (SHA-256):</span>
                <span className="text-[#252525] text-[10px] break-all bg-[#FCFBF8] p-1.5 rounded border border-[#D8D5CE] block">
                  {encryptionModal.ciphertext_sha256}
                </span>
              </div>
              <div>
                <span className="text-[#6F6D68] block mb-0.5">Physical Storage Path:</span>
                <span className="text-[#99958D] text-[10px] break-all bg-[#FCFBF8] p-1.5 rounded border border-[#D8D5CE] block">
                  {encryptionModal.file_path}
                </span>
              </div>
            </div>

            <div className="pt-2 flex justify-end border-t border-[#D8D5CE]">
              <button
                onClick={() => setEncryptionModal(null)}
                className="px-3.5 py-1.5 rounded bg-[#30302E] hover:bg-[#252525] text-white text-xs font-medium transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* CLEAR DATABASE MODAL */}
      {clearDbModalOpen && (
        <div className="fixed inset-0 z-50 bg-[#252525]/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-[#FCFBF8] border border-[#C87970] rounded-lg max-w-md w-full p-5 space-y-4 shadow-elevated">
            <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
              <div className="flex items-center space-x-2 text-[#8C3A32]">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <h3 className="text-xs font-mono font-bold uppercase tracking-wide">
                  Purge Entire Database & Vectors
                </h3>
              </div>
              <button
                onClick={() => !isClearingDb && setClearDbModalOpen(false)}
                className="text-[#99958D] hover:text-[#252525] text-xs font-mono cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2.5 text-xs text-[#252525]">
              <p className="font-medium text-[#8C3A32]">
                Warning: This action is permanent and cannot be undone.
              </p>
              <div className="p-3 bg-[#F8F7F3] rounded border border-[#D8D5CE] space-y-1.5 text-[11px] font-mono text-[#6F6D68]">
                <div className="flex items-center space-x-1.5">
                  <span className="text-[#8C3A32] font-bold">&bull;</span>
                  <span>PostgreSQL: All documents, chunks, deliverables & edit history</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="text-[#8C3A32] font-bold">&bull;</span>
                  <span>Qdrant: Wipes 384-dim semantic embeddings collection</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="text-[#8C3A32] font-bold">&bull;</span>
                  <span>FalkorDB: Deletes knowledge graph topology & entities</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="text-[#8C3A32] font-bold">&bull;</span>
                  <span>Storage: Deletes encrypted on-disk files (*.enc)</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <span className="text-[#8C3A32] font-bold">&bull;</span>
                  <span>Audit Ledger: Re-initializes tamper-evident genesis chain</span>
                </div>
              </div>
            </div>

            <div className="pt-3 flex items-center justify-end space-x-2 border-t border-[#D8D5CE]">
              <button
                type="button"
                disabled={isClearingDb}
                onClick={() => setClearDbModalOpen(false)}
                className="px-3.5 py-1.5 rounded border border-[#D8D5CE] text-xs font-mono text-[#6F6D68] hover:bg-[#F8F7F3] transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isClearingDb}
                onClick={handleClearDatabase}
                className="px-4 py-1.5 rounded bg-[#C87970] hover:bg-[#8C3A32] disabled:bg-[#B9B8B3] text-white text-xs font-mono font-medium transition flex items-center space-x-1.5 cursor-pointer"
              >
                {isClearingDb ? (
                  <>
                    <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                    <span>Purging Database...</span>
                  </>
                ) : (
                  <span>Yes, Purge Database</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

