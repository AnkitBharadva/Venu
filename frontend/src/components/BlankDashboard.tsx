import React from 'react';

export const BlankDashboard: React.FC = () => {
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

      {/* Main Skeleton Canvas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Ingestion Pipeline Stub (Phase 1) */}
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                <span>1. Source Document Ingestion</span>
              </h3>
              <span className="text-[11px] font-mono text-gray-500">Phase 1 Target</span>
            </div>

            {/* Ingestion Dropzone Stub */}
            <div className="border-2 border-dashed border-gray-800 hover:border-gray-700 rounded-xl p-8 text-center transition bg-gray-950/40">
              <div className="w-12 h-12 mx-auto mb-3 text-gray-600 flex items-center justify-center rounded-full bg-gray-900 border border-gray-800">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>
              <p className="text-xs font-medium text-gray-300">Drag & Drop Source Files</p>
              <p className="text-[11px] text-gray-500 mt-1">
                PDF &bull; DOCX &bull; PPTX &bull; Scanned Images &bull; Audio/Video
              </p>
              <div className="mt-4 inline-flex items-center px-3 py-1 rounded bg-gray-800/80 border border-gray-700/60 text-[11px] text-gray-400">
                <span>Encrypted At-Rest (AES-256)</span>
              </div>
            </div>
          </div>

          <div className="mt-6 text-[11px] text-gray-500 border-t border-gray-800/60 pt-3">
            Append-only audit row triggered on every upload.
          </div>
        </div>

        {/* Center Column: Deliverable Format Selection (Phase 4) */}
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                <span>2. Deliverable Adapters</span>
              </h3>
              <span className="text-[11px] font-mono text-gray-500">7 Formats</span>
            </div>

            <p className="text-xs text-gray-400 mb-3">
              Select transformation outputs with 100% claim-to-chunk provenance:
            </p>

            <div className="space-y-2">
              {[
                { name: 'LinkedIn Post', desc: 'Hook + Body + CTA + Hashtags', badge: 'Professional' },
                { name: 'Twitter/X Thread', desc: 'Char-limited multi-post sequence', badge: 'Viral' },
                { name: 'Executive Summary', desc: '150–300 words briefing note', badge: 'Briefing' },
                { name: 'Advisory Note', desc: 'Mandatory human approval checkpoint', badge: 'Safety' },
                { name: 'Slide Presentation', desc: 'Structured titles & bullet points', badge: 'Deck' },
                { name: 'Video Package', desc: 'Script, storyboard beats & SRT text', badge: 'Media' },
                { name: 'Infographic Brief', desc: 'Hierarchy & visual layout spec', badge: 'Visual' },
              ].map((fmt, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-gray-950/40 border border-gray-800/60 text-xs"
                >
                  <div>
                    <span className="text-gray-200 font-medium">{fmt.name}</span>
                    <p className="text-[10px] text-gray-500">{fmt.desc}</p>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-400 font-mono">
                    {fmt.badge}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 text-[11px] text-gray-500 border-t border-gray-800/60 pt-3">
            Multi-select supported &bull; Shared grounding context.
          </div>
        </div>

        {/* Right Column: Grounding & Audit Verification (Phase 3 & 5) */}
        <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800 mb-4">
              <h3 className="text-sm font-semibold text-gray-200 flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                <span>3. Grounding & Audit Trail</span>
              </h3>
              <span className="text-[11px] font-mono text-gray-500">Traceability</span>
            </div>

            {/* Traceability preview placeholder */}
            <div className="p-4 rounded-lg bg-gray-950/60 border border-gray-800 space-y-3">
              <div className="text-xs font-semibold text-gray-300">Live Provenance Engine</div>
              <p className="text-xs text-gray-400 leading-relaxed">
                Hovering any sentence in generated outputs displays the exact underlying source chunk, character span, and timestamp via{' '}
                <code className="bg-gray-800 text-indigo-400 px-1 py-0.5 rounded font-mono text-[10px]">/trace</code>.
              </p>

              <div className="p-3 bg-gray-900/90 rounded border border-gray-800/80 font-mono text-[11px] text-gray-400 space-y-1">
                <div className="text-emerald-400 font-semibold">&gt; Grounding Protocol:</div>
                <div>&bull; Qdrant Vector Search: Cosine top-k</div>
                <div>&bull; FalkorDB Graph: Entity path check</div>
                <div>&bull; Cryptographic Audit: SHA-256 chain</div>
              </div>
            </div>

            {/* Approval Workflow preview */}
            <div className="mt-4 p-3 rounded-lg bg-indigo-950/20 border border-indigo-900/40 text-xs">
              <div className="font-medium text-indigo-300 mb-1">Human-in-the-Loop Review</div>
              <p className="text-[11px] text-gray-400 leading-normal">
                Outputs default to <code className="text-amber-300">draft</code>. Export is cryptographically locked until approved by a reviewer.
              </p>
            </div>
          </div>

          <div className="mt-6 text-[11px] text-gray-500 border-t border-gray-800/60 pt-3">
            Phase 0 Skeleton operational &bull; Ready for Phase 1.
          </div>
        </div>
      </div>
    </div>
  );
};
