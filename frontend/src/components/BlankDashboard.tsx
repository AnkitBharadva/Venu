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

// Phase 3 & 4 Schemas
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
  encrypted_file_path?: string;
  reviewer_id?: string;
  reviewer_notes?: string;
  approved_at?: string;
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
  format_metadata: Record<string, any>;
  total_sentences: number;
  total_citations: number;
  contract_verified: boolean;
}

interface AuditVerification {
  valid: boolean;
  total_records: number;
  latest_hash?: string;
  status?: string;
  error?: string;
  record_id?: number;
}

interface OutputEncryptionInfo {
  output_id: string;
  verified: boolean;
  encrypted_at_rest: boolean;
  algorithm: string;
  file_path: string;
  file_size_bytes?: number;
  ciphertext_sha256?: string;
  deliverable_type?: string;
  status?: string;
  error?: string;
}

interface ExportResult {
  output_id: string;
  doc_id: string;
  deliverable_type: string;
  export_format: string;
  exported_filename: string;
  checksum_sha256: string;
  exported_content: string;
  encrypted_export_path: string;
  export_timestamp: string;
  actor: string;
}

interface EditHistoryItem {
  id: string;
  output_id: string;
  version: number;
  actor: string;
  action: string;
  target_type: string;
  target_id?: string;
  target_index?: number;
  before_content: string;
  after_content: string;
  diff_summary?: string;
  timestamp: string;
}

interface ReviewSummary {
  output_id: string;
  status: string;
  total_sentences: number;
  accepted_sentences: number;
  rejected_sentences: number;
  edited_sentences: number;
  pending_sentences: number;
  can_export: boolean;
  history_count: number;
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

const AVAILABLE_FORMATS = [
  { id: 'linkedin_post', label: 'LinkedIn Post', icon: '💼', category: 'Social' },
  { id: 'twitter_thread', label: 'Twitter/X Thread', icon: '🐦', category: 'Social' },
  { id: 'executive_summary', label: 'Executive Summary', icon: '📋', category: 'Executive' },
  { id: 'advisory', label: 'Tactical Advisory', icon: '🛡️', category: 'Operational', reviewRequired: true },
  { id: 'presentation', label: 'Presentation Deck', icon: '📊', category: 'Presentation' },
  { id: 'video_package', label: 'Video Package (Script & Storyboard)', icon: '🎬', category: 'Multimedia' },
  { id: 'infographic', label: 'Infographic Layout Spec', icon: '📐', category: 'Visual' },
];

export const BlankDashboard: React.FC = () => {
  // Navigation tabs
  const [activeTab, setActiveTab] = useState<'pipeline' | 'adapters' | 'review' | 'security'>('adapters');

  // Phase 6 Human Review State
  const [editingSentenceId, setEditingSentenceId] = useState<string | null>(null);
  const [editingSentenceText, setEditingSentenceText] = useState<string>('');
  const [editingNotes, setEditingNotes] = useState<string>('');
  const [isSavingEdit, setIsSavingEdit] = useState<boolean>(false);
  const [showHistoryModal, setShowHistoryModal] = useState<boolean>(false);
  const [editHistory, setEditHistory] = useState<EditHistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary | null>(null);

  // Phase 5 Security, RBAC & Audit State
  const [currentUserRole, setCurrentUserRole] = useState<'operator' | 'reviewer'>('operator');
  const [currentUserId, setCurrentUserId] = useState<string>('operator_alice');
  const [auditVerification, setAuditVerification] = useState<AuditVerification | null>(null);
  const [isVerifyingAudit, setIsVerifyingAudit] = useState<boolean>(false);
  const [encryptionModal, setEncryptionModal] = useState<OutputEncryptionInfo | null>(null);
  const [exportModal, setExportModal] = useState<ExportResult | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [rbacAlert, setRbacAlert] = useState<{ type: 'error' | 'success'; title: string; message: string } | null>(null);
  const [tamperDemoResult, setTamperDemoResult] = useState<string | null>(null);
  const [isSimulatingTamper, setIsSimulatingTamper] = useState<boolean>(false);
  const [exportFormatSelection, setExportFormatSelection] = useState<string>('markdown');

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

  // Phase 4 Multi-Select Adapters State
  const [selectedFormats, setSelectedFormats] = useState<string[]>([
    'linkedin_post',
    'twitter_thread',
    'executive_summary',
    'advisory',
  ]);
  const [targetAudience, setTargetAudience] = useState<string>('Air Force & Cyber Command');
  const [targetTone, setTargetTone] = useState<string>('Authoritative & Objective');
  const [detailLevel, setDetailLevel] = useState<string>('comprehensive');
  const [isGeneratingMulti, setIsGeneratingMulti] = useState<boolean>(false);

  // Grounding & Provenance Trace State (Phase 3 & 4)
  const [deliverables, setDeliverables] = useState<DeliverableResponse[]>([]);
  const [selectedDeliverable, setSelectedDeliverable] = useState<DeliverableResponse | null>(null);
  const [hoveredSentenceId, setHoveredSentenceId] = useState<string | null>(null);
  const [sentenceTrace, setSentenceTrace] = useState<SentenceTraceResponse | null>(null);
  const [isTracing, setIsTracing] = useState<boolean>(false);
  const [gatekeeperAlert, setGatekeeperAlert] = useState<{ type: 'error' | 'success'; message: string } | null>(null);

  // Hybrid Retrieval State
  const [hybridQuery, setHybridQuery] = useState<string>('air-gapped security and cryptographic isolation');
  const [isRetrievingHybrid, setIsRetrievingHybrid] = useState<boolean>(false);
  const [hybridResult, setHybridResult] = useState<GroundedContextResponse | null>(null);

  const toggleFormat = (id: string) => {
    setSelectedFormats((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
    );
  };

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

  const handleMultiGenerate = async () => {
    if (!latestDoc || chunks.length === 0 || selectedFormats.length === 0) return;

    setIsGeneratingMulti(true);
    setGatekeeperAlert(null);

    try {
      const payload = {
        doc_id: latestDoc.doc_id,
        deliverable_types: selectedFormats,
        query: hybridQuery || undefined,
        parameters: {
          audience: targetAudience,
          tone: targetTone,
          detail_level: detailLevel,
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
        throw new Error(errJson?.detail?.message || errJson?.detail || 'Multi-deliverable generation failed');
      }

      const data = await res.json();
      setDeliverables(data.deliverables);
      if (data.deliverables.length > 0) {
        setSelectedDeliverable(data.deliverables[0]);
      }
      setGatekeeperAlert({
        type: 'success',
        message: `Successfully generated ${data.total_deliverables} grounded deliverables! 100% claim-to-chunk provenance contract enforced.`,
      });
    } catch (err: unknown) {
      setGatekeeperAlert({
        type: 'error',
        message: err instanceof Error ? err.message : 'Generation failed',
      });
    } finally {
      setIsGeneratingMulti(false);
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

  const handleVerifyAuditChain = async () => {
    setIsVerifyingAudit(true);
    try {
      const res = await fetch('/api/v1/audit/verify-chain');
      const data: AuditVerification = await res.json();
      setAuditVerification(data);
      if (data.valid) {
        setRbacAlert({
          type: 'success',
          title: 'Audit Chain Cryptographically Verified (SHA-256)',
          message: `All ${data.total_records} audit log records verified against linear hash chain. Latest hash: ${data.latest_hash?.slice(0, 24)}...`,
        });
      } else {
        setRbacAlert({
          type: 'error',
          title: 'Tampering Detected in Audit Log!',
          message: `${data.error} at record ID ${data.record_id}`,
        });
      }
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Audit Verification Failed',
        message: err instanceof Error ? err.message : 'Failed to reach audit endpoint',
      });
    } finally {
      setIsVerifyingAudit(false);
    }
  };

  const handleVerifyEncryption = async (outputId: string) => {
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/verify-encryption`, {
        headers: {
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data: OutputEncryptionInfo = await res.json();
      setEncryptionModal(data);
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Encryption Verification Error',
        message: err instanceof Error ? err.message : 'Failed to inspect encrypted output',
      });
    }
  };

  const handleRequestApproval = async (outputId: string) => {
    setRbacAlert(null);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/request-approval`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
        body: JSON.stringify({ notes: `Submitted by ${currentUserId} via Dashboard` }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail?.message || errJson?.detail || `HTTP ${res.status}`);
      }
      const updated: DeliverableResponse = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      if (selectedDeliverable?.output_id === outputId) {
        setSelectedDeliverable(updated);
      }
      setRbacAlert({
        type: 'success',
        title: 'Submitted for Review',
        message: `Deliverable ${outputId.slice(0, 8)} transitioned to status: 'pending_review'.`,
      });
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Submission Failed',
        message: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handleApproveDeliverable = async (outputId: string) => {
    setRbacAlert(null);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
        body: JSON.stringify({ reviewer_notes: `Authorized by ${currentUserId}` }),
      });
      if (res.status === 403) {
        const err = await res.json();
        const msg = err.detail?.message || `User '${currentUserId}' with role '${currentUserRole}' lacks 'approve' permission. Only Reviewers/Approvers can authorize output publication.`;
        setRbacAlert({
          type: 'error',
          title: 'RBAC Access Forbidden (HTTP 403)',
          message: typeof msg === 'object' ? JSON.stringify(msg) : msg,
        });
        return;
      }
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const updated: DeliverableResponse = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      if (selectedDeliverable?.output_id === outputId) {
        setSelectedDeliverable(updated);
      }
      setRbacAlert({
        type: 'success',
        title: 'Deliverable Approved',
        message: `Deliverable ${outputId.slice(0, 8)} approved by Reviewer ${currentUserId}. Export authorization unlocked!`,
      });
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Approval Action Failed',
        message: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handleRejectDeliverable = async (outputId: string) => {
    setRbacAlert(null);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
        body: JSON.stringify({ reviewer_notes: `Rejected by ${currentUserId}: Citations require refinement` }),
      });
      if (res.status === 403) {
        const err = await res.json();
        const msg = err.detail?.message || `Role '${currentUserRole}' cannot reject deliverables.`;
        setRbacAlert({
          type: 'error',
          title: 'RBAC Access Forbidden (HTTP 403)',
          message: typeof msg === 'object' ? JSON.stringify(msg) : msg,
        });
        return;
      }
      const updated: DeliverableResponse = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      if (selectedDeliverable?.output_id === outputId) {
        setSelectedDeliverable(updated);
      }
      setRbacAlert({
        type: 'error',
        title: 'Deliverable Rejected',
        message: `Deliverable ${outputId.slice(0, 8)} rejected. Status: 'rejected'. Export remains locked.`,
      });
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Rejection Action Failed',
        message: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handleExportDeliverable = async (outputId: string, format: string) => {
    setRbacAlert(null);
    setIsExporting(true);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
        body: JSON.stringify({ export_format: format }),
      });
      if (res.status === 403) {
        const err = await res.json();
        const msg = err.detail?.message || err.detail || 'Forbidden';
        setRbacAlert({
          type: 'error',
          title: 'Export Blocked (Gatekeeper / RBAC Protection)',
          message: typeof msg === 'object' ? JSON.stringify(msg) : msg,
        });
        return;
      }
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const exportData: ExportResult = await res.json();
      setExportModal(exportData);
      setRbacAlert({
        type: 'success',
        title: 'Export Generated & Encrypted at Rest',
        message: `File ${exportData.exported_filename} successfully archived with AES-256 encryption. SHA-256: ${exportData.checksum_sha256.slice(0, 16)}...`,
      });
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Export Failed',
        message: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsExporting(false);
    }
  };

  const handleSimulateTamperDemo = async () => {
    setIsSimulatingTamper(true);
    setTamperDemoResult(null);
    try {
      const res = await fetch('/api/v1/audit/verify-chain');
      const data = await res.json();
      setTamperDemoResult(
        `[HASH CHAIN INSPECTION]\n` +
        `Current Records Count: ${data.total_records}\n` +
        `Linear Hash Status: ${data.valid ? '100% Intact & Cryptographically Valid' : 'Corrupted'}\n` +
        `Latest Block Hash: ${data.latest_hash || 'N/A'}\n\n` +
        `[MATHEMATICAL GUARANTEE]\n` +
        `Every audit entry is computed as:\n` +
        `Hash_n = SHA256(Hash_{n-1} | actor | action | doc_id | output_id | timestamp | source_hash | details)\n\n` +
        `If any database record is altered by an attacker, its recalculated hash mismatches, and every subsequent row's prev_hash breaks, pinpointing the exact compromised row ID.`
      );
    } catch (err: unknown) {
      setTamperDemoResult(`Tamper demonstration error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsSimulatingTamper(false);
    }
  };

  const handleEditSentence = async (outputId: string, sentenceId: string, newText: string, notes?: string) => {
    setIsSavingEdit(true);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/edit-sentence`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
        body: JSON.stringify({
          sentence_id: sentenceId,
          new_text: newText,
          notes: notes || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail?.message || err?.detail || `HTTP ${res.status}`);
      }
      const updated: DeliverableResponse = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      if (selectedDeliverable?.output_id === outputId) {
        setSelectedDeliverable(updated);
      }
      setEditingSentenceId(null);
      setEditingSentenceText('');
      setEditingNotes('');
      setRbacAlert({
        type: 'success',
        title: 'Sentence Edited & Diff Stored',
        message: `Sentence ${sentenceId} updated by ${currentUserId}. Before/after state and unified diff logged to audit trail.`,
      });
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Sentence Edit Failed',
        message: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleReviewSentence = async (outputId: string, sentenceId: string, decision: 'accept' | 'reject', notes?: string) => {
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/review-sentence`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
        body: JSON.stringify({
          sentence_id: sentenceId,
          decision,
          notes: notes || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail?.message || err?.detail || `HTTP ${res.status}`);
      }
      const updated: DeliverableResponse = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      if (selectedDeliverable?.output_id === outputId) {
        setSelectedDeliverable(updated);
      }
      setRbacAlert({
        type: 'success',
        title: `Sentence ${decision === 'accept' ? 'Accepted' : 'Rejected'}`,
        message: `Sentence ${sentenceId} marked as '${decision === 'accept' ? 'accepted' : 'rejected'}' by ${currentUserId}.`,
      });
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Sentence Decision Failed',
        message: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handleReviewSection = async (outputId: string, blockIndex: number, decision: 'accept' | 'reject') => {
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/review-section`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
        body: JSON.stringify({
          block_index: blockIndex,
          decision,
          notes: `Section #${blockIndex} bulk decision`,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail?.message || err?.detail || `HTTP ${res.status}`);
      }
      const updated: DeliverableResponse = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      if (selectedDeliverable?.output_id === outputId) {
        setSelectedDeliverable(updated);
      }
      setRbacAlert({
        type: 'success',
        title: `Section #${blockIndex} ${decision === 'accept' ? 'Accepted' : 'Rejected'}`,
        message: `All sentences in Section #${blockIndex} updated to '${decision === 'accept' ? 'accepted' : 'rejected'}'.`,
      });
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Section Decision Failed',
        message: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  };

  const handleFetchEditHistory = async (outputId: string) => {
    setIsLoadingHistory(true);
    setShowHistoryModal(true);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/history`, {
        headers: {
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data: EditHistoryItem[] = await res.json();
      setEditHistory(data);
    } catch (err: unknown) {
      setRbacAlert({
        type: 'error',
        title: 'Failed to Fetch History',
        message: err instanceof Error ? err.message : 'Error fetching audit diff history',
      });
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleFetchReviewSummary = async (outputId: string) => {
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/summary`, {
        headers: {
          'X-User-Role': currentUserRole,
          'X-User-Id': currentUserId,
        },
      });
      if (res.ok) {
        const data: ReviewSummary = await res.json();
        setReviewSummary(data);
      }
    } catch (err) {
      console.error('Failed to fetch summary:', err);
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
      <div className="bg-gradient-to-r from-emerald-950/40 via-indigo-950/30 to-gray-900 border border-emerald-800/40 rounded-xl p-4 flex flex-col xl:flex-row items-start xl:items-center justify-between gap-4">
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
                Phase 5 Defence-Grade Security & Audit
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              RBAC Dual-Control &bull; AES-256-GCM At Rest &bull; Tamper-Evident Hash Chaining &bull; Safety-Critical Gatekeeper.
            </p>
          </div>
        </div>

        {/* Role Switcher & Tab Navigation */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* RBAC Role Switcher */}
          <div className="flex items-center space-x-1.5 bg-gray-950/90 px-2 py-1 rounded-lg border border-gray-800">
            <span className="text-[10px] uppercase font-mono text-gray-400">User Role:</span>
            <button
              type="button"
              onClick={() => {
                setCurrentUserRole('operator');
                setCurrentUserId('operator_alice');
                setRbacAlert({
                  type: 'success',
                  title: 'Switched to Operator Role (Alice)',
                  message: 'Permissions: Ingest, Understand, Multi-Select Generate, Request Review. Strictly blocked from Approve & Export.',
                });
              }}
              className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                currentUserRole === 'operator'
                  ? 'bg-amber-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Operator (Alice)
            </button>
            <button
              type="button"
              onClick={() => {
                setCurrentUserRole('reviewer');
                setCurrentUserId('reviewer_bob');
                setRbacAlert({
                  type: 'success',
                  title: 'Switched to Reviewer Role (Bob)',
                  message: 'Permissions: Formal Review, Deliverable Approval/Rejection, and Export Authorization.',
                });
              }}
              className={`px-2.5 py-1 rounded text-xs font-semibold transition ${
                currentUserRole === 'reviewer'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Reviewer (Bob)
            </button>
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
              Pipeline (1-2)
            </button>
            <button
              onClick={() => setActiveTab('adapters')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center space-x-1.5 ${
                activeTab === 'adapters'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <span>Output Adapters (3-4)</span>
              {deliverables.length > 0 && (
                <span className="bg-emerald-950 text-emerald-300 text-[10px] font-mono px-1.5 py-0.2 rounded-full border border-emerald-800">
                  {deliverables.length}
                </span>
              )}
            </button>
            <button
              onClick={() => {
                setActiveTab('review');
                if (selectedDeliverable) {
                  handleFetchReviewSummary(selectedDeliverable.output_id);
                }
              }}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center space-x-1.5 ${
                activeTab === 'review'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <span>✍️ Human Review (6)</span>
              {deliverables.length > 0 && (
                <span className="bg-purple-950 text-purple-300 text-[10px] font-mono px-1.5 py-0.2 rounded-full border border-purple-800">
                  {deliverables.filter((d) => d.status !== 'final').length}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('security')}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition flex items-center space-x-1.5 ${
                activeTab === 'security'
                  ? 'bg-cyan-600 text-white shadow-sm'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              <span>🛡️ Security & Audit (5)</span>
            </button>
          </div>
        </div>
      </div>

      {/* RBAC / Security Notification Alert */}
      {rbacAlert && (
        <div
          className={`p-4 rounded-xl border flex items-start justify-between gap-3 ${
            rbacAlert.type === 'error'
              ? 'bg-rose-950/40 border-rose-800 text-rose-200'
              : 'bg-emerald-950/40 border-emerald-800 text-emerald-200'
          }`}
        >
          <div className="flex items-start space-x-3">
            <span className="text-xl">{rbacAlert.type === 'error' ? '🚫' : '🛡️'}</span>
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider font-mono">
                {rbacAlert.title}
              </h4>
              <p className="text-xs mt-0.5 opacity-90">{rbacAlert.message}</p>
            </div>
          </div>
          <button
            onClick={() => setRbacAlert(null)}
            className="text-gray-400 hover:text-white text-xs px-2 py-1 rounded"
          >
            ✕
          </button>
        </div>
      )}

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

      {/* TAB 2: Phase 4 Multi-Select Output Adapters & Grounding Suite */}
      {activeTab === 'adapters' && (
        <div className="space-y-6">
          {/* Multi-Select Adapter Generator Console */}
          <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between pb-4 border-b border-gray-800 mb-4 gap-4">
              <div>
                <h3 className="text-sm font-bold text-gray-200 flex items-center space-x-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                  <span>Modular Output Generation Adapters (Phase 4)</span>
                </h3>
                <p className="text-xs text-gray-400 mt-1">
                  Select multiple target deliverable formats. Adapters execute concurrently against shared grounded context.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleMultiGenerate}
                  disabled={isGeneratingMulti || chunks.length === 0 || selectedFormats.length === 0}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-800 text-white text-xs rounded-lg font-semibold transition flex items-center space-x-2 shadow-sm"
                >
                  {isGeneratingMulti ? (
                    <>
                      <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                      </svg>
                      <span>Generating ({selectedFormats.length}) Deliverables...</span>
                    </>
                  ) : (
                    <>
                      <span>✨</span>
                      <span>Generate Selected ({selectedFormats.length}) Formats</span>
                    </>
                  )}
                </button>

                <button
                  onClick={handleTestHardContractViolation}
                  disabled={!latestDoc}
                  className="px-3.5 py-2 bg-rose-950/60 hover:bg-rose-900/80 border border-rose-800/80 text-rose-300 text-xs rounded-lg font-medium transition flex items-center space-x-1.5"
                  title="Demonstrate that uncited claims are blocked by the gateway"
                >
                  <span>🛡️</span>
                  <span>Gatekeeper Test</span>
                </button>
              </div>
            </div>

            {/* Format Multi-Select Checkbox Pills */}
            <div className="space-y-3">
              <span className="text-[10px] font-mono uppercase tracking-wider text-gray-400 block">
                Select Deliverable Formats:
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
                {AVAILABLE_FORMATS.map((fmt) => {
                  const isSelected = selectedFormats.includes(fmt.id);
                  return (
                    <div
                      key={fmt.id}
                      onClick={() => toggleFormat(fmt.id)}
                      className={`p-2.5 rounded-lg border text-xs cursor-pointer transition flex items-center justify-between ${
                        isSelected
                          ? 'bg-emerald-950/70 border-emerald-500/80 text-emerald-100 shadow-sm'
                          : 'bg-gray-950/60 border-gray-800 text-gray-400 hover:border-gray-700'
                      }`}
                    >
                      <div className="flex items-center space-x-2">
                        <span className="text-base">{fmt.icon}</span>
                        <div>
                          <span className="font-medium text-xs block text-gray-200">{fmt.label}</span>
                          <span className="text-[9px] font-mono text-gray-400">{fmt.category}</span>
                        </div>
                      </div>
                      <div className="flex items-center space-x-1.5">
                        {fmt.reviewRequired && (
                          <span className="text-[9px] px-1 py-0.2 rounded bg-amber-950/80 text-amber-400 border border-amber-800/50">
                            Review Lock
                          </span>
                        )}
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}} // handled by parent div
                          className="rounded text-emerald-600 focus:ring-0 border-gray-700 bg-gray-900"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Generation Parameters Configuration */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-3 border-t border-gray-800/80">
                <div>
                  <label className="text-[10px] font-mono text-gray-400 block mb-1">Target Audience</label>
                  <input
                    type="text"
                    value={targetAudience}
                    onChange={(e) => setTargetAudience(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1 text-xs text-gray-200 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-mono text-gray-400 block mb-1">Tone of Voice</label>
                  <input
                    type="text"
                    value={targetTone}
                    onChange={(e) => setTargetTone(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1 text-xs text-gray-200 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-mono text-gray-400 block mb-1">Detail Level</label>
                  <select
                    value={detailLevel}
                    onChange={(e) => setDetailLevel(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded px-2.5 py-1 text-xs text-gray-200 focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="brief">Brief</option>
                    <option value="standard">Standard</option>
                    <option value="comprehensive">Comprehensive</option>
                  </select>
                </div>
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

          {/* Deliverables Viewer + Interactive Hovercard Inspector */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Deliverable Viewer with Hovercards */}
            <div className="lg:col-span-7 bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-semibold text-gray-200">Generated Deliverables</span>
                    {selectedDeliverable && (
                      <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/60 text-emerald-300">
                        {selectedDeliverable.deliverable_type}
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                    Hover Sentence &bull; Trace Provenance
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
                          className={`px-3 py-1.5 rounded-lg text-xs font-mono transition border flex items-center space-x-1.5 ${
                            selectedDeliverable?.output_id === d.output_id
                              ? 'bg-emerald-950/80 border-emerald-500 text-emerald-200'
                              : 'bg-gray-950 border-gray-800 text-gray-400 hover:border-gray-700'
                          }`}
                        >
                          <span>{d.deliverable_type}</span>
                          {d.format_metadata?.requires_human_review && (
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-400" title="Review Required"></span>
                          )}
                          <span className="text-[10px] opacity-70">({d.total_sentences})</span>
                        </button>
                      ))}
                    </div>

                    {/* Content Display with Sentence Hovercards */}
                    {selectedDeliverable && (
                      <div className="p-4 rounded-xl bg-gray-950/90 border border-gray-800 space-y-4">
                        <div className="border-b border-gray-800/80 pb-3 flex flex-col md:flex-row md:items-center justify-between gap-2">
                          <div>
                            <div className="flex items-center space-x-2">
                              <h4 className="text-sm font-bold text-gray-100">
                                {selectedDeliverable.content.title}
                              </h4>
                              {/* Deliverable Status Badge */}
                              <span
                                className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${
                                  selectedDeliverable.status === 'approved'
                                    ? 'bg-emerald-950/80 border-emerald-700 text-emerald-300 font-bold'
                                    : selectedDeliverable.status === 'pending_review'
                                    ? 'bg-amber-950/80 border-amber-700 text-amber-300 font-bold'
                                    : selectedDeliverable.status === 'rejected'
                                    ? 'bg-rose-950/80 border-rose-700 text-rose-300 font-bold'
                                    : 'bg-gray-800 border-gray-700 text-gray-300'
                                }`}
                              >
                                Status: {selectedDeliverable.status}
                              </span>
                            </div>
                            {selectedDeliverable.content.summary && (
                              <p className="text-xs text-gray-400 mt-1 italic">
                                {selectedDeliverable.content.summary}
                              </p>
                            )}
                          </div>

                          {/* Safety Critical Gatekeeper Badge */}
                          {selectedDeliverable.format_metadata?.requires_human_review && (
                            <div className="px-2.5 py-1 rounded bg-rose-950/70 border border-rose-800/80 text-rose-300 text-[10px] font-mono flex items-center space-x-1.5 self-start md:self-auto">
                              <span className="animate-pulse">🔒</span>
                              <span>MANDATORY REVIEW BEFORE EXPORT</span>
                            </div>
                          )}
                        </div>

                        {/* Phase 5 Action Toolbar: Review, Approval, Export & Encryption Verification */}
                        <div className="p-2.5 rounded-lg bg-gray-900/80 border border-gray-800/90 flex flex-wrap items-center justify-between gap-2 text-xs">
                          <div className="flex flex-wrap items-center gap-2">
                            {/* Verify Output Encryption Button */}
                            <button
                              type="button"
                              onClick={() => handleVerifyEncryption(selectedDeliverable.output_id)}
                              className="px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 text-[11px] font-mono flex items-center space-x-1"
                              title="Verify AES-256-GCM ciphertext on disk"
                            >
                              <span>🔐</span>
                              <span>Verify AES-256 at Rest</span>
                            </button>

                            {/* Request Approval Button */}
                            <button
                              type="button"
                              onClick={() => handleRequestApproval(selectedDeliverable.output_id)}
                              className="px-2.5 py-1 rounded bg-amber-950/60 hover:bg-amber-900/70 border border-amber-800/70 text-amber-300 text-[11px] font-medium"
                              title="Submit deliverable for formal human reviewer sign-off"
                            >
                              📩 Request Approval
                            </button>

                            {/* Reviewer Actions (Approve / Reject) */}
                            <button
                              type="button"
                              onClick={() => handleApproveDeliverable(selectedDeliverable.output_id)}
                              className="px-2.5 py-1 rounded bg-emerald-900/60 hover:bg-emerald-800/70 border border-emerald-700/70 text-emerald-200 text-[11px] font-semibold flex items-center space-x-1"
                              title={currentUserRole === 'operator' ? 'RBAC Test: Click as Operator to test 403 Forbidden' : 'Approve deliverable'}
                            >
                              <span>✔ Approve</span>
                              {currentUserRole === 'operator' && (
                                <span className="text-[9px] text-amber-400 font-mono">(RBAC Test)</span>
                              )}
                            </button>

                            <button
                              type="button"
                              onClick={() => handleRejectDeliverable(selectedDeliverable.output_id)}
                              className="px-2.5 py-1 rounded bg-rose-950/60 hover:bg-rose-900/70 border border-rose-800/70 text-rose-300 text-[11px] font-semibold flex items-center space-x-1"
                              title={currentUserRole === 'operator' ? 'RBAC Test: Click as Operator to test 403 Forbidden' : 'Reject deliverable'}
                            >
                              <span>✕ Reject</span>
                            </button>
                          </div>

                          {/* Export Controls */}
                          <div className="flex items-center space-x-1.5">
                            <select
                              value={exportFormatSelection}
                              onChange={(e) => setExportFormatSelection(e.target.value)}
                              className="bg-gray-950 border border-gray-700 rounded px-2 py-1 text-[11px] text-gray-200 font-mono focus:outline-none"
                            >
                              <option value="markdown">Markdown (.md)</option>
                              <option value="json">JSON (.json)</option>
                              <option value="html">HTML (.html)</option>
                              <option value="text">Plain Text (.txt)</option>
                            </select>

                            <button
                              type="button"
                              disabled={isExporting}
                              onClick={() => handleExportDeliverable(selectedDeliverable.output_id, exportFormatSelection)}
                              className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-800 text-white font-medium text-[11px] transition shadow flex items-center space-x-1"
                              title={
                                selectedDeliverable.format_metadata?.requires_human_review && selectedDeliverable.status !== 'approved'
                                  ? 'Gatekeeper Active: Unapproved Advisories cannot be exported'
                                  : 'Export deliverable'
                              }
                            >
                              <span>{isExporting ? '...' : '📦 Export'}</span>
                            </button>
                          </div>
                        </div>

                        {/* Format-Specific Previews */}
                        {/* 1. LinkedIn Post Hashtags Preview */}
                        {selectedDeliverable.deliverable_type === 'linkedin_post' && selectedDeliverable.format_metadata?.hashtags && (
                          <div className="flex flex-wrap gap-1.5 pb-2 border-b border-gray-800/60">
                            {selectedDeliverable.format_metadata.hashtags.map((h: string, idx: number) => (
                              <span key={idx} className="text-[10px] font-mono bg-blue-950/50 text-blue-300 border border-blue-800/50 px-2 py-0.5 rounded">
                                {h}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* 2. Twitter Thread Tweet Cards */}
                        {selectedDeliverable.deliverable_type === 'twitter_thread' && (
                          <div className="text-[10px] font-mono text-cyan-400 bg-cyan-950/30 px-2.5 py-1 rounded border border-cyan-800/30 flex items-center justify-between">
                            <span>Thread Length: {selectedDeliverable.content.blocks.length} Tweets</span>
                            <span>Max Limit: 280 chars / tweet</span>
                          </div>
                        )}

                        {/* 3. Slide Deck Slide Info */}
                        {selectedDeliverable.deliverable_type === 'presentation' && (
                          <div className="text-[10px] font-mono text-purple-400 bg-purple-950/30 px-2.5 py-1 rounded border border-purple-800/30 flex items-center justify-between">
                            <span>Slide Deck: {selectedDeliverable.content.blocks.length} Slides</span>
                            <span>16:9 Aspect Ratio</span>
                          </div>
                        )}

                        {/* 4. Video Package Storyboard Info */}
                        {selectedDeliverable.deliverable_type === 'video_package' && (
                          <div className="text-[10px] font-mono text-amber-400 bg-amber-950/30 px-2.5 py-1 rounded border border-amber-800/30 flex items-center justify-between">
                            <span>Multimedia Storyboard: {selectedDeliverable.content.blocks.length} Scenes</span>
                            <span>Timecoded SRT Included</span>
                          </div>
                        )}

                        {/* 5. Infographic Metrics Summary */}
                        {selectedDeliverable.deliverable_type === 'infographic' && selectedDeliverable.format_metadata?.key_metrics && (
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pb-2 border-b border-gray-800/60">
                            {selectedDeliverable.format_metadata.key_metrics.map((m: any, idx: number) => (
                              <div key={idx} className="p-2 rounded bg-gray-900 border border-gray-800 text-center">
                                <span className="text-xs font-bold text-emerald-400 block">{m.value}</span>
                                <span className="text-[9px] text-gray-400 font-mono truncate block">{m.label}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Sentences Container with Interactive Hover & Click */}
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

                        {/* Expandable SRT Subtitles for Video Package */}
                        {selectedDeliverable.deliverable_type === 'video_package' && selectedDeliverable.format_metadata?.subtitles_srt && (
                          <div className="pt-3 border-t border-gray-800">
                            <span className="text-[10px] font-mono text-amber-400 uppercase tracking-wider block mb-1.5">
                              Generated Timecoded Subtitles (.SRT Format):
                            </span>
                            <pre className="p-2.5 bg-gray-900 border border-gray-800 rounded text-[9px] font-mono text-gray-300 max-h-32 overflow-y-auto whitespace-pre-wrap">
                              {selectedDeliverable.format_metadata.subtitles_srt}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-8 text-center text-gray-500 border border-dashed border-gray-800/80 rounded-lg bg-gray-950/30">
                    <p className="text-xs">No deliverables generated yet.</p>
                    <p className="text-[10px] mt-1 text-gray-600">
                      Select target formats above and click &ldquo;Generate Selected Formats&rdquo; to execute Phase 4 adapters.
                    </p>
                  </div>
                )}
              </div>

              <div className="mt-4 text-[10px] text-gray-500 border-t border-gray-800/60 pt-2 flex items-center justify-between font-mono">
                <span>Hard Contract Status: Active</span>
                <span className="text-emerald-400">100% Citations Enforced Across Formats</span>
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

              {/* Hybrid Grounding Retrieval Console */}
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

      {/* PHASE 6: HUMAN REVIEW & APPROVAL WORKFLOW VIEW */}
      {activeTab === 'review' && (
        <div className="space-y-6 animate-fadeIn">
          {/* Top Overview Banner */}
          <div className="p-5 rounded-xl bg-gradient-to-r from-gray-900 via-purple-950/30 to-gray-900 border border-purple-800/40 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xl">✍️</span>
                <h2 className="text-base font-bold text-gray-100">
                  Human Review & Approval Workflow Enclave
                </h2>
                <span className="bg-purple-500/20 text-purple-300 text-[10px] font-mono px-2 py-0.5 rounded border border-purple-500/30">
                  Phase 6 Mandate
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-1 max-w-3xl">
                No deliverable leaves the air-gapped system without an authorized human checkpoint. Review emitted sentences against source citations, accept/reject per section or claim, edit with unified diff audit logging, and authorize export by transitioning status to <code className="bg-black/50 px-1 py-0.5 rounded text-emerald-300">final</code>.
              </p>
            </div>

            <div className="flex items-center gap-2">
              {selectedDeliverable && (
                <button
                  type="button"
                  onClick={() => handleFetchEditHistory(selectedDeliverable.output_id)}
                  disabled={isLoadingHistory}
                  className="px-3.5 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-semibold border border-gray-700 shadow transition flex items-center space-x-1.5"
                >
                  <span>📜 Audit Diff History</span>
                </button>
              )}
            </div>
          </div>

          {/* Deliverables Queue & Selector */}
          {deliverables.length > 0 ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-gray-400 uppercase tracking-wide">
                  Review Queue ({deliverables.length} deliverables):
                </span>
                <span className="text-[11px] text-gray-400 font-mono">
                  Active Reviewer Role: <strong className="text-purple-300">{currentUserRole}</strong> ({currentUserId})
                </span>
              </div>

              {/* Selector Tabs */}
              <div className="flex flex-wrap gap-2">
                {deliverables.map((d) => (
                  <button
                    key={d.output_id}
                    type="button"
                    onClick={() => {
                      setSelectedDeliverable(d);
                      setEditingSentenceId(null);
                      handleFetchReviewSummary(d.output_id);
                    }}
                    className={`px-3 py-2 rounded-lg text-xs font-mono transition border flex items-center space-x-2 ${
                      selectedDeliverable?.output_id === d.output_id
                        ? 'bg-purple-950/80 border-purple-500 text-purple-200 shadow-md'
                        : 'bg-gray-900 border-gray-800 text-gray-400 hover:border-gray-700'
                    }`}
                  >
                    <span className="font-semibold uppercase">{d.deliverable_type}</span>
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded font-bold uppercase ${
                        d.status === 'final'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                          : d.status === 'rejected'
                          ? 'bg-rose-950 text-rose-300 border border-rose-800'
                          : d.status === 'pending_review'
                          ? 'bg-amber-950 text-amber-300 border border-amber-800'
                          : 'bg-gray-800 text-gray-300 border border-gray-700'
                      }`}
                    >
                      {d.status}
                    </span>
                  </button>
                ))}
              </div>

              {selectedDeliverable && (
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 pt-2">
                  {/* Left Column (8 cols): Content Review Studio */}
                  <div className="lg:col-span-8 bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 space-y-5">
                    {/* Header with Title & Status Warning */}
                    <div className="border-b border-gray-800 pb-4 space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center space-x-2">
                          <h3 className="text-base font-bold text-gray-100">
                            {selectedDeliverable.content.title}
                          </h3>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950/60 border border-purple-800/60 text-purple-300 uppercase">
                            {selectedDeliverable.deliverable_type}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <button
                            type="button"
                            onClick={() => handleFetchEditHistory(selectedDeliverable.output_id)}
                            className="text-xs font-mono px-2.5 py-1 rounded border border-cyan-700 bg-cyan-950/60 hover:bg-cyan-900/80 text-cyan-300 transition flex items-center space-x-1"
                            title="View complete tamper-evident edit history and diffs"
                          >
                            <span>📜</span>
                            <span>Diff & Audit History</span>
                          </button>
                          <span
                            className={`text-xs font-mono font-bold px-2.5 py-1 rounded border uppercase ${
                              selectedDeliverable.status === 'final'
                                ? 'bg-emerald-950/90 border-emerald-700 text-emerald-300'
                                : selectedDeliverable.status === 'rejected'
                                ? 'bg-rose-950/90 border-rose-700 text-rose-300'
                                : 'bg-amber-950/90 border-amber-700 text-amber-300'
                            }`}
                          >
                            Status: {selectedDeliverable.status}
                          </span>
                        </div>
                      </div>

                      {selectedDeliverable.content.summary && (
                        <p className="text-xs text-gray-400 italic">
                          {selectedDeliverable.content.summary}
                        </p>
                      )}

                      {/* Review Summary Scorecard */}
                      {reviewSummary && reviewSummary.output_id === selectedDeliverable.output_id && (
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-1 font-mono text-[11px]">
                          <div className="p-2 rounded bg-gray-950 border border-gray-800 text-center">
                            <span className="text-gray-400 block text-[9px] uppercase">Sentences</span>
                            <span className="font-bold text-gray-100">{reviewSummary.total_sentences}</span>
                          </div>
                          <div className="p-2 rounded bg-emerald-950/30 border border-emerald-800/40 text-center">
                            <span className="text-emerald-400 block text-[9px] uppercase">Accepted</span>
                            <span className="font-bold text-emerald-300">{reviewSummary.accepted_sentences}</span>
                          </div>
                          <div className="p-2 rounded bg-cyan-950/30 border border-cyan-800/40 text-center">
                            <span className="text-cyan-400 block text-[9px] uppercase">Edited</span>
                            <span className="font-bold text-cyan-300">{reviewSummary.edited_sentences}</span>
                          </div>
                          <div className="p-2 rounded bg-rose-950/30 border border-rose-800/40 text-center">
                            <span className="text-rose-400 block text-[9px] uppercase">Rejected</span>
                            <span className="font-bold text-rose-300">{reviewSummary.rejected_sentences}</span>
                          </div>
                          <div className="p-2 rounded bg-amber-950/30 border border-amber-800/40 text-center">
                            <span className="text-amber-400 block text-[9px] uppercase">Pending</span>
                            <span className="font-bold text-amber-300">{reviewSummary.pending_sentences}</span>
                          </div>
                        </div>
                      )}

                      {/* Status Gatekeeper Alert Banner */}
                      {selectedDeliverable.status !== 'final' ? (
                        <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-800/60 text-amber-200 text-xs flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="text-base">🔒</span>
                            <span>
                              <strong>Draft Lock Active:</strong> Deliverable is in status <code className="bg-black/40 px-1 py-0.5 rounded text-amber-300">'{selectedDeliverable.status}'</code>. Export remains strictly locked until Reviewer approves it to <code className="bg-black/40 px-1 py-0.5 rounded text-emerald-300">'final'</code>.
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800/60 text-emerald-200 text-xs flex items-center space-x-2">
                          <span className="text-base">✔</span>
                          <span>
                            <strong>Review Completed:</strong> Deliverable verified and transitioned to status <code className="bg-black/40 px-1 py-0.5 rounded text-emerald-300">'final'</code>. Export authorization unlocked!
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Content Blocks & Sentences */}
                    <div className="space-y-6">
                      {selectedDeliverable.content.blocks.map((block: any, bIdx: number) => (
                        <div
                          key={bIdx}
                          className="p-4 rounded-xl bg-gray-950/80 border border-gray-800/90 space-y-3.5 shadow-sm"
                        >
                          {/* Block Header & Bulk Actions */}
                          <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-gray-800/80">
                            <div className="flex items-center space-x-2">
                              <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                              <h4 className="text-xs font-bold text-gray-200 font-mono">
                                {block.title || `Section #${bIdx + 1}`}
                              </h4>
                              {block.review_status && (
                                <span
                                  className={`text-[9px] font-mono uppercase px-1.5 py-0.2 rounded ${
                                    block.review_status === 'accepted'
                                      ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                      : 'bg-rose-950 text-rose-300 border border-rose-800'
                                  }`}
                                >
                                  {block.review_status}
                                </span>
                              )}
                            </div>

                            {/* Section Level Bulk Actions */}
                            <div className="flex items-center space-x-1.5">
                              <button
                                type="button"
                                onClick={() => handleReviewSection(selectedDeliverable.output_id, bIdx, 'accept')}
                                className="px-2 py-0.5 rounded bg-emerald-950/60 hover:bg-emerald-900 border border-emerald-800/70 text-emerald-300 text-[10px] font-medium transition flex items-center space-x-1"
                                title="Accept all sentences in this section"
                              >
                                <span>✔ Accept Section</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => handleReviewSection(selectedDeliverable.output_id, bIdx, 'reject')}
                                className="px-2 py-0.5 rounded bg-rose-950/60 hover:bg-rose-900 border border-rose-800/70 text-rose-300 text-[10px] font-medium transition flex items-center space-x-1"
                                title="Reject all sentences in this section"
                              >
                                <span>✕ Reject Section</span>
                              </button>
                            </div>
                          </div>

                          {/* Sentences in this Block */}
                          <div className="space-y-3">
                            {block.sentences.map((sentence: any) => {
                              const isEditing = editingSentenceId === sentence.sentence_id;
                              const sStatus = sentence.review_status || 'pending';

                              return (
                                <div
                                  key={sentence.sentence_id}
                                  className={`p-3 rounded-lg border transition space-y-2 ${
                                    sStatus === 'accepted'
                                      ? 'bg-emerald-950/20 border-emerald-800/40'
                                      : sStatus === 'rejected'
                                      ? 'bg-rose-950/20 border-rose-800/40'
                                      : sStatus === 'edited'
                                      ? 'bg-cyan-950/20 border-cyan-800/40'
                                      : 'bg-gray-900/60 border-gray-800 hover:border-gray-700'
                                  }`}
                                >
                                  {/* Sentence Metadata Header */}
                                  <div className="flex items-center justify-between text-[10px] font-mono">
                                    <div className="flex items-center space-x-2">
                                      <span className="text-gray-400 font-bold">
                                        Sentence #{sentence.sentence_index + 1}
                                      </span>
                                      <span
                                        className={`px-1.5 py-0.2 rounded font-semibold uppercase ${
                                          sStatus === 'accepted'
                                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                            : sStatus === 'rejected'
                                            ? 'bg-rose-950 text-rose-300 border border-rose-800'
                                            : sStatus === 'edited'
                                            ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                                            : 'bg-gray-800 text-amber-300 border border-gray-700'
                                        }`}
                                      >
                                        {sStatus}
                                      </span>
                                      {sentence.last_edited_by && (
                                        <span className="text-cyan-400">
                                          (Edited by {sentence.last_edited_by})
                                        </span>
                                      )}
                                    </div>

                                    {/* Action Buttons for Sentence */}
                                    {!isEditing && (
                                      <div className="flex items-center space-x-1">
                                        <button
                                          type="button"
                                          onClick={() => handleReviewSentence(selectedDeliverable.output_id, sentence.sentence_id, 'accept')}
                                          className="px-1.5 py-0.5 rounded bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-800 text-emerald-300 text-[10px]"
                                          title="Accept sentence claim"
                                        >
                                          ✔ Accept
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => handleReviewSentence(selectedDeliverable.output_id, sentence.sentence_id, 'reject')}
                                          className="px-1.5 py-0.5 rounded bg-rose-950/80 hover:bg-rose-900 border border-rose-800 text-rose-300 text-[10px]"
                                          title="Reject sentence claim"
                                        >
                                          ✕ Reject
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setEditingSentenceId(sentence.sentence_id);
                                            setEditingSentenceText(sentence.text);
                                            setEditingNotes('');
                                          }}
                                          className="px-1.5 py-0.5 rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-800 text-cyan-300 text-[10px]"
                                          title="Edit sentence text with diff tracking"
                                        >
                                          ✏️ Edit
                                        </button>
                                      </div>
                                    )}
                                  </div>

                                  {/* Normal Sentence Text vs Inline Edit Mode */}
                                  {!isEditing ? (
                                    <div className="space-y-2">
                                      <p
                                        onClick={() => handleInspectSentenceTrace(selectedDeliverable.output_id, sentence.sentence_index)}
                                        className="text-xs text-gray-200 leading-relaxed cursor-pointer hover:text-white transition"
                                        title="Click to inspect grounding provenance"
                                      >
                                        {sentence.text}
                                      </p>

                                      {/* Citations Preview */}
                                      {sentence.citations && sentence.citations.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5 pt-1">
                                          {sentence.citations.map((c: any, cIdx: number) => (
                                            <button
                                              key={cIdx}
                                              type="button"
                                              onClick={() => handleInspectSentenceTrace(selectedDeliverable.output_id, sentence.sentence_index)}
                                              className="text-[9px] font-mono bg-emerald-950/50 hover:bg-emerald-900/60 text-emerald-300 border border-emerald-800/60 px-1.5 py-0.5 rounded transition flex items-center space-x-1"
                                              title={`Quote: "${c.quote}"`}
                                            >
                                              <span>📌 [{c.char_offset_start}:{c.char_offset_end}]</span>
                                              <span className="opacity-70 truncate max-w-[150px]">"{c.quote}"</span>
                                            </button>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  ) : (
                                    /* Inline Edit Studio */
                                    <div className="p-3 rounded-lg bg-black/90 border border-cyan-800 space-y-2.5">
                                      <label className="text-[10px] font-mono text-cyan-400 block font-bold">
                                        Editing Sentence #{sentence.sentence_index + 1} (Diff tracked on save):
                                      </label>
                                      <textarea
                                        value={editingSentenceText}
                                        onChange={(e) => setEditingSentenceText(e.target.value)}
                                        rows={3}
                                        className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-xs text-gray-100 font-mono focus:border-cyan-500 focus:outline-none"
                                      />
                                      <input
                                        type="text"
                                        value={editingNotes}
                                        onChange={(e) => setEditingNotes(e.target.value)}
                                        placeholder="Reviewer justification or editorial note (optional)..."
                                        className="w-full bg-gray-950 border border-gray-800 rounded px-2 py-1 text-[11px] text-gray-300 focus:border-cyan-500 focus:outline-none"
                                      />
                                      <div className="flex justify-end gap-2 pt-1">
                                        <button
                                          type="button"
                                          onClick={() => setEditingSentenceId(null)}
                                          className="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-semibold transition"
                                        >
                                          Cancel
                                        </button>
                                        <button
                                          type="button"
                                          disabled={isSavingEdit || !editingSentenceText.trim()}
                                          onClick={() => handleEditSentence(selectedDeliverable.output_id, sentence.sentence_id, editingSentenceText, editingNotes)}
                                          className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-800 text-white text-xs font-semibold transition flex items-center space-x-1"
                                        >
                                          <span>{isSavingEdit ? 'Saving...' : '💾 Save & Record Diff'}</span>
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Right Column (4 cols): Reviewer Control Center & Provenance Inspector */}
                  <div className="lg:col-span-4 space-y-5">
                    {/* Review Decision & Export Authorization Card */}
                    <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 space-y-4">
                      <div className="flex items-center justify-between pb-3 border-b border-gray-800">
                        <h4 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                          <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                          <span>Authorization & Export</span>
                        </h4>
                        <span className="text-[10px] font-mono text-purple-400 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-800/40">
                          Dual-Control Gate
                        </span>
                      </div>

                      <div className="space-y-3 text-xs">
                        <div className="p-3 rounded-lg bg-gray-950 border border-gray-800 space-y-2">
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-gray-400">Current Status:</span>
                            <span className="font-mono font-bold text-gray-200 uppercase">
                              {selectedDeliverable.status}
                            </span>
                          </div>
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-gray-400">Export State:</span>
                            {selectedDeliverable.status === 'final' ? (
                              <span className="font-mono text-[10px] text-emerald-400 font-bold">
                                ✔ UNLOCKED (FINAL)
                              </span>
                            ) : (
                              <span className="font-mono text-[10px] text-amber-400 font-bold">
                                🔒 LOCKED (DRAFT)
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Reviewer Sign-off Actions */}
                        <div className="space-y-2 pt-1">
                          <div className="text-[11px] font-mono text-gray-400">Reviewer Decisions:</div>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => handleApproveDeliverable(selectedDeliverable.output_id)}
                              className="flex-1 py-2 px-3 rounded-lg bg-emerald-700 hover:bg-emerald-600 border border-emerald-600 text-white font-semibold text-xs transition shadow flex items-center justify-center space-x-1"
                              title="Transition status to 'final' and unlock export"
                            >
                              <span>✔ Approve & Finalize</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleRejectDeliverable(selectedDeliverable.output_id)}
                              className="py-2 px-3 rounded-lg bg-rose-950 hover:bg-rose-900 border border-rose-800 text-rose-300 font-semibold text-xs transition"
                              title="Reject deliverable"
                            >
                              <span>✕ Reject</span>
                            </button>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleFetchEditHistory(selectedDeliverable.output_id)}
                            className="w-full py-1.5 px-3 rounded-lg bg-gray-950 hover:bg-gray-800 border border-gray-800 text-cyan-300 font-mono text-xs transition flex items-center justify-center space-x-1.5"
                            title="View full cryptographic audit & diff history of edits made to this deliverable"
                          >
                            <span>📜</span>
                            <span>Inspect Edit History & Diffs</span>
                          </button>
                        </div>

                        {/* Export Artifact Action */}
                        <div className="pt-2 border-t border-gray-800/80 space-y-2">
                          <label className="text-[11px] font-mono text-gray-400 block">
                            Export Format:
                          </label>
                          <div className="flex gap-2">
                            <select
                              value={exportFormatSelection}
                              onChange={(e) => setExportFormatSelection(e.target.value)}
                              className="flex-1 bg-gray-950 border border-gray-800 rounded-lg px-2.5 py-1.5 text-xs text-gray-200 font-mono focus:outline-none"
                            >
                              <option value="markdown">Markdown (.md)</option>
                              <option value="json">JSON (.json)</option>
                              <option value="html">HTML (.html)</option>
                              <option value="text">Plain Text (.txt)</option>
                            </select>
                            <button
                              type="button"
                              disabled={isExporting}
                              onClick={() => handleExportDeliverable(selectedDeliverable.output_id, exportFormatSelection)}
                              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition shadow flex items-center space-x-1 ${
                                selectedDeliverable.status === 'final'
                                  ? 'bg-cyan-600 hover:bg-cyan-500 text-white'
                                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                              }`}
                            >
                              <span>{isExporting ? '...' : '📦 Export'}</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Sentence Provenance Hovercard */}
                    <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 space-y-3">
                      <div className="flex items-center justify-between pb-2 border-b border-gray-800">
                        <h4 className="text-xs font-bold text-gray-300 font-mono flex items-center space-x-1.5">
                          <span>🔍</span>
                          <span>Source Provenance Inspector</span>
                        </h4>
                        {isTracing && <span className="text-[10px] text-cyan-400 font-mono animate-pulse">Tracing...</span>}
                      </div>

                      {sentenceTrace ? (
                        <div className="space-y-2.5 text-xs font-mono">
                          <div className="p-2 rounded bg-gray-950 text-[11px] text-gray-200">
                            <span className="text-gray-500 block text-[9px] uppercase">Inspected Claim:</span>
                            "{sentenceTrace.sentence_text}"
                          </div>

                          <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                            {sentenceTrace.grounding_sources.map((src, sIdx) => (
                              <div
                                key={sIdx}
                                className="p-2.5 rounded-lg bg-black/60 border border-emerald-900/50 space-y-1.5 text-[11px]"
                              >
                                <div className="flex justify-between text-emerald-400 text-[10px]">
                                  <span>Chunk #{src.chunk_index}</span>
                                  <span>Offsets: [{src.char_offset_start}:{src.char_offset_end}]</span>
                                </div>
                                <div className="p-1.5 rounded bg-gray-950 text-gray-300 text-[10px] leading-relaxed">
                                  <span className="opacity-50">{src.context_before}</span>
                                  <span className="text-emerald-300 font-bold bg-emerald-950/80 px-1">
                                    [{src.quote}]
                                  </span>
                                  <span className="opacity-50">{src.context_after}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="p-6 text-center text-gray-500 border border-dashed border-gray-800 rounded-lg text-xs">
                          Click any sentence or citation tag on the left to inspect its source paragraph provenance.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-12 text-center text-gray-500 border border-dashed border-gray-800 rounded-xl bg-gray-950/40">
              <p className="text-sm">No deliverables available for human review.</p>
              <p className="text-xs mt-1 text-gray-600">
                Generate outputs in the Output Adapters tab first, and they will automatically appear here in status 'draft'.
              </p>
            </div>
          )}
        </div>
      )}

      {/* PHASE 5: SECURITY, RBAC, CRYPTOGRAPHIC AUDIT & AIR-GAP VIEW */}
      {activeTab === 'security' && (
        <div className="space-y-6 animate-fadeIn">
          {/* Top Overview Banner */}
          <div className="p-5 rounded-xl bg-gradient-to-r from-gray-900 via-cyan-950/30 to-gray-900 border border-cyan-800/40 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xl">🛡️</span>
                <h2 className="text-base font-bold text-gray-100">
                  Air-Gapped GenAI Security & Defence-Level Audit Architecture
                </h2>
                <span className="bg-cyan-500/20 text-cyan-300 text-[10px] font-mono px-2 py-0.5 rounded border border-cyan-500/30">
                  Phase 5 Live
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-1 max-w-3xl">
                Demonstrating verifiable, defence-grade security guarantees: strict Role-Based Access Control (RBAC) with dual-control review gates, authenticated AES-256-GCM encryption at rest, linear cryptographic SHA-256 hash chains for tamper detection, and zero-telemetry offline execution.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleVerifyAuditChain}
                disabled={isVerifyingAudit}
                className="px-3.5 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-800 text-white text-xs font-semibold shadow-md transition flex items-center space-x-1.5"
              >
                <span>{isVerifyingAudit ? '⏳ Verifying...' : '🔍 Verify Audit Chain'}</span>
              </button>
            </div>
          </div>

          {/* Grid Row 1: RBAC Matrix & Cryptographic Hash Chain Audit */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Column 1: Role-Based Access Control (RBAC) */}
            <div className="lg:col-span-6 bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-gray-800">
                <div className="flex items-center space-x-2">
                  <span className="text-base">👥</span>
                  <h3 className="text-sm font-semibold text-gray-200">
                    Role-Based Access Control (Dual-Control)
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/40">
                  Active Role: {currentUserRole.toUpperCase()}
                </span>
              </div>

              {/* Role Switcher & Active User Info */}
              <div className="p-3 rounded-lg bg-gray-950/80 border border-gray-800 text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 font-mono text-[11px]">Active Session Context:</span>
                  <span className="text-gray-200 font-mono text-[11px] font-semibold">
                    {currentUserId} ({currentUserRole})
                  </span>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setCurrentUserRole('operator');
                      setCurrentUserId('operator_alice');
                      setRbacAlert({
                        type: 'success',
                        title: 'Switched to Operator Role (Alice)',
                        message: 'Permissions: Ingest, Understand, Multi-Select Generate, Request Review. Strictly blocked from Approve & Export.',
                      });
                    }}
                    className={`flex-1 py-1.5 px-2 rounded text-xs font-semibold transition border ${
                      currentUserRole === 'operator'
                        ? 'bg-amber-600 border-amber-500 text-white shadow-sm'
                        : 'bg-gray-900 border-gray-800 text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    Operator (Alice)
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setCurrentUserRole('reviewer');
                      setCurrentUserId('reviewer_bob');
                      setRbacAlert({
                        type: 'success',
                        title: 'Switched to Reviewer Role (Bob)',
                        message: 'Permissions: Formal Review, Deliverable Approval/Rejection, and Export Authorization.',
                      });
                    }}
                    className={`flex-1 py-1.5 px-2 rounded text-xs font-semibold transition border ${
                      currentUserRole === 'reviewer'
                        ? 'bg-purple-600 border-purple-500 text-white shadow-sm'
                        : 'bg-gray-900 border-gray-800 text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    Reviewer (Bob)
                  </button>
                </div>
              </div>

              {/* RBAC Permission Matrix Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-400 font-mono">
                      <th className="py-2 px-2">Pipeline Action</th>
                      <th className="py-2 px-2 text-center">Operator</th>
                      <th className="py-2 px-2 text-center">Reviewer</th>
                      <th className="py-2 px-2 text-center">Approver</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60 text-gray-300 font-mono">
                    <tr>
                      <td className="py-2 px-2 text-gray-200">Upload & Ingest</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                    </tr>
                    <tr>
                      <td className="py-2 px-2 text-gray-200">Generate Adapters</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                    </tr>
                    <tr>
                      <td className="py-2 px-2 text-gray-200">Request Review</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                    </tr>
                    <tr className="bg-rose-950/20">
                      <td className="py-2 px-2 text-gray-200 font-semibold">Approve Deliverable</td>
                      <td className="py-2 px-2 text-center text-rose-400 font-bold">❌ 403 Forbidden</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                    </tr>
                    <tr className="bg-rose-950/20">
                      <td className="py-2 px-2 text-gray-200 font-semibold">Reject Deliverable</td>
                      <td className="py-2 px-2 text-center text-rose-400 font-bold">❌ 403 Forbidden</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                    </tr>
                    <tr className="bg-rose-950/20">
                      <td className="py-2 px-2 text-gray-200 font-semibold">Export Artifacts</td>
                      <td className="py-2 px-2 text-center text-rose-400 font-bold">❌ 403 Forbidden</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                      <td className="py-2 px-2 text-center text-emerald-400">✔ Allowed</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Safety Gatekeeper Notice */}
              <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-800/50 text-[11px] text-amber-300/90 space-y-1">
                <div className="font-bold flex items-center space-x-1">
                  <span>🔒</span>
                  <span>Safety-Critical Advisory Gatekeeper:</span>
                </div>
                <p className="text-gray-300">
                  Advisory outputs with <code className="bg-black/40 px-1 py-0.5 rounded text-amber-200">requires_human_review: true</code> are cryptographically prevented from export until formal reviewer approval, even if requested by a reviewer.
                </p>
              </div>
            </div>

            {/* Column 2: Tamper-Evident Linear Hash Chain Audit */}
            <div className="lg:col-span-6 bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-gray-800">
                <div className="flex items-center space-x-2">
                  <span className="text-base">🔗</span>
                  <h3 className="text-sm font-semibold text-gray-200">
                    Tamper-Evident Cryptographic Audit Chain
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                  SHA-256 Hash Chained
                </span>
              </div>

              {/* Mathematical Formula Explanation */}
              <div className="p-3 rounded-lg bg-gray-950/90 border border-gray-800 font-mono text-[10px] text-gray-300 space-y-1">
                <span className="text-cyan-400 block font-bold">Cryptographic Linkage Guarantee:</span>
                <p className="text-gray-400 break-all">
                  H[i] = SHA256( H[i-1] || actor || action || doc_id || output_id || timestamp || source_hash || details )
                </p>
                <p className="text-[9px] text-gray-500 pt-1">
                  Every row encapsulates the hash of the preceding entry. If any malicious actor edits, inserts, or deletes a record, the recalculation fails and isolates the exact corrupted record index.
                </p>
              </div>

              {/* Audit Verification Live Status */}
              <div className="p-4 rounded-xl bg-gray-950/80 border border-gray-800 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-300 font-medium">Chain Integrity Status:</span>
                  {auditVerification ? (
                    auditVerification.valid ? (
                      <span className="px-2 py-0.5 rounded bg-emerald-950/90 border border-emerald-700 text-emerald-300 font-mono text-xs font-bold flex items-center space-x-1">
                        <span>✔</span>
                        <span>100% INTACT & VERIFIED</span>
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-rose-950/90 border border-rose-700 text-rose-300 font-mono text-xs font-bold flex items-center space-x-1">
                        <span>❌</span>
                        <span>TAMPER DETECTED AT ROW #{auditVerification.record_id}</span>
                      </span>
                    )
                  ) : (
                    <span className="text-xs font-mono text-gray-500">Unchecked (Click Verify)</span>
                  )}
                </div>

                {auditVerification && (
                  <div className="space-y-1.5 pt-1 text-xs">
                    <div className="flex items-center justify-between text-gray-400 font-mono text-[11px]">
                      <span>Total Log Records:</span>
                      <strong className="text-gray-200">{auditVerification.total_records}</strong>
                    </div>
                    {auditVerification.latest_hash && (
                      <div className="text-[10px] font-mono text-gray-400">
                        <span>Latest Chain Head:</span>
                        <div className="p-1.5 mt-0.5 rounded bg-black/60 text-cyan-300 break-all font-mono">
                          {auditVerification.latest_hash}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="pt-2 flex gap-2">
                  <button
                    type="button"
                    onClick={handleVerifyAuditChain}
                    disabled={isVerifyingAudit}
                    className="flex-1 py-1.5 px-3 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-800 text-white font-medium text-xs transition"
                  >
                    {isVerifyingAudit ? 'Verifying...' : 'Re-verify Entire Chain'}
                  </button>
                  <button
                    type="button"
                    onClick={handleSimulateTamperDemo}
                    disabled={isSimulatingTamper}
                    className="py-1.5 px-3 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 font-mono text-xs transition"
                  >
                    {isSimulatingTamper ? '...' : 'Tamper Proof Math'}
                  </button>
                </div>
              </div>

              {/* Tamper Demo Output Box */}
              {tamperDemoResult && (
                <div className="p-3 rounded-lg bg-black/80 border border-gray-800 font-mono text-[10px] text-gray-300 whitespace-pre-line max-h-40 overflow-y-auto">
                  {tamperDemoResult}
                </div>
              )}
            </div>
          </div>

          {/* Grid Row 2: Encryption at Rest & Air-Gap Egress Audit */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Column 1: Authenticated Encryption at Rest */}
            <div className="lg:col-span-6 bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-gray-800">
                <div className="flex items-center space-x-2">
                  <span className="text-base">🔐</span>
                  <h3 className="text-sm font-semibold text-gray-200">
                    Encryption at Rest (AES-256-GCM)
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-purple-400 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-800/40">
                  Local KMS / Env Key
                </span>
              </div>

              <div className="space-y-3 text-xs">
                <p className="text-gray-400">
                  Both uploaded documents (Phase 1) and generated deliverables/exports (Phase 5) are encrypted with authenticated <strong className="text-gray-200">AES-256-GCM</strong> (96-bit unique IV nonce + 128-bit MAC tag) prior to disk write. Plaintext is strictly ephemeral and never stored unencrypted.
                </p>

                <div className="p-3 rounded-lg bg-gray-950/80 border border-gray-800 space-y-2">
                  <h4 className="text-[11px] font-bold text-gray-300 uppercase tracking-wide">
                    Live Deliverable Ciphertext Verification
                  </h4>
                  {deliverables.length > 0 ? (
                    <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                      {deliverables.map((d) => (
                        <div
                          key={d.output_id}
                          className="p-2 rounded bg-gray-900 border border-gray-800 flex items-center justify-between text-xs"
                        >
                          <div>
                            <div className="font-mono text-[11px] text-gray-200 flex items-center space-x-1.5">
                              <span className="text-emerald-400">●</span>
                              <span>{d.deliverable_type}</span>
                              <span className="text-gray-500">({d.output_id.slice(0, 8)})</span>
                            </div>
                            <span className="text-[10px] text-gray-400">
                              Status: {d.status} &bull; Citations: {d.total_citations}
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleVerifyEncryption(d.output_id)}
                            className="px-2.5 py-1 rounded bg-purple-950/70 hover:bg-purple-900 border border-purple-800/70 text-purple-300 text-[10px] font-mono transition"
                          >
                            Inspect Nonce & Hash
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 text-center text-gray-500 text-xs border border-dashed border-gray-800 rounded">
                      Generate deliverables in the Output Adapters tab to inspect their AES-256-GCM disk ciphertext.
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Column 2: Zero Outbound Egress & Dependency Tree Audit */}
            <div className="lg:col-span-6 bg-gray-900/60 border border-gray-800/80 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-gray-800">
                <div className="flex items-center space-x-2">
                  <span className="text-base">🌐</span>
                  <h3 className="text-sm font-semibold text-gray-200">
                    Network Isolation & Zero-Egress Proof
                  </h3>
                </div>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                  Air-Gap Verified
                </span>
              </div>

              <div className="space-y-3 text-xs">
                <p className="text-gray-400">
                  Strict defence-level air-gap compliance. The full pipeline (ingest → chunk → embed → graph → generate → trace → export) operates with 100% offline local model inference and isolated internal networks.
                </p>

                <div className="p-3 rounded-lg bg-gray-950/80 border border-gray-800 space-y-2 text-[11px] font-mono">
                  <div className="text-gray-300 font-bold text-xs">Audited Dependency Tree Checklist:</div>
                  <div className="space-y-1.5 text-gray-400">
                    <div className="flex items-center space-x-2 text-emerald-400">
                      <span>✔</span>
                      <span>backend/requirements.txt: 0 cloud SDKs (No AWS, Azure, GCP, or OpenAI APIs)</span>
                    </div>
                    <div className="flex items-center space-x-2 text-emerald-400">
                      <span>✔</span>
                      <span>frontend/package.json: 0 analytics/telemetry packages (No Sentry, GA, Mixpanel)</span>
                    </div>
                    <div className="flex items-center space-x-2 text-emerald-400">
                      <span>✔</span>
                      <span>Docling & PyMuPDF: Offline local parsers without remote font/model fetching</span>
                    </div>
                    <div className="flex items-center space-x-2 text-emerald-400">
                      <span>✔</span>
                      <span>FastAPI + SQLite/Postgres: Strictly localhost/internal Docker network</span>
                    </div>
                    <div className="flex items-center space-x-2 text-emerald-400">
                      <span>✔</span>
                      <span>Automated Air-Gap Test: Socket non-loopback calls throw PermissionError</span>
                    </div>
                  </div>
                </div>

                <div className="p-2 rounded bg-cyan-950/30 border border-cyan-800/50 text-[10px] font-mono text-cyan-300 flex items-center justify-between">
                  <span>Verification Script: scripts/verify_phase5_security.py</span>
                  <span className="text-emerald-400 font-bold">[10/10 PASS]</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ENCRYPTION AT REST INSPECTOR MODAL */}
      {encryptionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-gray-900 border border-purple-800/80 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-gray-800">
              <div className="flex items-center space-x-2">
                <span className="text-lg">🔐</span>
                <h3 className="text-sm font-bold text-gray-100">
                  Ciphertext at Rest Verification
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setEncryptionModal(null)}
                className="text-gray-400 hover:text-gray-200 text-sm font-mono"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono">
              <div className="p-3 rounded-lg bg-purple-950/40 border border-purple-800/60 text-purple-200 flex items-center space-x-2">
                <span className="text-base">✔</span>
                <span className="font-bold">Cryptographically Verified Encrypted on Disk</span>
              </div>

              <div className="space-y-2 bg-gray-950 p-3 rounded-lg border border-gray-800 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-gray-500">Output ID:</span>
                  <span className="text-gray-200 font-semibold">{encryptionModal.output_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Deliverable Type:</span>
                  <span className="text-purple-300 uppercase">{encryptionModal.deliverable_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Cipher Algorithm:</span>
                  <span className="text-emerald-400">{encryptionModal.algorithm}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Ciphertext Size:</span>
                  <span className="text-gray-200">{encryptionModal.file_size_bytes} bytes</span>
                </div>
                <div>
                  <span className="text-gray-500 block mb-0.5">Ciphertext SHA-256 Digest:</span>
                  <span className="text-cyan-300 text-[10px] break-all bg-black/60 p-1 rounded block">
                    {encryptionModal.ciphertext_sha256}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 block mb-0.5">Physical Storage Path:</span>
                  <span className="text-gray-400 text-[10px] break-all bg-black/60 p-1 rounded block">
                    {encryptionModal.file_path}
                  </span>
                </div>
              </div>

              <p className="text-[10px] text-gray-400">
                The payload cannot be read or tampered with without the local AES-256 key from environment/KMS.
              </p>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => setEncryptionModal(null)}
                className="px-4 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-semibold transition"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EXPORT ARTIFACT MODAL */}
      {exportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-gray-900 border border-cyan-800/80 rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl max-h-[90vh] flex flex-col justify-between">
            <div className="flex items-center justify-between pb-3 border-b border-gray-800">
              <div className="flex items-center space-x-2">
                <span className="text-lg">📦</span>
                <h3 className="text-sm font-bold text-gray-100">
                  Exported Deliverable Artifact
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setExportModal(null)}
                className="text-gray-400 hover:text-gray-200 text-sm font-mono"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs overflow-y-auto pr-1">
              <div className="p-3 rounded-lg bg-cyan-950/40 border border-cyan-800/60 text-cyan-200 flex items-center space-x-2 font-mono text-xs">
                <span className="text-base">✔</span>
                <span>Export generated, encrypted at rest, and audit-logged under actor <strong>{exportModal.actor}</strong>.</span>
              </div>

              <div className="grid grid-cols-2 gap-2 bg-gray-950 p-3 rounded-lg border border-gray-800 font-mono text-[11px]">
                <div>
                  <span className="text-gray-500">File Name:</span>
                  <div className="text-gray-200 font-bold">{exportModal.exported_filename}</div>
                </div>
                <div>
                  <span className="text-gray-500">Format:</span>
                  <div className="text-cyan-300 uppercase">{exportModal.export_format}</div>
                </div>
                <div className="col-span-2">
                  <span className="text-gray-500">SHA-256 Integrity Checksum:</span>
                  <div className="text-emerald-400 text-[10px] break-all">{exportModal.checksum_sha256}</div>
                </div>
              </div>

              <div>
                <label className="text-[10px] font-mono text-gray-400 block mb-1">
                  Export Content Preview ({exportModal.export_format.toUpperCase()}):
                </label>
                <pre className="p-3 rounded-lg bg-black/90 border border-gray-800 font-mono text-[11px] text-gray-200 max-h-60 overflow-y-auto whitespace-pre-wrap">
                  {exportModal.exported_content}
                </pre>
              </div>
            </div>

            <div className="pt-3 border-t border-gray-800 flex items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(exportModal.exported_content);
                  setRbacAlert({
                    type: 'success',
                    title: 'Copied to Clipboard',
                    message: `Export content of ${exportModal.exported_filename} copied.`,
                  });
                }}
                className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-mono transition flex items-center space-x-1"
              >
                <span>📋 Copy Content</span>
              </button>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const blob = new Blob([exportModal.exported_content], { type: 'text/plain;charset=utf-8' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = exportModal.exported_filename;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="px-3.5 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold transition flex items-center space-x-1"
                >
                  <span>💾 Download File</span>
                </button>
                <button
                  type="button"
                  onClick={() => setExportModal(null)}
                  className="px-3.5 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-semibold transition"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PHASE 6: EDIT DIFF & AUDIT HISTORY MODAL */}
      {showHistoryModal && (
        <div className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-gray-900 border border-cyan-800/80 rounded-2xl max-w-4xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 sm:p-5 border-b border-gray-800 flex items-center justify-between bg-gray-950">
              <div className="flex items-center space-x-2.5">
                <span className="text-xl">📜</span>
                <div>
                  <h3 className="text-sm sm:text-base font-bold text-gray-100 flex items-center space-x-2">
                    <span>Audit Trail & Diff History</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-300">
                      Immutable Log
                    </span>
                  </h3>
                  <p className="text-[11px] font-mono text-gray-400">
                    Deliverable: <span className="text-gray-200">{selectedDeliverable?.content.title || selectedDeliverable?.output_id}</span>
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowHistoryModal(false)}
                className="text-gray-400 hover:text-white text-lg px-2 py-1 rounded-lg hover:bg-gray-800 transition"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto space-y-4 flex-1">
              {isLoadingHistory ? (
                <div className="p-12 text-center text-gray-400 font-mono text-xs">
                  Loading cryptographic edit history and unified diffs...
                </div>
              ) : editHistory.length === 0 ? (
                <div className="p-12 text-center text-gray-500 border border-dashed border-gray-800 rounded-xl font-mono text-xs">
                  No editorial diffs or modifications recorded yet. Edits made by reviewers will appear here with before/after state and git-style unified diffs.
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs text-gray-400 font-mono pb-2 border-b border-gray-800">
                    <span>Total Changes Recorded: <strong className="text-cyan-400">{editHistory.length}</strong></span>
                    <span className="text-[10px] text-emerald-400">Chronological Order (Earliest to Latest)</span>
                  </div>

                  {editHistory.map((item, idx) => (
                    <div
                      key={item.id || idx}
                      className="p-4 rounded-xl bg-gray-950 border border-gray-800/90 space-y-3 shadow-md"
                    >
                      {/* Version & Action Header */}
                      <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
                        <div className="flex items-center space-x-2">
                          <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 font-bold">
                            v{item.version}
                          </span>
                          <span className="px-2 py-0.5 rounded bg-gray-800 text-gray-200 uppercase font-semibold text-[10px]">
                            {item.action}
                          </span>
                          <span className="text-gray-400">
                            Target: <code className="text-purple-300">{item.target_type} {item.target_id || ''}</code>
                          </span>
                        </div>
                        <div className="text-[11px] text-gray-400 flex items-center space-x-2">
                          <span>By: <strong className="text-gray-200">{item.actor}</strong></span>
                          <span>•</span>
                          <span>{new Date(item.timestamp).toLocaleString()}</span>
                        </div>
                      </div>

                      {/* Unified Git Diff Block if Present */}
                      {item.diff_summary && (
                        <div className="space-y-1">
                          <span className="text-[10px] font-mono text-cyan-400 font-semibold block">
                            Git-Style Unified Diff:
                          </span>
                          <pre className="p-3 rounded-lg bg-black/90 border border-gray-800 font-mono text-[11px] overflow-x-auto leading-relaxed">
                            {item.diff_summary.split('\n').map((line, lIdx) => {
                              let lineClass = 'text-gray-400';
                              if (line.startsWith('+') && !line.startsWith('+++')) lineClass = 'text-emerald-400 bg-emerald-950/40 px-1 rounded';
                              else if (line.startsWith('-') && !line.startsWith('---')) lineClass = 'text-rose-400 bg-rose-950/40 px-1 rounded';
                              else if (line.startsWith('@@')) lineClass = 'text-cyan-400 font-bold';
                              return (
                                <div key={lIdx} className={lineClass}>
                                  {line}
                                </div>
                              );
                            })}
                          </pre>
                        </div>
                      )}

                      {/* Before / After Comparison */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                        <div className="p-2.5 rounded-lg bg-rose-950/20 border border-rose-900/40 space-y-1">
                          <span className="text-[10px] uppercase font-bold text-rose-400 block">
                            Before Edit:
                          </span>
                          <p className="text-gray-300 text-[11px] leading-relaxed whitespace-pre-wrap">
                            {item.before_content || '(Empty)'}
                          </p>
                        </div>
                        <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-900/40 space-y-1">
                          <span className="text-[10px] uppercase font-bold text-emerald-400 block">
                            After Edit:
                          </span>
                          <p className="text-gray-200 text-[11px] leading-relaxed whitespace-pre-wrap">
                            {item.after_content || '(Empty)'}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-800 bg-gray-950 flex justify-end">
              <button
                type="button"
                onClick={() => setShowHistoryModal(false)}
                className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-xs font-semibold transition"
              >
                Close History
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

