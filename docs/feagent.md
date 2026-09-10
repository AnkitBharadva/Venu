# VENÜ — Dashboard Redesign Agent Specification

## 1. Mission

Completely redesign the existing VENÜ dashboard into a polished, aesthetic, premium-looking operator console.

The current dashboard should be treated as a functional reference only. Do NOT preserve its visual layout, dark neon styling, purple-heavy palette, or existing component appearance.

The redesign must feel like a purpose-built product rather than a generic AI dashboard.

Primary visual direction:

- Off-grey / warm grey
- Silver
- Light orange
- Light yellow
- Charcoal accents where necessary
- Very restrained use of color
- Soft borders
- Subtle shadows
- Clean typography
- Spacious layouts
- Premium SaaS / intelligence-workstation aesthetic
- No excessive gradients
- No neon colors
- No unnecessary glassmorphism
- No stock imagery
- No visually noisy backgrounds

---

# 2. Product Context

Product name:

VENÜ

Tagline:

Autonomous multi-format content transformation with claim provenance

VENÜ is an air-gapped, operator-controlled content transformation system.

The operator provides source material such as:

- PDF
- DOCX
- Scanned documents
- Audio
- Text
- Intelligence reports
- Advisories
- Research documents
- Incident reports
- Other unstructured material

The system processes the source material, verifies and correlates information, maintains claim provenance, and generates objective-driven communication deliverables.

The UI should communicate:

- Reliability
- Traceability
- Security
- Human oversight
- Intelligence analysis
- Structured transformation
- Operational readiness

It should NOT feel like a typical chatbot.

---

# 3. Core Design Principle

Design the interface around:

> "Calm intelligence workstation"

The application should feel sophisticated and controlled.

Avoid:

- Cyberpunk aesthetics
- Excessive glowing borders
- Purple/blue neon
- Huge rounded cards
- Excessive icons
- Excessive badges
- Dashboard clutter
- Generic AI gradients
- Floating decorative blobs
- Overly futuristic sci-fi visuals

Prefer:

- Strong hierarchy
- Editorial typography
- Thin separators
- Compact metadata
- Functional cards
- Soft neutral surfaces
- Carefully placed accent colors
- Deliberate whitespace
- Small interaction details

---

# 4. Color System

Create a centralized design-token system.

### Primary palette

```css
--bg: #F3F1EC;
--surface: #F8F7F3;
--surface-elevated: #FCFBF8;

--border: #D8D5CE;
--border-strong: #C7C3BA;

--text-primary: #252525;
--text-secondary: #6F6D68;
--text-muted: #99958D;

--charcoal: #30302E;

--silver: #B9B8B3;
--silver-light: #D9D8D3;

--orange: #E8A36A;
--orange-light: #F3C49A;

--yellow: #EBCB72;
--yellow-light: #F5DEA0;

--success: #7E9D82;
--danger: #C87970;