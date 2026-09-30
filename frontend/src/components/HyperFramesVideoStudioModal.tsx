import React, { useState, useEffect } from 'react';

export interface VideoChapterItem {
  chapter_index: number;
  label: string;
  duration: number;
  text_snippet: string;
}

export interface VideoStudioState {
  videoId: string;
  title: string;
  postText: string;
  deliverableType: string;
  aspectRatio: '16:9' | '9:16' | '1:1' | '4:3';
  theme: string;
  fontFamily: 'sans' | 'serif' | 'mono';
  motionStyle: 'kinetic' | 'tactical' | 'editorial' | 'minimal';
  brandName: string;
  classification: string;
  durationSeconds: number;
  previewUrl: string;
  mp4ExportUrl: string;
  isLoading: boolean;
  isExportingMp4: boolean;
  error: string | null;
  chapters?: VideoChapterItem[];
  activeChapterIndex?: number;
  isThreadSequence?: boolean;
}

export const VIDEO_THEME_OPTIONS = [
  { id: 'cyber_dark', label: 'Cyber Dark', icon: '🌑', color: '#38bdf8', bg: '#090d16' },
  { id: 'midnight_navy', label: 'Midnight Navy', icon: '🌌', color: '#60a5fa', bg: '#0b132b' },
  { id: 'terminal_green', label: 'Terminal Matrix', icon: '📟', color: '#22c55e', bg: '#05140b' },
  { id: 'sunset_amber', label: 'Sunset Amber', icon: '🌅', color: '#f59e0b', bg: '#1a1005' },
  { id: 'crimson_alert', label: 'Crimson Alert', icon: '🚨', color: '#ef4444', bg: '#1c0709' },
  { id: 'minimal_paper', label: 'Minimal Paper', icon: '📄', color: '#0f172a', bg: '#f8fafc' },
  { id: 'high_contrast', label: 'High Contrast', icon: '⚡', color: '#facc15', bg: '#000000' },
];

export const MOTION_STYLE_OPTIONS = [
  { id: 'kinetic', label: 'Kinetic Dynamic', desc: 'Punchy scale & staggered reveals' },
  { id: 'tactical', label: 'Tactical HUD', desc: 'Terminal telemetry & scanline pulses' },
  { id: 'editorial', label: 'Editorial Smooth', desc: 'Fluid eases & elegant slide-ins' },
  { id: 'minimal', label: 'Minimal Precision', desc: 'Subtle clean opacity shifts' },
] as const;

export const VIDEO_FONT_OPTIONS = [
  { id: 'sans', label: 'Modern Sans', sub: 'Inter UI' },
  { id: 'serif', label: 'Editorial Serif', sub: 'Merriweather' },
  { id: 'mono', label: 'Terminal Mono', sub: 'JetBrains' },
] as const;

export const VIDEO_ASPECT_RATIOS: Array<{
  id: '16:9' | '9:16' | '1:1' | '4:3';
  label: string;
  dims: string;
  tip: string;
}> = [
  { id: '16:9', label: '16:9', dims: '1920x1080', tip: 'Landscape (1920x1080) • Best for X & LinkedIn feeds / YouTube' },
  { id: '9:16', label: '9:16', dims: '1080x1920', tip: 'Vertical Reel (1080x1920) • Best for TikTok / Reels / Shorts' },
  { id: '1:1', label: '1:1', dims: '1080x1080', tip: 'Square (1080x1080) • Best for Instagram & carousel embeds' },
  { id: '4:3', label: '4:3', dims: '1440x1080', tip: 'Presentation / Briefing (1440x1080) • Tactical command view' },
];

interface Props {
  studio: VideoStudioState | null;
  onClose: () => void;
  onUpdateOptions: (updates: {
    ratio?: '16:9' | '9:16' | '1:1' | '4:3';
    theme?: string;
    fontFamily?: 'sans' | 'serif' | 'mono';
    motionStyle?: 'kinetic' | 'tactical' | 'editorial' | 'minimal';
    brandName?: string;
    classification?: string;
    durationSeconds?: number;
    text?: string;
    title?: string;
  }) => Promise<void>;
  onExportMP4: () => Promise<void>;
}

export const HyperFramesVideoStudioModal: React.FC<Props> = ({
  studio,
  onClose,
  onUpdateOptions,
  onExportMP4,
}) => {
  const [showDrawer, setShowDrawer] = useState<boolean>(false);
  const [editTitle, setEditTitle] = useState<string>('');
  const [editText, setEditText] = useState<string>('');
  const [editBrand, setEditBrand] = useState<string>('');
  const [editClassification, setEditClassification] = useState<string>('');
  const [editDuration, setEditDuration] = useState<number>(7);

  // Sync state when active video changes
  useEffect(() => {
    if (studio) {
      setEditTitle(studio.title || '');
      setEditText(studio.postText || '');
      setEditBrand(studio.brandName || 'AIZ INTELLIGENCE');
      setEditClassification(studio.classification || (studio.isThreadSequence ? 'TACTICAL THREAD' : 'VERIFIED CLAIM'));
      setEditDuration(studio.durationSeconds || (studio.isThreadSequence ? 5 : 7));
    }
  }, [studio?.videoId]);

  if (!studio) return null;

  const currentTheme = VIDEO_THEME_OPTIONS.find((t) => t.id === studio.theme) || VIDEO_THEME_OPTIONS[0];

  const handleApplyDrawerEdits = () => {
    onUpdateOptions({
      title: editTitle,
      text: editText,
      brandName: editBrand,
      classification: editClassification,
      durationSeconds: editDuration,
    });
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#090d16]/90 backdrop-blur-md flex items-center justify-center p-2 sm:p-4">
      <div className="bg-[#0f172a] border border-[#38bdf8]/40 rounded-2xl w-full max-w-6xl h-[95vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in duration-200">
        {/* Top Control Bar */}
        <div className="px-4 py-2.5 bg-[#090d16] border-b border-[#1e293b] flex flex-wrap items-center justify-between gap-2.5 text-xs font-mono text-white">
          {/* Header Title & Status */}
          <div className="flex items-center space-x-2.5">
            <div
              className="w-3 h-3 rounded-full shadow-[0_0_12px]"
              style={{ backgroundColor: currentTheme.color, boxShadow: `0 0 12px ${currentTheme.color}` }}
            />
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold tracking-wider text-sm" style={{ color: currentTheme.color }}>
                  HYPERFRAMES VIDEO STUDIO
                </span>
                <span className="hidden sm:inline-block px-2 py-0.5 rounded bg-[#1e293b] text-[#94a3b8] border border-[#334155] text-[10px]">
                  Seekable GSAP &bull; H.264 Playwright
                </span>
                {studio.isThreadSequence && (
                  <span className="px-2 py-0.5 rounded bg-[#38bdf8]/20 text-[#38bdf8] border border-[#38bdf8]/40 text-[10px] font-bold">
                    Multi-Post Thread ({studio.chapters?.length || 4} Scenes)
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Controls: Ratios, Themes, Motion, Fonts, MP4 Export, Close */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Aspect Ratio Selector */}
            <div className="flex items-center rounded-lg border border-[#38bdf8]/30 bg-[#1e293b]/70 p-0.5 text-[11px]">
              {VIDEO_ASPECT_RATIOS.map((r) => (
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
                {VIDEO_THEME_OPTIONS.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.icon} {t.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Motion Style Selector */}
            <div className="relative inline-block">
              <select
                value={studio.motionStyle}
                onChange={(e) => onUpdateOptions({ motionStyle: e.target.value as any })}
                className="bg-[#1e293b] hover:bg-[#27354a] border border-[#38bdf8]/30 text-[#e2e8f0] text-[11px] rounded px-2.5 py-1 cursor-pointer focus:outline-hidden focus:border-[#38bdf8] transition"
                title="Select Motion Style Animation Dynamics"
              >
                {MOTION_STYLE_OPTIONS.map((m) => (
                  <option key={m.id} value={m.id}>
                    ⚡ {m.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Typography Selector */}
            <div className="relative inline-block">
              <select
                value={studio.fontFamily}
                onChange={(e) => onUpdateOptions({ fontFamily: e.target.value as any })}
                className="bg-[#1e293b] hover:bg-[#27354a] border border-[#38bdf8]/30 text-[#e2e8f0] text-[11px] rounded px-2 py-1 cursor-pointer focus:outline-hidden focus:border-[#38bdf8] transition"
                title="Select Typography Style"
              >
                {VIDEO_FONT_OPTIONS.map((f) => (
                  <option key={f.id} value={f.id}>
                    🔤 {f.label}
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

            {/* MP4 Video Export Button */}
            <button
              onClick={onExportMP4}
              disabled={studio.isExportingMp4 || studio.isLoading}
              className="px-3 py-1 rounded bg-[#38bdf8] hover:bg-[#0ea5e9] disabled:bg-[#475569] text-[#090d16] font-bold text-[11px] transition flex items-center space-x-1.5 cursor-pointer shadow-[0_0_12px_rgba(56,189,248,0.3)]"
              title="Render and download high-definition H.264 MP4 video file using Playwright & local FFmpeg"
            >
              {studio.isExportingMp4 ? (
                <>
                  <div className="w-3 h-3 border-2 border-[#090d16] border-t-transparent rounded-full animate-spin" />
                  <span>Encoding MP4...</span>
                </>
              ) : (
                <span>🎥 Export MP4</span>
              )}
            </button>

            {/* External Preview Link */}
            {studio.previewUrl && (
              <a
                href={studio.previewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-2 py-1 rounded bg-[#1e293b] hover:bg-[#334155] border border-[#38bdf8]/30 text-[#38bdf8] text-[11px] transition flex items-center"
                title="Open in new window / full screen"
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

        {/* Thread Sequence Chapters Strip */}
        {studio.isThreadSequence && studio.chapters && studio.chapters.length > 0 && (
          <div className="px-4 py-2 bg-[#090d16] border-b border-[#1e293b] flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center space-x-2">
              <span className="text-[11px] text-[#38bdf8] uppercase tracking-wider font-semibold">Video Chapters:</span>
              <div className="flex items-center gap-1.5 overflow-x-auto max-w-[700px] py-0.5">
                {studio.chapters.map((ch, i) => (
                  <div
                    key={ch.chapter_index || i}
                    className="px-2.5 py-1 rounded text-xs bg-[#1e293b] text-[#94a3b8] border border-[#334155] flex items-center space-x-1.5 shrink-0"
                  >
                    <span className="text-[#38bdf8] font-bold">#{ch.chapter_index}</span>
                    <span className="truncate max-w-[150px]">{ch.label}</span>
                    <span className="text-[10px] text-[#64748b]">({ch.duration}s)</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="text-[11px] text-[#94a3b8]">
              Total Video Duration:{' '}
              <span className="text-[#38bdf8] font-bold">
                {studio.durationSeconds ? `${studio.durationSeconds.toFixed(1)}s` : 'Multi-Scene'}
              </span>
            </div>
          </div>
        )}

        {/* Collapsible Style, Branding & Content Drawer */}
        {showDrawer && (
          <div className="p-4 bg-[#090d16]/98 border-b border-[#1e293b] text-xs font-mono space-y-3 shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-[#38bdf8] font-bold flex items-center space-x-1.5">
                <span>🎨 HyperFrames Motion &amp; Brand Settings</span>
              </span>
              <span className="text-[10px] text-[#94a3b8]">
                Changes immediately recompile the GSAP motion timeline
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              {/* Brand Name Input */}
              <div className="md:col-span-1">
                <label className="block text-[10px] text-[#94a3b8] mb-1">Brand / Studio Name</label>
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
                  placeholder="e.g. TACTICAL THREAD"
                  className="w-full bg-[#1e293b] border border-[#38bdf8]/30 rounded px-2.5 py-1.5 text-xs text-white focus:border-[#38bdf8] focus:outline-hidden"
                />
              </div>

              {/* Video Title / Hook Input */}
              <div className="md:col-span-1">
                <label className="block text-[10px] text-[#94a3b8] mb-1">Video Headline / Hook</label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  placeholder="Headline Hook"
                  className="w-full bg-[#1e293b] border border-[#38bdf8]/30 rounded px-2.5 py-1.5 text-xs text-white focus:border-[#38bdf8] focus:outline-hidden"
                />
              </div>

              {/* Scene / Post Duration */}
              <div className="md:col-span-1">
                <label className="block text-[10px] text-[#94a3b8] mb-1">
                  {studio.isThreadSequence ? 'Seconds per Chapter' : 'Video Duration (seconds)'}
                </label>
                <input
                  type="number"
                  min={3}
                  max={20}
                  step={0.5}
                  value={editDuration}
                  onChange={(e) => setEditDuration(parseFloat(e.target.value) || 5)}
                  className="w-full bg-[#1e293b] border border-[#38bdf8]/30 rounded px-2.5 py-1.5 text-xs text-white focus:border-[#38bdf8] focus:outline-hidden"
                />
              </div>

              {/* Post Content Textarea (if single post video) */}
              {!studio.isThreadSequence && (
                <div className="md:col-span-4">
                  <label className="block text-[10px] text-[#94a3b8] mb-1">
                    Post Statement &amp; Citations (Kinetic Narrative)
                  </label>
                  <textarea
                    rows={3}
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    placeholder="Content to animate across scenes"
                    className="w-full bg-[#1e293b] border border-[#38bdf8]/30 rounded px-2.5 py-1.5 text-xs text-white focus:border-[#38bdf8] focus:outline-hidden resize-y"
                  />
                </div>
              )}
            </div>

            <div className="flex justify-end space-x-2 pt-1">
              <button
                onClick={handleApplyDrawerEdits}
                disabled={studio.isLoading}
                className="px-4 py-1.5 rounded bg-[#38bdf8] hover:bg-[#0ea5e9] disabled:bg-[#475569] text-[#090d16] font-bold text-xs transition cursor-pointer flex items-center space-x-1.5"
              >
                <span>⚡ Recompile HyperFrames Video</span>
              </button>
            </div>
          </div>
        )}

        {/* Live Video Preview Container */}
        <div className="flex-1 w-full bg-[#090d16] overflow-hidden relative flex items-center justify-center p-2 sm:p-4">
          {studio.isLoading && (
            <div className="absolute inset-0 z-10 bg-[#090d16]/80 backdrop-blur-xs flex flex-col items-center justify-center space-y-3 text-[#38bdf8] font-mono text-xs">
              <div className="w-9 h-9 border-3 border-[#38bdf8] border-t-transparent rounded-full animate-spin" />
              <span>Compiling HyperFrames timeline with {currentTheme.label} theme...</span>
            </div>
          )}

          {studio.isExportingMp4 && (
            <div className="absolute inset-0 z-20 bg-[#090d16]/85 backdrop-blur-xs flex flex-col items-center justify-center space-y-4 text-center p-6 font-mono text-xs text-white">
              <div className="w-12 h-12 border-4 border-[#38bdf8] border-t-transparent rounded-full animate-spin shadow-[0_0_20px_rgba(56,189,248,0.5)]" />
              <div className="space-y-1">
                <p className="text-sm font-bold text-[#38bdf8]">Rendering H.264 Video via Playwright &amp; FFmpeg</p>
                <p className="text-[#94a3b8] text-[11px] max-w-sm">
                  Capturing seekable HyperFrames composition frames and encoding faststart MP4. This may take 5–15 seconds...
                </p>
              </div>
            </div>
          )}

          {studio.error ? (
            <div className="p-6 text-center text-[#ef4444] font-mono text-xs max-w-md bg-[#1e293b] rounded-xl border border-[#ef4444]/40">
              <p className="font-bold mb-2">Video Rendering Error</p>
              <p>{studio.error}</p>
            </div>
          ) : studio.previewUrl ? (
            <iframe
              key={`${studio.videoId}-${studio.aspectRatio}-${studio.theme}-${studio.fontFamily}-${studio.motionStyle}-${studio.durationSeconds}`}
              src={studio.previewUrl}
              title="HyperFrames Video Player Preview"
              className="w-full h-full border-0 rounded-xl shadow-2xl"
              allow="autoplay"
            />
          ) : null}
        </div>
      </div>
    </div>
  );
};
