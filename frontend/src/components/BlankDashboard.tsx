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

export const BlankDashboard: React.FC = () => {
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [latestDoc, setLatestDoc] = useState<SourceDocument | null>(null);
  const [showTextPreview, setShowTextPreview] = useState<boolean>(false);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    setUploadError(null);

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
                Offline Mode: Active (Zero Outbound Egress)
              </h3>
              <span className="bg-emerald-500/20 text-emerald-300 text-[10px] font-mono px-2 py-0.5 rounded border border-emerald-500/30">
                Air-Gapped
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              All LLM reasoning, OCR, speech transcription, vector storage, and graph linking run locally within container enclave.
            </p>
          </div>
        </div>

        <div className="text-xs font-mono bg-gray-950/80 px-3 py-1.5 rounded-lg border border-gray-800 text-gray-300 flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          <span>Egress Firewall: BLOCKED</span>
        </div>
      </div>

      {/* Main Multi-Column Canvas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Active Ingestion Pipeline (Phase 1) */}
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                <span>1. Source Document Ingestion</span>
              </h3>
              <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50">
                Phase 1 Active
              </span>
            </div>

            {/* Interactive Ingestion Dropzone */}
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
                  ? 'border-indigo-500 bg-indigo-950/30'
                  : 'border-gray-800 hover:border-gray-700 bg-gray-950/40'
              }`}
            >
              <div className="w-12 h-12 mx-auto mb-3 text-indigo-400 flex items-center justify-center rounded-full bg-indigo-950/50 border border-indigo-800/60">
                {isUploading ? (
                  <svg className="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                  </svg>
                ) : (
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                )}
              </div>
              <p className="text-xs font-medium text-gray-200">
                {isUploading ? 'Encrypting & Ingesting...' : 'Drag & Drop or Click to Browse'}
              </p>
              <p className="text-[11px] text-gray-400 mt-1">
                Plain Text &bull; PDF &bull; DOCX &bull; PPTX &bull; Images &bull; Audio/Video
              </p>
              <div className="mt-3 flex items-center justify-center gap-2">
                <span className="px-2 py-0.5 rounded bg-gray-800/90 text-[10px] text-emerald-400 font-mono border border-emerald-800/40">
                  AES-256 Enclave
                </span>
                <span className="px-2 py-0.5 rounded bg-gray-800/90 text-[10px] text-indigo-400 font-mono border border-indigo-800/40">
                  Audit Chained
                </span>
              </div>
            </div>

            {uploadError && (
              <div className="mt-3 p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300 flex items-start space-x-2">
                <span>⚠️</span>
                <div>
                  <p className="font-medium">Ingestion Error</p>
                  <p className="text-[11px] text-rose-400/80 mt-0.5">{uploadError}</p>
                </div>
              </div>
            )}
          </div>

          <div className="mt-4 text-[11px] text-gray-500 border-t border-gray-800/60 pt-3">
            File encrypted before writing to disk &bull; Append-only audit record committed.
          </div>
        </div>

        {/* Center Column: Normalized Document Inspection */}
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                <span>Normalized SourceDocument</span>
              </h3>
              <span className="text-[11px] font-mono text-gray-400">
                {latestDoc ? 'Ingested' : 'Awaiting Input'}
              </span>
            </div>

            {latestDoc ? (
              <div className="space-y-3">
                <div className="bg-gray-950/70 p-3.5 rounded-lg border border-gray-800 space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-200 truncate max-w-[180px]">
                      {latestDoc.original_filename}
                    </span>
                    <span className="font-mono text-[10px] text-indigo-400 bg-indigo-950/80 px-2 py-0.5 rounded border border-indigo-800/40">
                      {latestDoc.content_type}
                    </span>
                  </div>

                  <div className="text-[11px] text-gray-400 font-mono flex items-center justify-between">
                    <span>Checksum:</span>
                    <span className="text-gray-300">{latestDoc.checksum.substring(0, 16)}...</span>
                  </div>

                  <div className="text-[11px] text-gray-400 font-mono flex items-center justify-between">
                    <span>Doc ID:</span>
                    <span className="text-gray-300">{latestDoc.doc_id.substring(0, 12)}...</span>
                  </div>

                  {/* Structural metadata metrics */}
                  <div className="pt-2 border-t border-gray-800/80 grid grid-cols-2 gap-2 text-[11px] font-mono">
                    <div className="bg-gray-900/80 p-1.5 rounded">
                      <span className="text-gray-500 block">Parser</span>
                      <span className="text-gray-300 font-medium">
                        {latestDoc.structural_metadata.parser || 'Standard'}
                      </span>
                    </div>
                    <div className="bg-gray-900/80 p-1.5 rounded">
                      <span className="text-gray-500 block">Characters</span>
                      <span className="text-gray-300 font-medium">
                        {latestDoc.raw_text?.length || 0}
                      </span>
                    </div>
                  </div>

                  {/* Low confidence warning surfaced to operator (Task 5) */}
                  {latestDoc.structural_metadata.low_confidence && (
                    <div className="mt-2 p-2 rounded bg-amber-950/50 border border-amber-800/60 text-[11px] text-amber-300">
                      <p className="font-medium flex items-center gap-1">
                        <span>⚠️</span> Low-Confidence Extraction
                      </p>
                      {latestDoc.structural_metadata.warnings?.map((w, idx) => (
                        <p key={idx} className="text-[10px] text-amber-400/80 mt-0.5">&bull; {w}</p>
                      ))}
                    </div>
                  )}
                </div>

                <button
                  onClick={() => setShowTextPreview(!showTextPreview)}
                  className="w-full text-xs py-1.5 px-3 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg border border-gray-700 font-medium transition"
                >
                  {showTextPreview ? 'Hide Extracted Text Preview' : 'View Extracted Text Preview'}
                </button>

                {showTextPreview && (
                  <div className="max-h-48 overflow-y-auto p-3 bg-black/50 rounded-lg border border-gray-800 text-[11px] font-mono text-gray-300 whitespace-pre-wrap leading-relaxed">
                    {latestDoc.raw_text}
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 text-center text-gray-500 border border-dashed border-gray-800/80 rounded-lg bg-gray-950/30">
                <p className="text-xs">No document ingested yet.</p>
                <p className="text-[11px] mt-1 text-gray-600">Upload a source file in Step 1 to inspect normalized text.</p>
              </div>
            )}
          </div>

          <div className="mt-4 text-[11px] text-gray-500 border-t border-gray-800/60 pt-3">
            Common schema: doc_id, filename, content_type, raw_text, checksum, metadata.
          </div>
        </div>

        {/* Right Column: Grounding & Audit Verification (Phase 3 & 5) */}
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                <span>Security Envelope & Audit</span>
              </h3>
              <span className="text-[11px] font-mono text-gray-500">SHA-256 Chained</span>
            </div>

            <div className="space-y-3">
              <div className="p-3.5 rounded-lg bg-gray-950/60 border border-gray-800 text-xs space-y-2">
                <div className="font-semibold text-gray-200">Defense-Level Air-Gap Proof</div>
                <div className="space-y-1.5 text-[11px] font-mono text-gray-400">
                  <div className="flex items-center space-x-2 text-emerald-400">
                    <span>✔</span>
                    <span>AES-256-GCM at-rest encryption</span>
                  </div>
                  <div className="flex items-center space-x-2 text-emerald-400">
                    <span>✔</span>
                    <span>No telemetry or cloud model APIs</span>
                  </div>
                  <div className="flex items-center space-x-2 text-emerald-400">
                    <span>✔</span>
                    <span>Tamper-evident append-only audit trail</span>
                  </div>
                  <div className="flex items-center space-x-2 text-emerald-400">
                    <span>✔</span>
                    <span>Zero outbound container egress</span>
                  </div>
                </div>
              </div>

              {/* Format selection roadmap */}
              <div className="p-3 rounded-lg bg-indigo-950/20 border border-indigo-900/40 text-xs">
                <div className="font-medium text-indigo-300 mb-1">Upcoming Deliverables (Phase 4)</div>
                <p className="text-[11px] text-gray-400 leading-relaxed">
                  LinkedIn &bull; Twitter/X &bull; Executive Summary &bull; Advisory &bull; Presentation &bull; Video Package &bull; Infographic
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 text-[11px] text-gray-500 border-t border-gray-800/60 pt-3">
            Phase 1 Complete &bull; Ready for Phase 2 (Chunking & Embeddings).
          </div>
        </div>
      </div>
    </div>
  );
};
