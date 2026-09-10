# SIH26155 — Demo Video Script (2-Minute Walkthrough)

> **Video Duration:** 02:00 (120 Seconds Exactly)  
> **Audience:** Hackathon Judges, Defense Technical Evaluators, Procurement Leads  
> **Core Narrative:** Demonstrating end-to-end multi-source transformation with zero hallucination, verifiable sentence provenance, tamper-evident audit chaining, and air-gap network isolation.

---

## Storyboard & Timing Breakdown

```
[00:00 - 00:20] BEAT 1: The Problem & Ingestion (20s)
[00:20 - 00:45] BEAT 2: 6-Parameter Config & Multi-Format Generation (25s)
[00:45 - 01:10] BEAT 3: Sentence-Level Grounding & /trace Provenance (25s)
[00:10 - 01:30] BEAT 4: Air-Gap Network Isolation Proof (20s)
[00:30 - 01:50] BEAT 5: Human Review, Inline Diff & Final Approval (20s)
[00:50 - 02:00] BEAT 6: Cryptographic Audit Ledger & Wrap-up (10s)
```

---

## Beat-by-Beat Script

### [00:00 – 00:20] Beat 1: Ingestion & Multi-Source Normalization (20 Seconds)

**Visual:**  
Camera focuses on the Operator Dashboard at `http://localhost:3000`. The persistent green banner `🟢 Offline Mode: Active (Zero Outbound Egress)` is clearly visible at the top.  
Operator clicks **"Defence Directive 2026 (Air-Gap Standard)"** in the 1-Click Samples drawer. The multi-stage progress bar animates smoothly:
- `Step 1/4: Reading & SHA-256 Checksum` &rarr;
- `Step 2/4: AES-256-GCM Encryption` &rarr;
- `Step 3/4: Docling Parser Normalization` &rarr;
- `Step 4/4: Chained Audit Record`.

**Narrator Voiceover:**  
> *"Welcome to SIH26155—the Defense-Grade GenAI platform for Automated Content Transformation. Operating in a strictly air-gapped enclave with zero internet connectivity, we begin by ingesting an unstructured defense directive. Notice the real-time parser routing—Docling, Whisper, and PaddleOCR normalize heterogeneous sources while immediately encrypting files at rest using local AES-256-GCM."*

---

### [00:20 – 00:45] Beat 2: 6-Parameter Configuration & Multi-Select Generation (25 Seconds)

**Visual:**  
Operator navigates to the **Transformation Parameters** panel.  
Clicks the **"DoD Directive"** 1-Click Preset button. The 6 controls instantly populate:
- `Audience: Joint Chiefs of Staff & Cyber Command`
- `Tone: Authoritative & Objective`
- `Language: en`
- `Detail Level: comprehensive`
- `Objective: Operational Threat Neutralization`
- `Style: DoD Military Directive Standard (MIL-STD)`

Operator selects 3 formats: **Executive Summary**, **Tactical Advisory**, and **Presentation Deck**.  
Clicks **"Generate Deliverables (3 Formats)"**.  
Under 1 second, generation completes with green checkmarks.

**Narrator Voiceover:**  
> *"Operators configure 6 mission-critical transformation parameters or apply one-touch presets like DoD Directive standard. We select 3 distinct formats: Executive Summary, Tactical Advisory, and Presentation Deck. Generating simultaneously, each format is constructed through a modular adapter enforcing strict structural contracts."*

---

### [00:45 – 01:10] Beat 3: Sentence-Level Grounding & Provenance Trace (`/trace`) (25 Seconds)

**Visual:**  
Operator clicks the **Tactical Advisory** tab. The output appears with highlighted interactive sentence chips `[Chunk #0]`, `[Chunk #1]`.  
Operator **hovers the cursor** over the sentence:
> *"All sensitive computing assets must operate inside a physically disconnected Faraday facility."*

A rich **Grounding Provenance Drawer** slides open on the right:
- Verbatim Source Quote: `"Section 1: Air-Gap Perimeter Security..."`
- Exact Character Offsets: `[char_offset_start: 38, char_offset_end: 184]`
- Heading: `Section 1: Air-Gap Perimeter Security`
- Badge: `100% Provenance Verified (Zero Hallucination)`

**Narrator Voiceover:**  
> *"Here is our core differentiator: 100% Claim-to-Chunk Provenance. In high-stakes defense environments, hallucination is catastrophic. Every single generated sentence is bound to an underlying retrieved chunk. Hovering over any claim calls our `/trace` endpoint, revealing the exact character span, section heading, and verbatim quote from the raw source document."*

---

### [01:10 – 01:30] Beat 4: Air-Gap Network Isolation Proof (20 Seconds)

**Visual:**  
Operator clicks **"🔍 Inspect Air-Gap Proof"** on the top header banner.  
The modal dialog pops up. Operator clicks **"⚡ Re-Run Socket Egress Test"**.  
A live socket probe targets public internet DNS `1.1.1.1:53`.  
Result displays in glowing emerald:
- Status: `✓ EGRESS BLOCKED (ISOLATED)`
- Diagnostic output: `Errno 10051 / 10060 - Network Unreachable (Packet drop policy active)`
- Shows Docker topology: `internal: true`, zero default gateway, zero cloud SDKs.

**Narrator Voiceover:**  
> *"We don't just assert air-gapping—we prove it live. Opening our Air-Gap Proof Inspector, the system executes an OS-level TCP socket probe to public DNS 1.1.1.1. The connection is instantly refused by our zero-egress container firewall. No OpenAI, Anthropic, or external telemetry libraries exist anywhere in our dependency tree."*

---

### [01:30 – 01:50] Beat 5: Human Review, Inline Diffs & Approval Gatekeeper (20 Seconds)

**Visual:**  
Operator switches the top role switcher from **"Operator (Alice)"** to **"Reviewer (Bob)"**.  
Navigates to **Review Studio**.  
Attempts to click **"Export Output"** &mdash; system displays a red alert:
> `HTTP 403 Forbidden: Output is locked in status 'draft'. Formal reviewer approval required.`

Reviewer clicks **"Edit Sentence"**, refines phrasing, and clicks **"Save Revision"**.  
Opens **Diff History Modal** &mdash; shows git-style unified diff with colorized `+` (green) and `-` (red) lines.  
Reviewer clicks **"Approve & Finalize"**. Status transitions to `final`.  
Export button turns green &mdash; Reviewer downloads authenticated Markdown & JSON bundles with SHA-256 checksums.

**Narrator Voiceover:**  
> *"To ensure dual-control compliance, deliverables start locked in draft status. As demonstrated, exporting draft content is strictly forbidden. Switching to the Reviewer role, Bob inspects claims, performs inline edits tracked via git-style unified diffs, and executes formal sign-off. The output transitions to final status, unlocking verified cryptographic export."*

---

### [01:50 – 02:00] Beat 6: Cryptographic Audit Ledger & Wrap-Up (10 Seconds)

**Visual:**  
Operator switches to the **Audit Trail** tab.  
A filterable table displays every action (`upload`, `generate`, `edit_sentence`, `approve`, `export`).  
Operator clicks **"Verify Cryptographic Chain"** &mdash; returns `Valid: 100% (31 records verified, SHA-256 intact)`.

**Narrator Voiceover:**  
> *"Every single action is permanently recorded in an append-only linear SHA-256 hash chain, guaranteeing complete mathematical accountability. SIH26155 delivers sovereign, secure, and verifiable intelligence transformation."*

---

## Production Recording Checklist
- [x] Resolution: 1920x1080 (1080p, 60fps)
- [x] Zoom: 110% in Chrome for crystal-clear text readability
- [x] Cursor: Highlighted click rings for visual tracking
- [x] Audio: Clear, noise-gated studio narration with subtle corporate defense soundtrack
