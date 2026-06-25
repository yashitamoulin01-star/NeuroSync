# NeuroSync — Demo Flow

**RC1 Scripted Walkthrough**  
Estimated time: 12–18 minutes  
Audience: HR leaders, talent acquisition teams, technical evaluators

---

## Setup Checklist

Before beginning:

- [ ] Backend running: `uvicorn main:app --port 8000`
- [ ] Frontend running: `npm run dev` (port 3000)
- [ ] Camera and microphone connected and permitted
- [ ] Demo session available at `/session/demo/results`
- [ ] Browser: full screen, dev tools closed

---

## Act 1 — The Platform (3 min)

### 1.1 Landing Page
**URL:** `http://localhost:3000`

Open the landing page. Let it load fully.

> *"NeuroSync is a behavioral intelligence platform for structured interviews. Every output it produces is a piece of evidence — not a verdict. The recruiter still makes the decision. NeuroSync makes sure that decision is grounded in data."*

Point to the proof strip below the hero:
- **82.4% macro-F1** — the DeBERTa v3 model's accuracy across five behavioral dimensions
- **74K training samples** — the dataset size
- **< 1s latency** — per analysis window
- **100% local** — inference runs on your server, no data leaves

Scroll down to the **Behavioral Fingerprint** section.

> *"Five dimensions — Confidence, Engagement, Communication, Consistency, and Composure — each derived simultaneously from voice, face, and language. The final score is a multimodal aggregate, not a single metric."*

Scroll to the **Signal Pipeline**.

> *"Three independent streams: voice, face, and language. A sliding 3-second window synchronizes them. Every score is traceable to the specific signal that drove it."*

Scroll to the **Trust section**.

> *"This is the most important slide. NeuroSync never makes hiring decisions. It provides structured evidence. And everything it produces is explainable, auditable, and self-hosted."*

---

## Act 2 — The Demo Session Results (5 min)

### 2.1 Open the Demo Report
**URL:** `http://localhost:3000/session/demo/results`

> *"This is a session results report — the output NeuroSync produces at the end of every interview. Let's walk through it."*

**Report Header:**
- Point to the large verdict card ("Proceed" in green, or "Review" in amber)
- Point to the score: "74 / 100"
- Point to the metric strip below: 5 colored chips showing each dimension

> *"The verdict is prominent by design. A recruiter opening this report at the start of a debrief should immediately know whether behavioral indicators support advancing, reviewing further, or holding."*

**Assessment Summary:**
- Read or paraphrase the executive summary paragraph

> *"This is auto-generated from the session data. It doesn't just say '74 out of 100' — it explains what drove that score, where stress was detected, and whether the arc improved or declined across the session."*

**Behavioral Profile:**
- Point to the radar fingerprint chart
- Point to the 5 dimension bars with colored fills and level labels (High / Moderate / Developing / Low)

> *"Each bar shows the dimension score and a human-readable level. Each color matches the fingerprint. This is the behavioral profile for this specific candidate in this specific session."*

**Session Arc:**
- Point to the timeline chart

> *"This is behavioral performance over time. You can see where confidence dipped, where stress spiked, and whether the candidate recovered. This is what memory-based interviewing loses completely."*

### 2.2 Behavioral Narrative
Scroll down to the **Analysis** section.

> *"This is where the system earns its keep. The narrative explains what happened, why the scores are what they are, and — critically — where signals contradicted each other."*

- Point to the **Behavioral Arc** (improving / stable / declining)
- Point to a **Contradiction** (if present): *"Here — the candidate used confident language while showing physiological stress markers. NeuroSync surfaces this rather than averaging it away, so the recruiter can decide what it means."*
- Point to **Decision Support**: Observed Strengths, Areas of Concern, and Missing Signals

> *"The 'Missing Signals' section is intentional. If the session was too short for reliable scoring, NeuroSync says so. It doesn't produce scores when it doesn't have enough data."*

### 2.3 AI Model Attestation
Scroll to the bottom. Expand the **AI Model Attestation** section.

- Show the ExplainabilityPanel and ModelTransparencyCard
- Point to the model accuracy bars (per-dimension F1)
- Point to the footer attestation

> *"Every report ends with this. The model that produced these scores is named, versioned, and its performance is documented. This is what makes the report defensible in an HR audit."*

---

## Act 3 — Live Session (4 min)

### 3.1 Start a Session
**URL:** `http://localhost:3000/session/new`

> *"Let me show you what the analysis looks like in real time. I'll start a short session."*

- Enter a name: "Demo Candidate"
- Select mode: Interview
- Click "Start Interview"
- Allow camera and microphone when prompted

### 3.2 The Live Interface
**URL:** `http://localhost:3000/session/[id]`

Point to each panel:

> *"Top left: the behavioral fingerprint, updated every 500ms. This is the current behavioral state."*

Point to the metric bars:
> *"Each dimension updates in real time. Confidence, Engagement, Communication, Consistency, Composure."*

Point to the **Reasoning Inspector** (if visible):
> *"This is the reasoning inspector — it shows the raw modality signals: face, audio, and NLP, as they come in. You can see eye contact score, pitch variance, and confidence language score updating live."*

Speak for 30–60 seconds on any topic. Let the signals update visibly.

> *"The system is analyzing continuously. Everything you see here is running locally — no API calls to external services."*

End the session when ready.

---

## Act 4 — Enterprise Platform (3 min)

### 4.1 Recruiter Workspace
**URL:** `http://localhost:3000/workspace`

> *"At scale, NeuroSync provides a recruiter workspace — a ranked view of all candidates assessed, filtered by tier: Proceed, Review, Hold, or Shortlisted."*

- Show the KPI strip: Total assessed, Proceed count, Needs review count, Avg. score
- Show the filter tabs
- Show a candidate card with tier badge, confidence bar, and top strength/concern

> *"The shortlist button lets recruiters flag candidates for debrief without leaving the platform."*

### 4.2 Governance & Audit
**URL:** `http://localhost:3000/governance`

> *"Every NeuroSync deployment includes a governance center. Audit logs, compliance reports, user permissions, and data retention policy are all managed here."*

- Show the Audit Log tab (timestamp, action, actor, result)
- Show the Compliance tab

> *"This is what legal review requires. Everything is logged immutably."*

### 4.3 Architecture (Optional — for technical audiences)
**URL:** `http://localhost:3000/architecture`

> *"For engineers evaluating the platform — the interactive architecture explorer shows every component, its latency profile, its accuracy, and how signals flow through the system."*

- Click on a component card to show the detail panel
- Show the Signal Flow expandable

---

## Closing (1 min)

Return to the landing page.

> *"NeuroSync gives every interview what it currently lacks: a structured, evidence-based record of what actually happened. The recruiter still makes the decision — NeuroSync makes sure it's the right one for the right reasons."*

Point to the two CTAs:
- **Start interview** → start a real session
- **View demo results** → return to the demo report

---

## Common Questions

**"Is this a surveillance tool?"**
> No. NeuroSync is session-scoped — analysis runs only during an active structured interview, at the candidate's knowledge and with consent as per your HR policy. No continuous monitoring.

**"What if the model is wrong?"**
> All scores include a reliability tier. Insufficient-data sessions produce no scores. The platform is designed to be overridden — recruiter annotations are weighted higher than model outputs in the CBIP validation layer.

**"What about accent bias?"**
> This is documented as a known limitation. The training distribution skews toward professional English-language speech. We recommend demographic bias auditing before production deployment. The FAQ at `/faq` covers this directly.

**"Who owns the data?"**
> You do. Inference runs locally. No data is transmitted to third-party servers. Storage is SQLite on your own infrastructure.

**"Does this comply with the EU AI Act?"**
> NeuroSync provides governance infrastructure. Compliance obligations depend on your use case and jurisdiction. The Governance center, audit logs, and this documentation support a compliance argument — but legal review is required.

---

*Demo prepared for NeuroSync Platform v1.2.0-rc1*
