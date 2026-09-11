import React, { useState, useEffect, useCallback } from 'react';

export interface GroundingCitation {
  chunk_id: string;
  char_offset_start: number;
  char_offset_end: number;
  quote: string;
}

export interface GroundingSentence {
  sentence_id: string;
  sentence_index: number;
  text: string;
  citations: GroundingCitation[];
}

export interface DeliverableBlock {
  block_index: number;
  title?: string;
  sentences: GroundingSentence[];
}

export interface DeliverableData {
  output_id: string;
  doc_id: string;
  deliverable_type: string;
  status: 'draft' | 'pending_review' | 'approved' | 'rejected' | string;
  reviewer_id?: string | null;
  reviewer_notes?: string | null;
  approved_at?: string | null;
  total_sentences: number;
  total_citations: number;
  contract_verified: boolean;
  encrypted_file_path?: string;
  content: {
    title: string;
    summary?: string;
    blocks: DeliverableBlock[];
  };
}

export interface DiffHistoryItem {
  diff_id: number;
  output_id: string;
  actor: string;
  change_type: string;
  target_id: string;
  unified_diff: string;
  notes?: string;
  timestamp: string;
}

export interface SentenceTraceData {
  output_id: string;
  sentence_id: string;
  sentence_index: number;
  sentence_text: string;
  grounding_sources: Array<{
    chunk_id: string;
    chunk_index: number;
    heading?: string;
    char_offset_start: number;
    char_offset_end: number;
    quote: string;
    context_before: string;
    context_after: string;
  }>;
}

interface HumanReviewWorkspaceProps {
  userRole: 'operator' | 'reviewer';
  onSwitchRole: (role: 'operator' | 'reviewer') => void;
  activeDocId?: string | null;
  onRefreshAuditLogs?: () => void;
  onToast: (msg: { type: 'success' | 'alert'; text: string }) => void;
  onExportSuccess?: (exportResult: any) => void;
}

export const HumanReviewWorkspace: React.FC<HumanReviewWorkspaceProps> = ({
  userRole,
  onSwitchRole,
  activeDocId,
  onRefreshAuditLogs,
  onToast,
  onExportSuccess,
}) => {
  // Queue & Selection
  const [deliverables, setDeliverables] = useState<DeliverableData[]>([]);
  const [selectedOutputId, setSelectedOutputId] = useState<string | null>(null);
  const [isLoadingQueue, setIsLoadingQueue] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'all' | 'pending_review' | 'draft' | 'approved' | 'rejected'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Active Review State
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [reviewerNotes, setReviewerNotes] = useState('');
  const [operatorNotes, setOperatorNotes] = useState('');

  // Sentence Edit State
  const [editingSentenceId, setEditingSentenceId] = useState<string | null>(null);
  const [editedText, setEditedText] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  // Citation Trace Inspector
  const [activeSentenceTrace, setActiveSentenceTrace] = useState<SentenceTraceData | null>(null);
  const [isLoadingTrace, setIsLoadingTrace] = useState(false);

  // Diff History
  const [diffHistory, setDiffHistory] = useState<DiffHistoryItem[]>([]);
  const [isLoadingDiffs, setIsLoadingDiffs] = useState(false);
  const [activeInspectorTab, setActiveInspectorTab] = useState<'citations' | 'diffs'>('citations');

  // Export Format
  const [exportFormat, setExportFormat] = useState('markdown');
  const [isExporting, setIsExporting] = useState(false);

  // Fetch pending deliverables queue
  const fetchDeliverables = useCallback(async () => {
    setIsLoadingQueue(true);
    try {
      const url = activeDocId
        ? `/api/v1/review/pending?doc_id=${activeDocId}`
        : `/api/v1/review/pending`;

      const res = await fetch(url, {
        headers: {
          'X-User-Role': userRole,
          'X-User-Id': userRole === 'reviewer' ? 'reviewer_primary' : 'operator_primary',
        },
      });

      if (res.ok) {
        const list: DeliverableData[] = await res.json();
        setDeliverables(list);
        if (list.length > 0 && !selectedOutputId) {
          setSelectedOutputId(list[0].output_id);
        }
      }
    } catch (err) {
      console.error('Failed to load review deliverables:', err);
    } finally {
      setIsLoadingQueue(false);
    }
  }, [activeDocId, userRole, selectedOutputId]);

  useEffect(() => {
    fetchDeliverables();
  }, [fetchDeliverables]);

  // Selected deliverable data
  const selectedDeliverable = deliverables.find((d) => d.output_id === selectedOutputId) || null;

  // Load Diff History for selected deliverable
  const fetchDiffHistory = useCallback(async (outputId: string) => {
    setIsLoadingDiffs(true);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/history`, {
        headers: {
          'X-User-Role': userRole,
          'X-User-Id': userRole === 'reviewer' ? 'reviewer_primary' : 'operator_primary',
        },
      });
      if (res.ok) {
        const history: DiffHistoryItem[] = await res.json();
        setDiffHistory(history);
      }
    } catch (err) {
      console.error('Failed to load diff history:', err);
    } finally {
      setIsLoadingDiffs(false);
    }
  }, [userRole]);

  useEffect(() => {
    if (selectedOutputId) {
      fetchDiffHistory(selectedOutputId);
      setActiveSentenceTrace(null);
      setEditingSentenceId(null);
    }
  }, [selectedOutputId, fetchDiffHistory]);

  // Trace a sentence against ground truth
  const handleTraceSentence = async (outputId: string, sentenceIndex: number) => {
    setIsLoadingTrace(true);
    setActiveInspectorTab('citations');
    try {
      const res = await fetch(`/api/v1/grounding/trace/${outputId}/${sentenceIndex}`, {
        headers: {
          'X-User-Role': userRole,
          'X-User-Id': userRole === 'reviewer' ? 'reviewer_primary' : 'operator_primary',
        },
      });
      if (res.ok) {
        const data: SentenceTraceData = await res.json();
        setActiveSentenceTrace(data);
      }
    } catch (err) {
      console.error('Failed to trace sentence:', err);
    } finally {
      setIsLoadingTrace(false);
    }
  };

  // Submit deliverable for formal review (Operator action)
  const handleRequestApproval = async (outputId: string) => {
    setIsActionLoading(true);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/request-approval`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': 'operator',
          'X-User-Id': 'operator_primary',
        },
        body: JSON.stringify({ notes: operatorNotes || 'Submitted for formal review verification.' }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail?.message || errJson?.detail || `HTTP ${res.status}`);
      }

      const updated: DeliverableData = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      setOperatorNotes('');
      onToast({ type: 'success', text: 'Deliverable submitted to reviewer queue (status: pending_review).' });
      if (onRefreshAuditLogs) onRefreshAuditLogs();
    } catch (err: any) {
      onToast({ type: 'alert', text: err.message || 'Failed to submit for approval' });
    } finally {
      setIsActionLoading(false);
    }
  };

  // Formally approve deliverable (Reviewer action)
  const handleApprove = async (outputId: string) => {
    setIsActionLoading(true);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': 'reviewer',
          'X-User-Id': 'reviewer_primary',
        },
        body: JSON.stringify({
          reviewer_notes: reviewerNotes || 'Verified 100% ground-truth citations. Approved for distribution.',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail?.message || errJson?.detail || `HTTP ${res.status}`);
      }

      const updated: DeliverableData = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      setReviewerNotes('');
      onToast({ type: 'success', text: 'Deliverable certified and approved. Export authorization unlocked!' });
      if (onRefreshAuditLogs) onRefreshAuditLogs();
    } catch (err: any) {
      onToast({ type: 'alert', text: err.message || 'Approval failed' });
    } finally {
      setIsActionLoading(false);
    }
  };

  // Formally reject deliverable (Reviewer action)
  const handleReject = async (outputId: string) => {
    if (!reviewerNotes.trim()) {
      onToast({ type: 'alert', text: 'Please provide reviewer notes explaining rejection reason.' });
      return;
    }

    setIsActionLoading(true);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': 'reviewer',
          'X-User-Id': 'reviewer_primary',
        },
        body: JSON.stringify({ reviewer_notes: reviewerNotes }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail?.message || errJson?.detail || `HTTP ${res.status}`);
      }

      const updated: DeliverableData = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      setReviewerNotes('');
      onToast({ type: 'alert', text: 'Deliverable rejected with feedback. Sent back for revision.' });
      if (onRefreshAuditLogs) onRefreshAuditLogs();
    } catch (err: any) {
      onToast({ type: 'alert', text: err.message || 'Rejection failed' });
    } finally {
      setIsActionLoading(false);
    }
  };

  // Save sentence edit and record cryptographic audit diff
  const handleSaveSentenceEdit = async (outputId: string, sentenceId: string) => {
    if (!editedText.trim()) return;
    setIsSavingEdit(true);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/edit-sentence`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': userRole,
          'X-User-Id': userRole === 'reviewer' ? 'reviewer_primary' : 'operator_primary',
        },
        body: JSON.stringify({
          sentence_id: sentenceId,
          new_text: editedText.trim(),
          notes: editNotes.trim() || 'Editorial claim refinement.',
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail?.message || errJson?.detail || `HTTP ${res.status}`);
      }

      const updated: DeliverableData = await res.json();
      setDeliverables((prev) => prev.map((d) => (d.output_id === outputId ? updated : d)));
      setEditingSentenceId(null);
      setEditedText('');
      setEditNotes('');
      fetchDiffHistory(outputId);
      onToast({ type: 'success', text: 'Sentence edited. Cryptographic diff recorded in audit log.' });
      if (onRefreshAuditLogs) onRefreshAuditLogs();
    } catch (err: any) {
      onToast({ type: 'alert', text: err.message || 'Sentence edit failed' });
    } finally {
      setIsSavingEdit(false);
    }
  };

  // Export deliverable with gatekeeper protection
  const handleExport = async (outputId: string) => {
    setIsExporting(true);
    try {
      const res = await fetch(`/api/v1/review/outputs/${outputId}/export`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': userRole,
          'X-User-Id': userRole === 'reviewer' ? 'reviewer_primary' : 'operator_primary',
        },
        body: JSON.stringify({ export_format: exportFormat }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        const msg = errJson?.detail?.message || errJson?.detail?.error || errJson?.detail || `HTTP ${res.status}`;
        throw new Error(msg);
      }

      const data = await res.json();
      onToast({ type: 'success', text: `Exported ${exportFormat.toUpperCase()} package with SHA-256 checksum.` });
      if (onExportSuccess) onExportSuccess(data);
      if (onRefreshAuditLogs) onRefreshAuditLogs();
    } catch (err: any) {
      onToast({ type: 'alert', text: err.message || 'Export gatekeeper blocked distribution.' });
    } finally {
      setIsExporting(false);
    }
  };

  // Filtered deliverables list
  const filteredDeliverables = deliverables.filter((d) => {
    if (statusFilter !== 'all' && d.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchType = d.deliverable_type.toLowerCase().includes(q);
      const matchTitle = d.content?.title?.toLowerCase().includes(q);
      if (!matchType && !matchTitle) return false;
    }
    return true;
  });

  const pendingCount = deliverables.filter((d) => d.status === 'pending_review').length;
  const draftCount = deliverables.filter((d) => d.status === 'draft').length;
  const approvedCount = deliverables.filter((d) => d.status === 'approved' || d.status === 'final').length;
  const rejectedCount = deliverables.filter((d) => d.status === 'rejected').length;

  return (
    <div className="space-y-4">
      {/* Top Banner: Dual-Control Principle & Persona Switcher */}
      <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 shadow-soft flex flex-col md:flex-row md:items-center justify-between gap-3 bg-gradient-to-r from-[#FCFBF8] via-[#F8F7F3] to-[#FCFBF8]">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-[#D97706] animate-pulse"></span>
            <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wider">
              Dual-Control Human Review Checkpoint (Airgap Mandate § 2)
            </span>
          </div>
          <p className="text-[11px] text-[#6F6D68]">
            No automated GenAI deliverable may be exported without two-person rule verification. Inspect ground-truth citations, track sentence diffs, and authorize release.
          </p>
        </div>

        {/* Active Persona Switcher */}
        <div className="flex items-center space-x-2 shrink-0">
          <span className="text-[11px] font-mono text-[#6F6D68]">Active Persona:</span>
          <div className="flex items-center rounded-md border border-[#D8D5CE] bg-[#FCFBF8] p-0.5">
            <button
              onClick={() => onSwitchRole('operator')}
              className={`px-3 py-1 rounded text-xs font-mono transition ${
                userRole === 'operator'
                  ? 'bg-[#30302E] text-white shadow-soft'
                  : 'text-[#6F6D68] hover:text-[#252525]'
              }`}
            >
              Operator (Analyst)
            </button>
            <button
              onClick={() => onSwitchRole('reviewer')}
              className={`px-3 py-1 rounded text-xs font-mono transition ${
                userRole === 'reviewer'
                  ? 'bg-[#15803D] text-white shadow-soft font-semibold'
                  : 'text-[#6F6D68] hover:text-[#252525]'
              }`}
            >
              Reviewer (Approver)
            </button>
          </div>
        </div>
      </div>

      {/* Main Grid: Queue on Left (4 cols), Review Workbench on Right (8 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Deliverable Review Queue */}
        <div className="lg:col-span-4 space-y-3">
          <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-3.5 space-y-3 shadow-soft">
            <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
              <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                Review Queue ({deliverables.length})
              </span>
              <button
                onClick={fetchDeliverables}
                disabled={isLoadingQueue}
                className="text-[10px] font-mono text-[#E8A36A] hover:underline"
              >
                {isLoadingQueue ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>

            {/* Filter Pills */}
            <div className="flex flex-wrap gap-1 text-[10px] font-mono">
              <button
                onClick={() => setStatusFilter('all')}
                className={`px-2 py-0.5 rounded border transition ${
                  statusFilter === 'all'
                    ? 'bg-[#30302E] text-white border-[#30302E]'
                    : 'bg-[#FCFBF8] text-[#6F6D68] border-[#D8D5CE]'
                }`}
              >
                All ({deliverables.length})
              </button>
              <button
                onClick={() => setStatusFilter('pending_review')}
                className={`px-2 py-0.5 rounded border transition ${
                  statusFilter === 'pending_review'
                    ? 'bg-[#D97706] text-white border-[#D97706]'
                    : 'bg-[#FCFBF8] text-[#D97706] border-[#D8D5CE]'
                }`}
              >
                Pending ({pendingCount})
              </button>
              <button
                onClick={() => setStatusFilter('draft')}
                className={`px-2 py-0.5 rounded border transition ${
                  statusFilter === 'draft'
                    ? 'bg-[#6F6D68] text-white border-[#6F6D68]'
                    : 'bg-[#FCFBF8] text-[#6F6D68] border-[#D8D5CE]'
                }`}
              >
                Draft ({draftCount})
              </button>
              <button
                onClick={() => setStatusFilter('approved')}
                className={`px-2 py-0.5 rounded border transition ${
                  statusFilter === 'approved'
                    ? 'bg-[#15803D] text-white border-[#15803D]'
                    : 'bg-[#FCFBF8] text-[#15803D] border-[#D8D5CE]'
                }`}
              >
                Approved ({approvedCount})
              </button>
              <button
                onClick={() => setStatusFilter('rejected')}
                className={`px-2 py-0.5 rounded border transition ${
                  statusFilter === 'rejected'
                    ? 'bg-[#B91C1C] text-white border-[#B91C1C]'
                    : 'bg-[#FCFBF8] text-[#B91C1C] border-[#D8D5CE]'
                }`}
              >
                Rejected ({rejectedCount})
              </button>
            </div>

            {/* Search filter */}
            <input
              type="text"
              placeholder="Filter deliverables..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2.5 py-1 text-xs text-[#252525] font-mono focus:outline-none focus:border-[#30302E]"
            />

            {/* Deliverables List */}
            <div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">
              {filteredDeliverables.length > 0 ? (
                filteredDeliverables.map((item) => {
                  const isSelected = selectedOutputId === item.output_id;
                  const isApproved = item.status === 'approved' || item.status === 'final';
                  const isPending = item.status === 'pending_review';
                  const isRejected = item.status === 'rejected';

                  return (
                    <div
                      key={item.output_id}
                      onClick={() => setSelectedOutputId(item.output_id)}
                      className={`p-3 rounded-lg border text-xs cursor-pointer transition space-y-1.5 ${
                        isSelected
                          ? 'bg-[#F8F7F3] border-[#30302E] shadow-sm'
                          : 'bg-[#FCFBF8] border-[#D8D5CE] hover:border-[#C7C3BA]'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-semibold text-[#252525] uppercase text-[11px] truncate">
                          {item.deliverable_type.replace('_', ' ')}
                        </span>
                        <span
                          className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${
                            isApproved
                              ? 'bg-[#EBF7EE] text-[#15803D] border-[#BBE5C4]'
                              : isPending
                              ? 'bg-[#FEF3C7] text-[#D97706] border-[#FDE68A]'
                              : isRejected
                              ? 'bg-[#FEE2E2] text-[#DC2626] border-[#FECACA]'
                              : 'bg-[#F3F4F6] text-[#6B7280] border-[#E5E7EB]'
                          }`}
                        >
                          {item.status}
                        </span>
                      </div>

                      <div className="text-xs font-serif text-[#252525] font-medium truncate">
                        {item.content?.title || 'Untitled Deliverable'}
                      </div>

                      <div className="flex items-center justify-between text-[10px] font-mono text-[#6F6D68] pt-1 border-t border-[#D8D5CE]/60">
                        <span>{item.total_sentences} claims &bull; {item.total_citations} citations</span>
                        <span className="truncate max-w-[100px]">Doc: {item.doc_id?.slice(0, 8)}</span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="p-8 text-center text-[#99958D] text-xs font-mono">
                  No deliverables match the selected filter.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Review & Sign-Off Workbench */}
        <div className="lg:col-span-8 space-y-3.5">
          {selectedDeliverable ? (
            <div className="space-y-3.5">
              {/* Deliverable Status & Action Header */}
              <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 shadow-soft space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#D8D5CE]">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono uppercase tracking-wider text-[#6F6D68]">
                        Format: <strong className="text-[#252525]">{selectedDeliverable.deliverable_type}</strong>
                      </span>
                      <span className="text-[#D8D5CE]">&bull;</span>
                      <span className="text-[10px] font-mono text-[#6F6D68]">
                        ID: {selectedDeliverable.output_id.slice(0, 8)}...
                      </span>
                    </div>
                    <h2 className="text-lg font-serif font-bold text-[#252525] tracking-tight mt-0.5">
                      {selectedDeliverable.content.title}
                    </h2>
                  </div>

                  {/* Export Controls */}
                  <div className="flex items-center space-x-2 shrink-0">
                    <select
                      value={exportFormat}
                      onChange={(e) => setExportFormat(e.target.value)}
                      className="bg-[#F8F7F3] border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525] font-mono"
                    >
                      <option value="markdown">Markdown (.md)</option>
                      <option value="json">JSON (.json)</option>
                      <option value="html">HTML (.html)</option>
                      <option value="text">Plain Text (.txt)</option>
                    </select>

                    <button
                      onClick={() => handleExport(selectedDeliverable.output_id)}
                      disabled={isExporting}
                      className={`px-3.5 py-1.5 rounded text-xs font-mono font-medium transition shadow-soft flex items-center space-x-1.5 ${
                        selectedDeliverable.status === 'approved' || selectedDeliverable.status === 'final'
                          ? 'bg-[#15803D] hover:bg-[#166534] text-white cursor-pointer'
                          : 'bg-[#B9B8B3] text-white cursor-not-allowed opacity-75'
                      }`}
                      title={
                        selectedDeliverable.status === 'approved' || selectedDeliverable.status === 'final'
                          ? 'Export certified deliverable'
                          : 'Export is locked pending certified Reviewer sign-off'
                      }
                    >
                      {isExporting ? (
                        <span>Exporting...</span>
                      ) : (
                        <>
                          {selectedDeliverable.status === 'approved' || selectedDeliverable.status === 'final' ? (
                            <span>✓ Export Release</span>
                          ) : (
                            <span>🔒 Export Locked</span>
                          )}
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Dynamic Status Callout Banner */}
                {selectedDeliverable.status === 'draft' && (
                  <div className="p-3 rounded-md bg-[#F3F4F6] border border-[#E5E7EB] text-xs font-mono space-y-2">
                    <div className="flex items-center justify-between text-[#4B5563]">
                      <span className="font-semibold">Current State: DRAFT (Export Authorization Locked)</span>
                      <span className="text-[10px]">Dual-Control Mandate</span>
                    </div>
                    <p className="text-[11px] text-[#6B7280]">
                      This AI-generated deliverable has passed 100% citation grounding contract verification. To proceed toward publication, an Operator must submit it for certified reviewer evaluation.
                    </p>
                    <div className="flex items-center space-x-2 pt-1">
                      <input
                        type="text"
                        placeholder="Optional operator context / notes for reviewer..."
                        value={operatorNotes}
                        onChange={(e) => setOperatorNotes(e.target.value)}
                        className="flex-1 bg-white border border-[#D8D5CE] rounded px-2.5 py-1 text-xs text-[#252525]"
                      />
                      <button
                        onClick={() => handleRequestApproval(selectedDeliverable.output_id)}
                        disabled={isActionLoading}
                        className="px-3 py-1 rounded bg-[#30302E] hover:bg-[#252525] text-white text-xs font-medium transition shrink-0"
                      >
                        {isActionLoading ? 'Submitting...' : 'Submit for Human Review &rarr;'}
                      </button>
                    </div>
                  </div>
                )}

                {selectedDeliverable.status === 'pending_review' && (
                  <div className="p-3 rounded-md bg-[#FEF3C7] border border-[#FDE68A] text-xs font-mono space-y-2">
                    <div className="flex items-center justify-between text-[#92400E]">
                      <span className="font-semibold">Current State: PENDING HUMAN REVIEW</span>
                      <span className="text-[10px]">Awaiting Certified Sign-off</span>
                    </div>
                    <p className="text-[11px] text-[#78350F]">
                      Submitted for verification. Examine claim accuracy against source citations below. Certified Reviewers may approve for release or reject with revision notes.
                    </p>

                    {userRole === 'reviewer' ? (
                      <div className="space-y-2 pt-1 border-t border-[#FDE68A]">
                        <textarea
                          placeholder="Reviewer justification, citation verification notes, or revision reasons..."
                          value={reviewerNotes}
                          onChange={(e) => setReviewerNotes(e.target.value)}
                          rows={2}
                          className="w-full bg-white border border-[#D8D5CE] rounded p-2 text-xs text-[#252525] focus:outline-none focus:border-[#15803D]"
                        />
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => handleReject(selectedDeliverable.output_id)}
                            disabled={isActionLoading}
                            className="px-3 py-1 rounded bg-[#FCFBF8] border border-[#DC2626] text-[#DC2626] hover:bg-[#FEE2E2] text-xs font-medium transition"
                          >
                            ✕ Reject &amp; Request Revision
                          </button>
                          <button
                            onClick={() => handleApprove(selectedDeliverable.output_id)}
                            disabled={isActionLoading}
                            className="px-4 py-1 rounded bg-[#15803D] hover:bg-[#166534] text-white text-xs font-semibold transition shadow-soft"
                          >
                            ✓ Approve &amp; Authorize Export
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="text-[11px] text-[#B45309] italic">
                        Logged in as Operator. Switch to "Reviewer (Approver)" persona above to execute formal sign-off.
                      </div>
                    )}
                  </div>
                )}

                {(selectedDeliverable.status === 'approved' || selectedDeliverable.status === 'final') && (
                  <div className="p-3 rounded-md bg-[#EBF7EE] border border-[#BBE5C4] text-xs font-mono space-y-1">
                    <div className="flex items-center justify-between text-[#15803D]">
                      <span className="font-semibold">✓ CERTIFIED BY HUMAN REVIEWER (EXPORT UNLOCKED)</span>
                      <span className="text-[10px]">Reviewer: {selectedDeliverable.reviewer_id || 'reviewer_primary'}</span>
                    </div>
                    {selectedDeliverable.reviewer_notes && (
                      <p className="text-[11px] text-[#166534] italic">
                        "{selectedDeliverable.reviewer_notes}"
                      </p>
                    )}
                  </div>
                )}

                {selectedDeliverable.status === 'rejected' && (
                  <div className="p-3 rounded-md bg-[#FEE2E2] border border-[#FECACA] text-xs font-mono space-y-1">
                    <div className="flex items-center justify-between text-[#DC2626]">
                      <span className="font-semibold">✕ REJECTED BY HUMAN REVIEWER</span>
                      <span className="text-[10px]">Revision Required</span>
                    </div>
                    {selectedDeliverable.reviewer_notes && (
                      <p className="text-[11px] text-[#991B1B] italic">
                        Feedback: "{selectedDeliverable.reviewer_notes}"
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Claims & Sentence Inspector with Inline Editing */}
              <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 shadow-soft space-y-3.5">
                <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
                  <div>
                    <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                      Claims &amp; Grounding Sentences ({selectedDeliverable.total_sentences})
                    </span>
                    <p className="text-[11px] text-[#6F6D68]">
                      Click "Inspect" to check character citations or "Edit" to refine claims with immutable diff logging.
                    </p>
                  </div>
                  <div className="flex items-center space-x-1 font-mono text-[10px]">
                    <button
                      onClick={() => setActiveInspectorTab('citations')}
                      className={`px-2.5 py-1 rounded border transition ${
                        activeInspectorTab === 'citations'
                          ? 'bg-[#30302E] text-white border-[#30302E]'
                          : 'bg-[#FCFBF8] text-[#6F6D68] border-[#D8D5CE]'
                      }`}
                    >
                      Citations
                    </button>
                    <button
                      onClick={() => setActiveInspectorTab('diffs')}
                      className={`px-2.5 py-1 rounded border transition ${
                        activeInspectorTab === 'diffs'
                          ? 'bg-[#30302E] text-white border-[#30302E]'
                          : 'bg-[#FCFBF8] text-[#6F6D68] border-[#D8D5CE]'
                      }`}
                    >
                      Diff History ({diffHistory.length})
                    </button>
                  </div>
                </div>

                {/* Sentences List */}
                <div className="space-y-3">
                  {selectedDeliverable.content.blocks.map((block) => (
                    <div key={block.block_index} className="space-y-2">
                      {block.title && (
                        <h4 className="text-xs font-mono font-semibold text-[#6F6D68] uppercase tracking-wider pt-1">
                          {block.title}
                        </h4>
                      )}

                      <div className="space-y-2">
                        {block.sentences.map((sentence) => {
                          const isEditing = editingSentenceId === sentence.sentence_id;
                          const isInspecting = activeSentenceTrace?.sentence_id === sentence.sentence_id;

                          return (
                            <div
                              key={sentence.sentence_id}
                              className={`p-3 rounded-lg border text-xs transition space-y-2 ${
                                isInspecting
                                  ? 'bg-[#F5DEA0]/20 border-[#E8A36A]'
                                  : 'bg-[#F8F7F3] border-[#D8D5CE]'
                              }`}
                            >
                              <div className="flex items-center justify-between text-[10px] font-mono text-[#6F6D68]">
                                <span className="font-semibold text-[#252525]">Claim #{sentence.sentence_index + 1}</span>
                                <div className="flex items-center space-x-2">
                                  <span className="text-[#15803D]">
                                    {sentence.citations.length} verified citation{sentence.citations.length > 1 ? 's' : ''}
                                  </span>
                                  <button
                                    onClick={() => handleTraceSentence(selectedDeliverable.output_id, sentence.sentence_index)}
                                    className="text-[#E8A36A] hover:underline"
                                  >
                                    Inspect &rarr;
                                  </button>
                                  <button
                                    onClick={() => {
                                      if (isEditing) {
                                        setEditingSentenceId(null);
                                      } else {
                                        setEditingSentenceId(sentence.sentence_id);
                                        setEditedText(sentence.text);
                                        setEditNotes('');
                                      }
                                    }}
                                    className="text-[#30302E] hover:underline font-medium"
                                  >
                                    {isEditing ? 'Cancel Edit' : 'Edit Claim'}
                                  </button>
                                </div>
                              </div>

                              {isEditing ? (
                                <div className="space-y-2 pt-1 border-t border-[#D8D5CE]">
                                  <textarea
                                    value={editedText}
                                    onChange={(e) => setEditedText(e.target.value)}
                                    rows={3}
                                    className="w-full bg-white border border-[#30302E] rounded p-2 text-xs text-[#252525] font-serif leading-relaxed"
                                  />
                                  <div className="flex items-center space-x-2">
                                    <input
                                      type="text"
                                      placeholder="Editorial notes / justification..."
                                      value={editNotes}
                                      onChange={(e) => setEditNotes(e.target.value)}
                                      className="flex-1 bg-white border border-[#D8D5CE] rounded px-2 py-1 text-xs text-[#252525] font-mono"
                                    />
                                    <button
                                      onClick={() => handleSaveSentenceEdit(selectedDeliverable.output_id, sentence.sentence_id)}
                                      disabled={isSavingEdit || !editedText.trim()}
                                      className="px-3 py-1 rounded bg-[#30302E] hover:bg-[#252525] text-white text-xs font-mono transition shrink-0"
                                    >
                                      {isSavingEdit ? 'Saving...' : 'Save & Record Diff'}
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                <p className="text-[12px] font-serif leading-relaxed text-[#252525]">
                                  {sentence.text}
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bottom Inspection Drawer: Citations OR Diff History */}
              {activeInspectorTab === 'citations' && (
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 shadow-soft space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
                    <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                      Ground Truth Citation Inspector
                    </span>
                    {isLoadingTrace && (
                      <span className="text-[10px] font-mono text-[#6F6D68]">Resolving coordinates...</span>
                    )}
                  </div>

                  {activeSentenceTrace ? (
                    <div className="space-y-2.5">
                      <div className="text-xs font-serif text-[#252525] italic border-l-2 border-[#E8A36A] pl-2 py-0.5">
                        Examining Claim #{activeSentenceTrace.sentence_index + 1}: "{activeSentenceTrace.sentence_text}"
                      </div>

                      <div className="space-y-2">
                        {activeSentenceTrace.grounding_sources.map((src, i) => (
                          <div key={i} className="p-3 rounded bg-[#F8F7F3] border border-[#D8D5CE] space-y-1.5 text-xs font-mono">
                            <div className="flex items-center justify-between text-[#6F6D68] text-[10px]">
                              <span className="font-semibold text-[#252525]">Source Chunk #{src.chunk_index}</span>
                              <span>Span: [{src.char_offset_start}:{src.char_offset_end}]</span>
                            </div>
                            {src.heading && (
                              <div className="text-[10px] text-[#6F6D68]">Section: § {src.heading}</div>
                            )}
                            <div className="p-2 rounded bg-[#F5DEA0]/40 border border-[#EBCB72] text-[11px] leading-relaxed text-[#252525]">
                              "{src.quote}"
                            </div>
                            <div className="text-[10px] text-[#99958D] leading-tight">
                              <span>{src.context_before}</span>
                              <span className="text-[#252525] font-bold underline px-1">[{src.quote.slice(0, 24)}...]</span>
                              <span>{src.context_after}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="p-6 text-center text-[#99958D] text-xs font-mono">
                      Click "Inspect &rarr;" on any claim above to examine verbatim character coordinates and ground truth context.
                    </div>
                  )}
                </div>
              )}

              {activeInspectorTab === 'diffs' && (
                <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-4 shadow-soft space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-[#D8D5CE]">
                    <span className="text-xs font-mono font-semibold text-[#252525] uppercase tracking-wide">
                      Append-Only Unified Diff History ({diffHistory.length} edits)
                    </span>
                    {isLoadingDiffs && (
                      <span className="text-[10px] font-mono text-[#6F6D68]">Loading diffs...</span>
                    )}
                  </div>

                  {diffHistory.length > 0 ? (
                    <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1 font-mono text-xs">
                      {diffHistory.map((item) => (
                        <div key={item.diff_id} className="p-3 rounded bg-[#F8F7F3] border border-[#D8D5CE] space-y-1.5">
                          <div className="flex items-center justify-between text-[10px] text-[#6F6D68]">
                            <span className="font-semibold text-[#252525]">
                              Revision by <strong className="text-[#30302E]">{item.actor}</strong> ({item.change_type})
                            </span>
                            <span>{new Date(item.timestamp).toLocaleTimeString()}</span>
                          </div>
                          {item.notes && (
                            <div className="text-[10px] text-[#6F6D68] italic">Note: "{item.notes}"</div>
                          )}
                          <pre className="p-2 bg-[#FCFBF8] border border-[#D8D5CE] rounded text-[10px] whitespace-pre-wrap overflow-x-auto text-[#252525]">
                            {item.unified_diff}
                          </pre>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-6 text-center text-[#99958D] text-xs font-mono">
                      No revisions recorded yet. Claims currently match the initial AI-generated draft.
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg p-16 text-center space-y-3 shadow-soft font-mono">
              <div className="w-10 h-10 rounded-full bg-[#F8F7F3] border border-[#D8D5CE] flex items-center justify-center mx-auto text-base">
                ⚖️
              </div>
              <div className="text-xs font-semibold text-[#252525]">
                No Deliverable Selected for Review
              </div>
              <p className="text-[11px] text-[#6F6D68] max-w-sm mx-auto">
                Generate deliverable formats in the Transformation Studio or select an existing deliverable from the queue on the left.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
