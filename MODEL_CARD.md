# NeuroSync DeBERTa v3 — Model Card

**Version:** step_18000 (best checkpoint)
**Framework:** HuggingFace Transformers + PEFT
**Task:** Multi-label behavioral text classification
**Deployment:** Self-hosted CPU/GPU inference via faster-Whisper + DeBERTa pipeline

---

## Model Description

`microsoft/deberta-v3-base` fine-tuned with Low-Rank Adaptation (LoRA) on a behavioral text classification task.

The model classifies transcribed speech into four behavioral dimensions simultaneously:
- **Confidence** — assertiveness, clarity, absence of hedging language
- **Stress / Hesitation** — filler word patterns, self-interruption, uncertainty markers
- **Communication quality** — structural clarity, coherence, response organization
- **Engagement** — active vocabulary, energy markers, response depth

### Architecture

| Property | Value |
|---|---|
| Base model | microsoft/deberta-v3-base |
| Total parameters | 184M |
| LoRA rank (r) | 16 |
| LoRA alpha (α) | 32 |
| LoRA target modules | query_proj, value_proj |
| Trainable parameters | 442K (0.24% of total) |
| Training samples | 74,288 |
| Best checkpoint | Step 18,000 |
| Macro-F1 | 82.4% |

---

## Training

### Dataset

74,288 behavioral text samples assembled from three sources:

1. **Publicly available interview transcripts** (with researcher annotations) — confidence, hesitation, and communication quality labels from annotated behavioral interview corpora
2. **Structured coaching session logs** (with outcome labels) — session-outcome pairs used to validate that behavioral language scores correlate with coaching outcomes
3. **Augmented data** — high-confidence samples paraphrased via back-translation to improve minority class coverage

All samples passed a programmatic validation gate before inclusion. A subset (approx. 12,000 samples) received human review at the L3 confidence level (recruiter annotation). This is reflected in the CBIP Validation Pyramid, where L3-annotated data carries weight 0.70 vs. L1-auto data at 0.20.

**Data limitations:** The dataset is not a purely human-labeled gold standard. Training distribution skews toward English-language, professional-register speech. Performance on non-native English speakers, heavily accented speech, or informal registers has not been formally evaluated.

### Training Configuration

```yaml
optimizer: AdamW
learning_rate: 2e-4
warmup_steps: 500
scheduler: cosine
epochs: 3
batch_size: 32
max_sequence_length: 512
dropout: 0.1
```

### Evaluation

Test set: 15% stratified holdout from training distribution.

| Dimension | Precision | Recall | F1 |
|---|---|---|---|
| Confidence | 87.1% | 85.4% | 86.2% |
| Stress / Hesitation | 86.0% | 83.7% | 84.8% |
| Communication | 82.3% | 81.2% | 81.7% |
| Engagement | 77.8% | 76.1% | 76.9% |
| **Macro average** | **83.3%** | **81.6%** | **82.4%** |

---

## Calibration

Post-hoc calibration was applied to correct for neural network overconfidence:

- **Method:** Temperature scaling (learned T on calibration set)
- **Expected Calibration Error (ECE):** 0.031 (post-calibration)
- **Pre-calibration ECE:** 0.089

Calibration is **static** — computed once on the validation set and fixed at deployment. It is never adjusted from live session data.

Reliability tiers assigned based on calibrated probability:
- **Insufficient** (< 0.30): Score not reliable, insufficient signal
- **Low** (0.30–0.50): Limited reliability, interpret with caution
- **Medium** (0.50–0.75): Moderate reliability, standard use
- **High** (> 0.75): High reliability, report with confidence

---

## Intended Use

**Intended use cases:**
- Structured interview analysis providing behavioral evidence to recruiters
- Coaching session tracking for behavioral trend analysis
- Presentation analysis for communication skills development

**Out-of-scope use cases:**
- Making hiring decisions without human review
- Assessing individuals with communication disabilities without appropriate accommodation
- Diagnosing psychological conditions or disorders
- Real-time surveillance or mass monitoring

---

## Limitations

1. **Distribution mismatch:** Training data skews toward professional English-language speech. Performance may degrade on informal speech, non-native speakers, or technical jargon-heavy contexts.

2. **Session length dependency:** Scores from sessions under 3 minutes or under 100 words are assigned `insufficient` reliability. The model needs sufficient context to classify behavioral patterns reliably.

3. **No temporal modeling:** The model classifies 3-second windows independently. Cross-session behavioral change is tracked by the ABME layer, not the model itself.

4. **Accent and dialect bias:** This model has not undergone formal demographic bias evaluation. Accuracy may vary systematically across accent groups.

5. **Whisper dependency:** The NLP pipeline depends on Whisper transcription quality. Poor transcription (heavy accent, background noise) directly degrades DeBERTa classification accuracy.

---

## Ethical Considerations

This model must not be used as the sole input for any hiring, promotion, or adverse employment decision. All outputs are probabilistic estimates that require human interpretation and judgment.

Organizations deploying this model should:
- Conduct their own demographic bias audit before production use
- Ensure compliance with applicable AI regulations (EU AI Act, EEOC guidance, NY Local Law 144)
- Follow the NeuroSync AI Governance Policy
- Maintain human oversight for all high-stakes decisions

---

## Production Constraints

- **Model weights are immutable at runtime** — no online learning, no continuous retraining from user session data
- **Calibration is static** — computed offline, never dynamically adjusted
- **Model promotion requires regression gate** — passing all 10 golden test scenarios before deployment

---

## Citation

If referencing this model in research or documentation:

```
NeuroSync MBA Engine — DeBERTa v3-base + LoRA behavioral text classifier
Fine-tuned at r=16, α=32 on 74,288-sample behavioral interview corpus
Best checkpoint: step_18000 | Macro-F1: 82.4%
NeuroSync Platform | Behavioral Intelligence | 2026
```
