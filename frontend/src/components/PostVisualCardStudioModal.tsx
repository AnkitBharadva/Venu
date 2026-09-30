import React, { useState, useEffect } from 'react';

export interface PostCardItem {
  card_id: string;
  title: string;
  post_text: string;
  sequence_index: number;
  sequence_total: number;
  sequence_label: string;
  preview_url: string;
  png_download_url: string;
  aspect_ratio?: string;
  theme?: string;
  font_family?: string;
  layout_preset?: string;
  brand_name?: string;
  classification?: string;
}

export interface PostCardStudioState {
  cardId: string;
  title: string;
  postText: string;
  deliverableType: string;
  aspectRatio: '16:9' | '1:1' | '4:3' | '9:16';
  theme: string;
  fontFamily: 'sans' | 'serif' | 'mono';
  layoutPreset: 'auto' | 'hero' | 'split' | 'technical' | 'minimal';
  brandName: string;
  classification: string;
  previewUrl: string;
  pngDownloadUrl: string;
  isLoading: boolean;
  isDownloadingPng: boolean;
  error: string | null;
  cards: PostCardItem[];
  activeCardIndex: number;
}

export const THEME_OPTIONS = [
  { id: 'cyber_dark', label: 'Cyber Dark', icon: '🌑', color: '#38bdf8', bg: '#0a0f1d' },
  { id: 'midnight_navy', label: 'Midnight Navy', icon: '🌌', color: '#60a5fa', bg: '#0b132b' },
  { id: 'terminal_green', label: 'Terminal Matrix', icon: '📟', color: '#22c55e', bg: '#05140b' },
  { id: 'sunset_amber', label: 'Sunset Amber', icon: '🌅', color: '#f59e0b', bg: '#1a1005' },
  { id: 'crimson_alert', label: 'Crimson Alert', icon: '🚨', color: '#ef4444', bg: '#1c0709' },
  { id: 'minimal_paper', label: 'Minimal Paper', icon: '📄', color: '#0f172a', bg: '#f8fafc' },
  { id: 'high_contrast', label: 'High Contrast', icon: '⚡', color: '#facc15', bg: '#000000' },
];

export const FONT_OPTIONS = [
  { id: 'sans', label: 'Modern Sans', sub: 'Inter UI' },
  { id: 'serif', label: 'Editorial Serif', sub: 'Merriweather' },
  { id: 'mono', label: 'Terminal Mono', sub: 'JetBrains' },
] as const;

export const LAYOUT_OPTIONS = [
  { id: 'auto', label: 'Auto Detect', desc: 'Adapts to content' },
  { id: 'hero', label: 'Hero Hook', desc: 'Prominent quote' },
  { id: 'split', label: 'Split Grid', desc: 'Takeaway matrix' },
  { id: 'technical', label: 'Terminal Box', desc: 'Command spec' },
  { id: 'minimal', label: 'Minimalist', desc: 'Clean editorial' },
] as const;

export const ASPECT_RATIOS: Array<{
  id: '16:9' | '1:1' | '4:3' | '9:16';
  label: string;
  dims: string;
  tip: string;
}> = [
  { id: '16:9', label: '16:9', dims: '1200x675', tip: 'Landscape (1200x675) • Best for X & LinkedIn feeds' },
  { id: '1:1', label: '1:1', dims: '1080x1080', tip: 'Square (1080x1080) • Best for carousels & Instagram' },
  { id: '4:3', label: '4:3', dims: '1200x900', tip: 'Memo (1200x900) • Best for executive briefings' },
  { id: '9:16', label: '9:16', dims: '1080x1920', tip: 'Story / Reel (1080x1920) • Best for vertical mobile' },
];

interface Props {
  studio: PostCardStudioState | null;
  onClose: () => void;
  onSelectCardIndex: (index: number) => void;
  onUpdateOptions: (updates: {
    ratio?: '16:9' | '1:1' | '4:3' | '9:16';
    theme?: string;
    fontFamily?: 'sans' | 'serif' | 'mono';
    layoutPreset?: 'auto' | 'hero' | 'split' | 'technical' | 'minimal';
    brandName?: string;
    classification?: string;
    text?: string;
    title?: string;
  }) => Promise<void>;
  onDownloadSinglePNG: () => Promise<void>;
  onDownloadAllPNGs: () => Promise<void>;
}

export const PostVisualCardStudioModal: React.FC<Props> = ({
  studio,
  onClose,
  onSelectCardIndex,
  onUpdateOptions,
  onDownloadSinglePNG,
  onDownloadAllPNGs,
}) => {
  const [showDrawer, setShowDrawer] = useState<boolean>(false);
  const [editTitle, setEditTitle] = useState<string>('');
  const [editText, setEditText] = useState<string>('');
  const [editBrand, setEditBrand] = useState<string>('');
  const [editClassification, setEditClassification] = useState<string>('');

  // Sync edit state when active card changes
  useEffect(() => {
    if (studio) {
      setEditTitle(studio.title || '');
      setEditText(studio.postText || '');
      setEditBrand(studio.brandName || 'AIZ INTELLIGENCE');
      setEditClassification(studio.classification || 'VERIFIED CLAIM');
    }
  }, [studio?.cardId, studio?.activeCardIndex]);

  if (!studio) return null;

  const currentTheme = THEME_OPTIONS.find((t) => t.id === studio.theme) || THEME_OPTIONS[0];

  const handleApplyDrawerEdits = () => {
    onUpdateOptions({
      title: editTitle,
      text: editText,
      brandName: editBrand,
      classification: editClassification,
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#090d16]/90 backdrop-blur-md flex items-center justify-center p-2 sm:p-4">
      <div className="bg-[#0f172a] border border-[#38bdf8]/40 rounded-2xl w-full max-w-6xl h-[95vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in duration-200">
        {/* Top Control Bar */}
        <div className="px-4 py-2.5 bg-[#090d16] border-b border-[#1e293b] flex flex-wrap items-center justify-between gap-2.5 text-xs font-mono text-white">
          {/* Header Title */}
          <div className="flex items-center space-x-2.5">
            <div
              className="w-3 h-3 rounded-full shadow-[0_0_12px]"
              style={{ backgroundColor: currentTheme.color, boxShadow: `0 0 12px ${currentTheme.color}` }}
            />
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold tracking-wider text-sm" style={{ color: currentTheme.color }}>
                  POST VISUAL CARD STUDIO
                </span>
                <span className="hidden sm:inline-block px-2 py-0.5 rounded bg-[#1e293b] text-[#94a3b8] border border-[#334155] text-[10px]">
                  Air-Gapped &bull; 100% Provenance
                </span>
              </div>
            </div>
          </div>

          {/* Controls: Ratios, Themes, Fonts, Layout, Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Aspect Ratio Selector */}
            <div className="flex items-center rounded-lg border border-[#38bdf8]/30 bg-[#1e293b]/70 p-0.5 text-[11px]">
              {ASPECT_RATIOS.map((r) => (
                <button
                  key={r.id}
                  onClick={() => onUpdateOptions({ ratio: r.id })}
                  className={`px-2 py-0.5 rounded font-medium transition cursor-pointer ${
                    studio.aspectRatio === r.id
                      ? 'bg-[#38bdf8] text-[#090d16] font-bold shadow-xs'
                      : 'text-[#94a3b8] hover:text-white'
                  }`}
                  title={r.tip}
                >
                  {r.label}
                </button>
              ))}
            </div>

            {/* Theme Selector Dropdown */}
            <div className="relative inline-block">
              <select
                value={studio.theme}
                onChange={(e) => onUpdateOptions({ theme: e.target.value })}
                className="bg-[#1e293b] hover:bg-[#27354a] border border-[#38bdf8]/30 text-[#e2e8f0] text-[11px] rounded px-2.5 py-1 cursor-pointer focus:outline-hidden focus:border-[#38bdf8] transition"
                title="Select Visual Theme Palette"
              >
                {THEME_OPTIONS.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.icon} {t.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Typography (Font) Selector */}
            <div className="relative inline-block">
              <select
                value={studio.fontFamily}
                onChange={(e) => onUpdateOptions({ fontFamily: e.target.value as any })}
                className="bg-[#1e293b] hover:bg-[#27354a] border border-[#38bdf8]/30 text-[#e2e8f0] text-[11px] rounded px-2 py-1 cursor-pointer focus:outline-hidden focus:border-[#38bdf8] transition"
                title="Select Typography Style"
              >
                {FONT_OPTIONS.map((f) => (
                  <option key={f.id} value={f.id}>
                    🔤 {f.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Layout Preset Selector */}
            <div className="relative inline-block">
              <select
                value={studio.layoutPreset}
                onChange={(e) => onUpdateOptions({ layoutPreset: e.target.value as any })}
                className="bg-[#1e293b] hover:bg-[#27354a] border border-[#38bdf8]/30 text-[#e2e8f0] text-[11px] rounded px-2 py-1 cursor-pointer focus:outline-hidden focus:border-[#38bdf8] transition"
                title="Select Card Layout Blueprint"
              >
                {LAYOUT_OPTIONS.map((l) => (
                  <option key={l.id} value={l.id}>
                    📐 {l.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Style & Content Drawer Button */}
            <button
              onClick={() => setShowDrawer(!showDrawer)}
              className={`px-2.5 py-1 rounded border text-[11px] transition flex items-center space-x-1 cursor-pointer ${
                showDrawer
                  ? 'bg-[#38bdf8] text-[#090d16] font-bold border-[#38bdf8]'
                  : 'bg-[#1e293b] hover:bg-[#334155] border-[#38bdf8]/30 text-[#e2e8f0]'
              }`}
              title="Customize Brand, Classification, Headline, and Text"
            >
              <span>🎨 {showDrawer ? 'Hide Controls' : 'Edit & Brand'}</span>
            </button>

            {/* PNG Download Button */}
            <button
              onClick={onDownloadSinglePNG}
              disabled={studio.isDownloadingPng || studio.isLoading}
              className="px-3 py-1 rounded bg-[#38bdf8] hover:bg-[#0ea5e9] disabled:bg-[#475569] text-[#090d16] font-bold text-[11px] transition flex items-center space-x-1.5 cursor-pointer shadow-[0_0_12px_rgba(56,189,248,0.3)]"
              title="Download pixel-perfect 2x retina PNG rendered by local Chromium"
            >
              {studio.isDownloadingPng ? (
                <>
                  <div className="w-3 h-3 border-2 border-[#090d16] border-t-transparent rounded-full animate-spin" />
                  <span>Rendering...</span>
                </>
              ) : (
                <span>📸 Download PNG</span>
              )}
            </button>

            {/* External Preview Link */}
            {studio.previewUrl && (
              <a
                href={studio.previewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-2 py-1 rounded bg-[#1e293b] hover:bg-[#334155] border border-[#38bdf8]/30 text-[#38bdf8] text-[11px] transition flex items-center"
                title="Open in new window"
              >
                <span>↗</span>
              </a>
            )}

            {/* Close Modal Button */}
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-lg bg-[#1e293b] hover:bg-[#ef4444] text-white flex items-center justify-center font-bold text-sm transition cursor-pointer"
              title="Close modal"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Thread Sequence Navigation Strip */}
        {studio.cards && studio.cards.length > 1 && (
          <div className="px-4 py-2 bg-[#090d16] border-b border-[#1e293b] flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center space-x-2">
              <span className="text-[11px] text-[#38bdf8] uppercase tracking-wider font-semibold">Sequence:</span>
              <div className="flex items-center gap-1.5 overflow-x-auto max-w-[620px] py-0.5">
                {studio.cards.map((c, i) => (
                  <button
                    key={c.card_id || i}
                    onClick={() => onSelectCardIndex(i)}
                    className={`px-3 py-1 rounded text-xs transition cursor-pointer flex items-center space-x-1.5 shrink-0 ${
                      studio.activeCardIndex === i
                        ? 'bg-[#38bdf8] text-[#090d16] font-bold shadow-[0_0_10px_rgba(56,189,248,0.4)]'
                        : 'bg-[#1e293b] text-[#94a3b8] hover:text-white hover:bg-[#334155]'
                    }`}
                  >
                    <span>{c.sequence_label || `Card ${i + 1}/${studio.cards.length}`}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center space-x-2 shrink-0">
              <button
                onClick={() => onSelectCardIndex(Math.max(0, studio.activeCardIndex - 1))}
                disabled={studio.activeCardIndex === 0}
                className="px-2.5 py-1 rounded bg-[#1e293b] hover:bg-[#334155] disabled:opacity-30 text-[#e2e8f0] text-xs transition cursor-pointer"
              >
                &larr; Prev
              </button>
              <span className="text-[#38bdf8] text-xs font-bold">
                {studio.activeCardIndex + 1} / {studio.cards.length}
              </span>
              <button
                onClick={() => onSelectCardIndex(Math.min(studio.cards.length - 1, studio.activeCardIndex + 1))}
                disabled={studio.activeCardIndex === studio.cards.length - 1}
                className="px-2.5 py-1 rounded bg-[#1e293b] hover:bg-[#334155] disabled:opacity-30 text-[#e2e8f0] text-xs transition cursor-pointer"
              >
                Next &rarr;
              </button>

              <button
                onClick={onDownloadAllPNGs}
                disabled={studio.isDownloadingPng}
                className="ml-2 px-3 py-1 rounded bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600 text-white font-bold text-xs transition flex items-center space-x-1 cursor-pointer shadow-sm"
                title="Download all cards in this sequence as individual 2x PNGs"
              >
                <span>📦 Download All ({studio.cards.length} PNGs)</span>
              </button>
            </div>
          </div>
        )}

        {/* Collapsible Style, Branding & Content Drawer */}
        {showDrawer && (
          <div className="p-4 bg-[#090d16]/98 border-b border-[#1e293b] text-xs font-mono space-y-3 shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-[#38bdf8] font-bold flex items-center space-x-1.5">
                <span>🎨 Card Content &amp; Custom Branding</span>
              </span>
              <span className="text-[10px] text-[#94a3b8]">
                Changes immediately re-render with active palette &amp; layout
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              {/* Brand Name Input */}
              <div className="md:col-span-1">
                <label className="block text-[10px] text-[#94a3b8] mb-1">Brand / Org Name</label>
                <input
                  type="text"
                  value={editBrand}
                  onChange={(e) => setEditBrand(e.target.value)}
                  placeholder="e.g. AIZ INTELLIGENCE"
                  className="w-full bg-[#1e293b] border border-[#38bdf8]/30 rounded px-2.5 py-1.5 text-xs text-white focus:border-[#38bdf8] focus:outline-hidden"
                />
              </div>

              {/* Classification Tag Input */}
              <div className="md:col-span-1">
                <label className="block text-[10px] text-[#94a3b8] mb-1">Classification / Tag</label>
                <input
                  type="text"
                  value={editClassification}
                  onChange={(e) => setEditClassification(e.target.value)}
                  placeholder="e.g. VERIFIED CLAIM"
                  className="w-full bg-[#1e293b] border border-[#38bdf8]/30 rounded px-2.5 py-1.5 text-xs text-white focus:border-[#38bdf8] focus:outline-hidden"
                />
              </div>

              {/* Headline Input */}
              <div className="md:col-span-2">
                <label className="block text-[10px] text-[#94a3b8] mb-1">Card Headline / Hook</label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  placeholder="Card Headline"
                  className="w-full bg-[#1e293b] border border-[#38bdf8]/30 rounded px-2.5 py-1.5 text-xs text-white focus:border-[#38bdf8] focus:outline-hidden"
                />
              </div>

              {/* Post Textarea */}
              <div className="md:col-span-4">
                <label className="block text-[10px] text-[#94a3b8] mb-1">
                  Post Content (Statements, Takeaways, Bullets)
                </label>
                <textarea
                  rows={3}
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  placeholder="The exact post text to display on the card"
                  className="w-full bg-[#1e293b] border border-[#38bdf8]/30 rounded px-2.5 py-1.5 text-xs text-white focus:border-[#38bdf8] focus:outline-hidden resize-y"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-1">
              <button
                onClick={handleApplyDrawerEdits}
                disabled={studio.isLoading}
                className="px-4 py-1.5 rounded bg-[#38bdf8] hover:bg-[#0ea5e9] disabled:bg-[#475569] text-[#090d16] font-bold text-xs transition cursor-pointer flex items-center space-x-1.5"
              >
                <span>⚡ Re-render Card with Edits</span>
              </button>
            </div>
          </div>
        )}

        {/* Live Preview Container */}
        <div className="flex-1 w-full bg-[#090d16] overflow-hidden relative flex items-center justify-center p-2 sm:p-4">
          {studio.isLoading && (
            <div className="absolute inset-0 z-10 bg-[#090d16]/80 backdrop-blur-xs flex flex-col items-center justify-center space-y-3 text-[#38bdf8] font-mono text-xs">
              <div className="w-9 h-9 border-3 border-[#38bdf8] border-t-transparent rounded-full animate-spin" />
              <span>Compiling visual card with {currentTheme.label} theme...</span>
            </div>
          )}

          {studio.error ? (
            <div className="p-6 text-center text-[#ef4444] font-mono text-xs max-w-md bg-[#1e293b] rounded-xl border border-[#ef4444]/40">
              <p className="font-bold mb-2">Rendering Error</p>
              <p>{studio.error}</p>
            </div>
          ) : studio.previewUrl ? (
            <iframe
              key={`${studio.cardId}-${studio.aspectRatio}-${studio.theme}-${studio.fontFamily}-${studio.layoutPreset}`}
              src={studio.previewUrl}
              title="Post Visual Card Preview"
              className="w-full h-full border-0 rounded-xl"
            />
          ) : null}
        </div>
      </div>
    </div>
  );
};
