---
name: aiz-infographic
description: >-
  Generate deterministic, self-contained, air-gapped HTML/SVG/CSS infographics,
  visual reports, and intelligence dashboards from structured data, grounded deliverables,
  and retrieved document chunks using the 5-layer architecture (Canvases, Snippets, Styles, Elements, Templates).
---

# AIZ-Infographic Agent Skill

The `aiz-infographic` skill enables AI coding agents and operators to transform structured technical documents, RAG retrieval outputs, and intelligence briefings into high-fidelity, standalone, air-gapped HTML/SVG/CSS infographics.

## Core Tenets
1. **100% Air-Gapped**: Zero external CDN calls, zero Google Fonts fetches, zero remote JavaScript bundles. All CSS, SVG charts, and interactive modals are completely embedded.
2. **Deterministic & Grounded**: Every visual card, stat, and directive retains strict citation provenance linking back to verbatim source document chunks.
3. **5-Layer Reference System**:
   - **Layer 1: Canvases**: Responsive 1200px poster layouts with classification headers, hero metadata, and cryptographic audit footers.
   - **Layer 2: Snippets**: Specialized section patterns including Hero KPI strips, sequential Chevron process flows, and multi-column Architecture cards.
   - **Layer 3: Styles**: Cyber Defense Slate (Dark) and Tactical Paper (Light) themes with CSS variables and print stylesheets.
   - **Layer 4: Elements**: Pure inline vector SVG donut distribution charts, horizontal bar comparisons, pulsing status pills, and interactive citation inspector drawers.
   - **Layer 5: Templates**: Content-driven layouts (`tactical_defense`, `technical_architecture`, `process_flow`, `executive_brief`).

---

## 5-Layer Reference Guide

### 1. Canvases
- **Vertical Narrative Poster** (`aiz-canvas`): Optimized for executive intelligence briefs, system architectures, and security directives. Responsive from 320px mobile up to 4K displays.
- **Header Chrome**: Includes classification banner (`Air-Gapped Tier-4 Enclave`), deliverable format pill, document status dot, main title, and executive takeaway summary.
- **Footer Chrome**: Displays Document ID, Output ID, block and citation counts, and verified timestamp.

### 2. Snippets
- **Hero KPI Strip** (`aiz-kpi-strip`): Displays 2 to 4 prominent metric cards with numerical values, labels, and status badges (e.g. `100% Air-Gap Isolation`, `1024-D BGE-M3 Dense Vectors`, `AES-256 GCM Encryption`).
- **Process Flow** (`aiz-process-flow`): Numbered sequential stages with chevron connectors, stage titles, and grounded descriptions.
- **Architecture Grid** (`aiz-grid-cards`): Multi-column card matrix displaying system enclaves, capabilities, or parameters with glowing borders and citation inspection chips.
- **Analytics Row** (`aiz-analytics-row`): Dual-panel data visualization pairing an SVG donut chart with an SVG horizontal bar comparison.

### 3. Styles
- **`cyber-defense-dark`** (Default): Deep space navy background (`#090d16`), cyan accents (`#38bdf8`), emerald status highlights (`#10b981`), and subtle glassmorphic card borders.
- **`tactical-paper-light`**: High-contrast slate paper (`#f8fafc`), crisp borders (`#cbd5e1`), and dark typography (`#0f172a`).
- **Print Stylesheet**: Automatically converts canvas to pure white paper styling with crisp borders when `window.print()` is triggered.

### 4. Elements
- **Vector Donut Chart**: Rendered in pure SVG with stroke-dasharray calculations and central percentage text.
- **Horizontal Bar Chart**: Pure SVG rectangular bars with labels and rounded corners.
- **Citation Inspection Chip** (`aiz-citation-chip`): Interactive badge linking to a modal showing verbatim source quotes and character offset spans.
- **Export Toolbar**: Floating actions:
  - **Save PNG**: Rasterizes canvas into a 2x retina PNG via client-side HTML5 Canvas.
  - **Print / PDF**: Triggers native browser print preview styled for clean PDF generation.
  - **Toggle Theme**: Switches seamlessly between dark and light themes.

### 5. Templates
- `tactical_defense`: Defense directives, security advisories, policy enforcements.
- `technical_architecture`: Data pipelines, vector-graph database designs, enclave boundaries.
- `process_flow`: Ingestion lifecycles, review approval pipelines, audit flows.
- `executive_brief`: High-level strategic takeaways, KPI summaries, action items.

---

## Programmatic Usage in Venu

### 1. Via Python Service Layer
```python
from app.services.infographics import AIZInfographicEngine

# From an existing GeneratedOutput or deliverable dictionary:
html_content = AIZInfographicEngine.render_from_deliverable(
    deliverable=output,
    template="tactical_defense",
    theme="dark"
)

# From raw retrieved chunks:
html_content = AIZInfographicEngine.render_from_chunks(
    chunks=retrieved_chunks,
    title="Air-Gap Security Architecture",
    summary="Multi-enclave zero-telemetry defense directives."
)
```

### 2. Via REST API
- **Live Preview in Browser/iFrame**:
  `GET /api/v1/infographics/preview/{output_id}?theme=dark&template=auto`
- **Ad-hoc Infographic Compilation**:
  `POST /api/v1/infographics/render`
- **Export Approved Deliverable as Infographic**:
  `POST /api/v1/generate/export/{output_id}?format=infographic`
