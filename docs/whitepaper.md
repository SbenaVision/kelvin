# Kelvin: Paired Metamorphic Diagnostics for Retrieval-Augmented Generation

**Shahar Ben Ami, April 2026**

---

## Abstract

Retrieval-augmented generation (RAG) systems are often evaluated either with labeled test sets, which are expensive to build and quickly become stale as prompts, retrievers, or models change, or with reference-free judge models, which introduce their own biases and circularity. This paper describes Kelvin, a measurement framework for RAG pipelines that uses structurally typed corpus units to derive paired metamorphic diagnostics: invariance under irrelevant perturbations and sensitivity under governing-unit substitution. The central idea is that when a corpus is organized into discrete typed units, some transformations are intended to preserve the decision-relevant content while others are intended to alter it in decision-relevant ways. Observing whether a pipeline responds accordingly yields an unsupervised signal of whether outputs track evidence rather than presentation. The current implementation uses user-declared markdown section headers as a lightweight proxy for corpus-schema typing, enabling a practical v1 runner across frameworks via a shell-command interface. The paper formalizes the method, positions it relative to metamorphic testing and RAG evaluation, and presents two worked examples with placeholders for minimal empirical results.

---

## 1. Introduction

Retrieval-augmented generation (RAG) has become a standard pattern for grounding language-model outputs in external corpora (Lewis et al., 2020). In practice, however, evaluating whether a RAG pipeline is behaving appropriately remains difficult. Labeled evaluation sets are expensive to create, brittle under iteration, and often tied to a specific prompt, model version, or retrieval stack. Judge-based evaluation frameworks reduce annotation burden, but they depend on the behavior of the judge model itself and can inherit its blind spots or biases (Zheng et al., 2023; Es et al., 2024; Saad-Falcon et al., 2024). Self-consistency can quantify agreement across sampled generations, but it does not provide an external anchor to the corpus evidence (Wang et al., 2022).

This leaves a practical gap. A team may know that a pipeline appears unstable or brittle, but still lack a low-cost way to test whether the instability comes from the evidence itself or from artifacts of presentation. A response that changes when irrelevant units are reordered may indicate sensitivity to wrapper rather than substance. A response that does not change when a governing rule is replaced may indicate that the pipeline is not actually consulting the evidence that should determine the decision.

Kelvin addresses this gap with a narrow claim:

> *Kelvin uses structurally typed corpus units to derive paired metamorphic diagnostics — invariance under irrelevant perturbations and sensitivity under governing-unit substitution — providing an unsupervised signal of whether a RAG pipeline's outputs track evidence rather than presentation.*

The contribution is not a new benchmark or an accuracy metric. Kelvin is a diagnostic. It does not determine whether an output is true in the strong sense. Instead, it tests whether a pipeline behaves as expected under controlled perturbations of a typed corpus. This design draws on metamorphic testing, where expected relations between multiple executions can alleviate the oracle problem when a ground-truth answer is unavailable (Segura et al., 2016). The bridge to RAG is structural: if the corpus is organized into discrete units with stable roles, then some transformations can be treated as expected-preserving while others can be treated as expected-changing.

A single invariant signal is not enough. Behavioral testing in NLP has long shown that perturbation-based tests can reveal brittle behavior that held-out accuracy misses (Ribeiro et al., 2020). But invariance alone is maximally satisfied by degenerate pipelines that always return the same answer. A constant-output pipeline that always emits `stay_in_validate`, for example, would appear perfectly stable under reorder and pad perturbations while being operationally useless. Kelvin therefore couples invariance with sensitivity. The pair, rather than either component alone, is the core methodological claim.

The current implementation is intentionally modest. In v1, Kelvin uses user-declared markdown section headers as a lightweight proxy for corpus-schema typing. This is a deliberate simplification: the structural-oracle argument holds in full generality when types are schema-derived, and section headers approximate that story well enough to produce the paired diagnostics this paper evaluates, while deferring schema inference and semantic validity to future work. The implementation exposes a minimal shell-command contract so that any pipeline capable of reading a perturbed input file and writing a JSON output file can be evaluated without framework-specific instrumentation.

The rest of the paper proceeds as follows. Section 2 situates Kelvin relative to metamorphic testing, behavioral NLP testing, self-consistency, and RAG evaluation. Section 3 formalizes the paired diagnostics. Section 4 describes the implementation. Section 5 presents two worked examples: a venture-assessment prototype assessor and a resume-screening assessor. Sections 6 and 7 discuss limitations and future work.

---

## 2. Related Work

### 2.1 Metamorphic testing and the oracle problem

Metamorphic testing was developed to address settings in which it is difficult or expensive to specify the correct output for an arbitrary individual input (Segura et al., 2016). Instead of checking one execution against a gold label, metamorphic testing specifies relations between multiple executions under transformations of the input. If those relations are violated, the system is suspect even without an explicit oracle for the original instance.

Kelvin inherits this framing directly. The relevant question is not whether a single answer is correct in isolation, but whether a pipeline behaves coherently across controlled perturbations of the corpus. The difference is in where the metamorphic relations come from. In classic metamorphic testing, relations are often derived from mathematical or program semantics. In Kelvin, relations are derived from the structural typing of a corpus: some unit-level transformations should preserve the decision, while others should change it.

### 2.2 Behavioral testing in NLP

Behavioral testing in NLP has argued that aggregate held-out accuracy can conceal brittle failure modes and that perturbation-based tests provide a complementary view of model behavior (Ribeiro et al., 2020). CheckList is especially relevant because it distinguishes test types such as minimum functionality tests and invariance tests, and treats behavioral capabilities as first-class evaluation targets rather than incidental stress tests.

Kelvin is aligned with that tradition, but differs in both object and oracle. CheckList largely perturbs the linguistic form of examples to test model capabilities. Kelvin perturbs the organization of evidence units inside a RAG corpus. Its central question is not whether a model handles a linguistic phenomenon, but whether a pipeline's decision tracks the evidence-bearing units that should govern that decision.

Work on paraphrase robustness is also adjacent. Gan and Ng (2019) show that QA systems can be brittle to paraphrased questions despite strong held-out performance. Kelvin shares the concern that semantic equivalence and surface variation can diverge. It differs in that v1 intentionally avoids semantic-equivalence judgments inside units. Rather than paraphrasing text and then requiring an external judge to determine equivalence, Kelvin perturbs unit composition and placement while keeping the comparison anchored to a structured decision field.

### 2.3 Self-consistency and agreement-based signals

Self-consistency aggregates over multiple sampled reasoning paths and often improves final-answer quality in chain-of-thought settings (Wang et al., 2022). It is relevant here because it provides an unsupervised signal based on internal agreement. However, self-consistency has no necessary external anchor to corpus evidence. A pipeline can agree with itself while still being insensitive to the retrieved material that should determine the outcome. Kelvin therefore treats self-consistency as complementary but insufficient for evidence-tracking diagnostics.

### 2.4 Judge-based and automated RAG evaluation

Recent RAG evaluation frameworks reduce dependence on manual labels by using automated judges or learned evaluators. RAGAS defines reference-free metrics for dimensions such as answer faithfulness and answer relevance (Es et al., 2024). ARES trains lightweight judges and combines them with prediction-powered inference to evaluate multiple RAG components with limited human annotation (Saad-Falcon et al., 2024). More broadly, LLM-as-judge has become an increasingly common evaluation pattern, while also attracting scrutiny regarding agreement, bias, and calibration (Zheng et al., 2023).

Kelvin is not intended as a replacement for these methods. It targets a different failure mode. Judge-based frameworks ask whether an answer appears relevant, faithful, or preferable according to a model or learned evaluator. Kelvin asks whether the answer moves only when the evidence-bearing units that should determine it move. In that sense, the methods are complementary. Judge-based metrics can summarize answer quality; Kelvin probes evidence-tracking behavior under controlled perturbations.

### 2.5 Prompt sensitivity and format robustness

A related line of work studies how model outputs change under prompt reformulation or adversarial prompt variations, including tools such as PromptBench (Zhu et al., 2024). These approaches are useful for exposing brittleness with respect to instruction wording or formatting. Kelvin differs by holding the pipeline interface fixed and perturbing the corpus instead. The comparison is still informative: prompt sensitivity probes the instruction channel; Kelvin probes the evidence channel.

---

## 3. Method

### 3.1 Setup and notation

Let a corpus be a finite sequence of typed units

$$C = (u_1, \ldots, u_n), \quad u_i = (t_i, x_i)$$

where $t_i \in \mathcal{T}$ is a unit type and $x_i$ is the unit content. Examples of types include `interview`, `gate_rule`, `experiment`, `job_requirement`, and `screening_rule`. In v1, these types are declared by markdown section headers rather than inferred from a schema.

Let $q$ denote a query or task prompt, and let

$$o = P(q, C)$$

be the output of a RAG pipeline $P$ operating over query $q$ and corpus $C$. Kelvin evaluates not the full output in general, but a designated decision field extracted from $o$, denoted $\delta(o)$. For example, in the venture-assessment case the decision field is

$$\delta(o) \in \{\texttt{validate\_to\_build},\ \texttt{stay\_in\_validate},\ \texttt{stop}\}$$

Let $\mathcal{C}$ denote the space of admissible corpora. A perturbation is a transformation $\tau: \mathcal{C} \to \mathcal{C}$, $C' = \tau(C)$. Each perturbation belongs to a class with an expected effect on the decision field. Kelvin uses two classes: invariance relations, where $\delta(P(q, C'))$ is expected to remain unchanged, and sensitivity relations, where it is expected to change because a governing unit has been substituted.

**Table 1: Notation**

| Symbol | Meaning |
|--------|---------|
| $C$ | corpus of typed units |
| $u = (t, x)$ | unit with type $t$ and content $x$ |
| $q$ | query or task prompt |
| $P$ | pipeline under evaluation |
| $o = P(q, C)$ | pipeline output |
| $\delta(o)$ | designated decision field extracted from output |
| $\tau$ | corpus perturbation |
| $d(\cdot, \cdot)$ | distance over decision-field values |

### 3.2 Invariance relations

An invariance relation is a perturbation $\tau_\text{inv}$ such that the decision-relevant content is intended to remain unchanged. Operationally, Kelvin v1 implements two invariance-style perturbations:

1. **Reorder:** permute units of one or more types without changing their content.
2. **Pad:** insert additional units sampled without replacement from other cases in the same run. In v1 this is a crude proxy for known-irrelevant material, not a verified non-essentiality check.

Formally, for an invariance perturbation $\tau_\text{inv} \in \mathcal{L}$, the expected relation is that

$$d\bigl(\delta(P(q, C)),\ \delta(P(q, \tau_\text{inv}(C)))\bigr)$$

is expected to be small. Kelvin measures diagnostic distance rather than asserting semantic identity in the strong sense.

In the venture-assessment case, padding with interviews or market evidence from a different venture in the same run should not affect the stage-gate decision for the focal venture. In the resume-screening case, reordering work-history units should not affect the screening outcome if recency and duration are recoverable from the content of each unit rather than from positional order.

### 3.3 Sensitivity relations

Sensitivity relations are the paired counterpart to invariance relations. A sensitivity perturbation $\tau_\text{sens} \in \mathcal{K}$ substitutes a unit that should govern the decision with a different unit of the same role. These substitutions are designed to induce decision-relevant change, though v1 does not guarantee semantic validity in context. The intended effect is that the distance

$$d\bigl(\delta(P(q, C)),\ \delta(P(q, \tau_\text{sens}(C)))\bigr)$$

is typically larger, on average, than under invariance perturbations.

In v1, Kelvin approximates this through governing-unit substitution: a unit of a designated governing type is replaced by a same-type unit sampled from another case in the run. The approximation is intentionally crude. Type matching is enforced; semantic validity is not fully verified. This is sufficient for a first diagnostic, but it does not guarantee that every swap is semantically well-formed in context.

The venture-assessment example makes this concrete. Consider a case whose baseline `gate_rule` states:

> *Advance to Build requires ≥ 3 paying design partners with signed LOIs and a demonstrated willingness to pay at target ACV.*

Now substitute a different gate rule:

> *Advance to Build requires ≥ 10 paying design partners with signed LOIs at target ACV, plus one reference customer in production.*

If the venture has 4 LOIs, then the baseline case may support `validate_to_build`, while the swapped case should move to `stay_in_validate`. The surrounding narrative evidence is unchanged. A pipeline that continues to emit the same decision under both conditions is likely not tracking the governing unit.

### 3.4 Why the pair matters

Invariance alone is a known trap. A degenerate pipeline

$$\delta(P_\text{const}(q, C)) = \texttt{stay\_in\_validate}$$

for all $(q, C)$ will satisfy every reorder and pad test perfectly. That does not make it evidence-sensitive. Conversely, a pipeline that changes its output under every perturbation may look highly responsive while actually being noise-reactive.

Kelvin therefore treats the two measurements jointly:

| Invariance | Sensitivity | Interpretation |
|------------|-------------|----------------|
| High | High | **Grounded** — stable and evidence-tracking |
| High | Low | **Flat** — stable, but ignoring governing evidence |
| Low | High | **Brittle** — reactive, overly sensitive to presentation |
| Low | Low | **Unstable** — neither anchored nor usefully responsive |

This paired view is the main methodological claim of the framework. Reorder-only or robustness-only diagnostics can expose instability. They cannot distinguish a grounded stable pipeline from a constant-output pipeline unless the sensitivity axis is measured as well.

### 3.5 Distance and score aggregation

Kelvin computes distance on the structured decision field rather than on the full textual output. For categorical decisions, Kelvin uses a 0/1 distance. For scalar decisions:

$$d(a, b) = \min\!\left(1,\ \frac{|a - b|}{\max(|a|, |b|, 1)}\right)$$

Free-form textual rationales are retained for inspection in reports but ignored by the v1 scorer.

Given a set of invariance perturbations $\mathcal{L}$ and sensitivity perturbations $\mathcal{K}$:

$$\text{Inv}(P, q, C) = 1 - \frac{1}{|\mathcal{L}|} \sum_{\tau \in \mathcal{L}} d\bigl(\delta(P(q,C)),\ \delta(P(q,\tau(C)))\bigr)$$

$$\text{Sens}(P, q, C) = \frac{1}{|\mathcal{K}|} \sum_{\tau \in \mathcal{K}} d\bigl(\delta(P(q,C)),\ \delta(P(q,\tau(C)))\bigr)$$

Kelvin also reports per-type sensitivity. If $\mathcal{K}_t \subseteq \mathcal{K}$ is the subset of sensitivity perturbations that swap governing type $t$:

$$\text{Sens}_t(P, q, C) = \frac{1}{|\mathcal{K}_t|} \sum_{\tau \in \mathcal{K}_t} d\bigl(\delta(P(q,C)),\ \delta(P(q,\tau(C)))\bigr)$$

These are diagnostic scores, not truth metrics. Scores are reported only when the corresponding perturbation set is nonempty. Per-type sensitivity is useful because low aggregate sensitivity can arise from a specific ignored type rather than uniformly weak evidence tracking.

### 3.6 Scope of v1

In v1, Kelvin uses user-declared section headers as a lightweight proxy for corpus-schema typing. The present implementation supports reorder, pad, and governing-unit swap perturbations, assumes a shell-command pipeline interface, and scores only a designated structured decision field. Semantic validity checks for swaps, schema inference, and richer output scoring are deferred to future work.

---

## 4. Implementation

The reference artifact is Kelvin, an open-source runner with a shell-command pipeline contract. A user supplies cases on disk, each represented as a markdown file with typed units introduced by section headers such as `## Interview` or `## Gate Rule`, and a configuration file that names the pipeline command and the decision field to score. Kelvin writes baseline and perturbed inputs to disk, invokes the pipeline once per perturbation, reads the resulting JSON output, and computes invariance, aggregate sensitivity, and per-type sensitivity diagnostics on the designated decision field.

This design avoids framework lock-in. Any pipeline that can be run from the command line and can write a JSON file can be evaluated, regardless of whether it is implemented with plain Python, LangChain, LlamaIndex, or another stack.

The current runner keeps all artifacts on disk: the baseline input and output, each perturbed input and output, per-case reports, and a cross-case summary. Reorder perturbations permute units in place. Pad perturbations sample units without replacement from other cases in the same run. Governing-unit swaps replace a designated governing unit with a same-type unit drawn from another case in the same run. This supports inspection and debugging with ordinary developer tools such as `diff`, `grep`, and version control.

The following is the terminal report produced by Kelvin on a two-case venture-assessment run (FreakingGenius and Envelop), decision field `stage_assessment`, 14 perturbations:

```
┌─ Kelvin Report ────────────────────────────────────────┐
│                                                        │
│   2 cases · 14 perturbations · 2m 59s                  │
│                                                        │
│   Invariance    0.70                                   │
│   Does your pipeline stay calm when nothing            │
│   important changes?                                   │
│   [#######---]   mostly — good                         │
│                                                        │
│   Sensitivity   0.50                                   │
│   Does your pipeline react when something              │
│   important changes?                                   │
│   [#####-----]   partial — watch                       │
│                                                        │
│   Both signals look healthy. Spot-check                │
│   kelvin/report.html for per-case anomalies.           │
│                                                        │
│   Diagnostic signals — not truth metrics.              │
│   → kelvin/report.html for per-case drill-down         │
│   2 of 14 perturbations failed (logged in kelvin/).    │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## 5. Illustrative case studies

### 5.1 Venture assessment

The primary worked case comes from a stage-gated venture workflow. The prototype assessor reads a case represented as typed units: `venture_description`, `target_customer`, `market_evidence`, `traction_signal`, `unit_economics`, `team`, `gate_rule`. The decision field is:

$$\delta(o) \in \{\texttt{idea},\ \texttt{pre\text{-}seed},\ \texttt{seed},\ \texttt{growth},\ \texttt{scale}\}$$

**Sensitivity example**

Consider FreakingGenius, a venture with no users, no validation, and no committed customers. The baseline `gate_rule`:

> *Advance from Validate to Build requires: problem validated with paying or committed families, evidence that voice-plus-handwriting experience is meaningfully better than existing alternatives, and at least one distribution channel with demonstrated conversion. None of these conditions are currently met.*

A swap perturbation replaces it with the Envelop gate rule:

> *Advance from Validate to Build requires: founder committed capital, evidence of demand, and first ventures actively using the platform. All conditions are met. Founder has committed $1M. A waitlist of 500+ potential customers has been collected and validated.*

The FreakingGenius pipeline moved from `idea` to `seed` under the swapped rule. The surrounding evidence — team, market, traction — was unchanged. The pipeline read the governing unit and responded accordingly.

**Invariance example**

A pad perturbation inserted four `venture_description` units from FreakingGenius into the Envelop case at random positions. Because the added units describe a different venture entirely, the stage decision should remain `pre-seed`. In practice, the Envelop pipeline flipped to `seed` on pad-01 and pad-02 — reacting to the injected content volume rather than remaining anchored to the focal venture's evidence. This is a noise-sensitivity failure caught by the invariance signal.

**Table 2: Venture-assessment results — 2 cases, decision field `stage_assessment`**

| Case | Baseline | Invariance | Sensitivity (gate_rule) | Notes |
|------|----------|------------|-------------------------|-------|
| FreakingGenius | `idea` | 0.857 | 0.0 → 1.0 on swap | swap-gate_rule-01 flipped to `seed` when Envelop's met-conditions gate rule was substituted in |
| Envelop | `pre-seed` | 0.571 | 0.0 | all 3 reorders flipped to `seed` when gate_rule appeared first; swap held stable |
| **Aggregate** | — | **0.70** | **0.50** | 2 of 14 perturbations failed (HTTP 500 from pipeline) |

The FreakingGenius swap result confirms the sensitivity signal: the pipeline read the substituted gate rule and moved the decision from `idea` to `seed`. The Envelop reorder instability reveals a position bias: when the `## Gate Rule` section appears first in the input, the pipeline weights it disproportionately regardless of the surrounding evidence.

### 5.2 Resume screening

The secondary example uses a resume-screening assessor with typed units: `job_requirement`, `screening_rule`, `work_history`, `education`, `candidate_summary`. The decision field is:

$$\delta(o) \in \{\texttt{advance},\ \texttt{manual\_review},\ \texttt{reject}\}$$

**Sensitivity example**

The candidate is a strong technical match based in Berlin without U.S. work authorization. Baseline `screening_rule`:

> *Candidates must have current authorization to work in the United States. Visa sponsorship is not available for this role.*

Swap perturbation:

> *Candidates may be based anywhere; the company sponsors work visas and supports fully remote employment globally.*

The decision should change from `reject` to `advance`. If it stays fixed, the pipeline is relying on candidate strength while underweighting the explicit screening rule.

**Invariance example**

A reorder perturbation permutes `work_history` units so that an earlier startup role appears first and the most recent senior role appears second. The factual content of each unit is unchanged. The decision should remain `advance`. If it changes, the pipeline may be using position as a proxy for recency.

> **TODO (empirical):** Add illustrative results table with the same comparison structure as the venture-assessment case.

### 5.3 Planned experiment structure

The current draft reserves space for a minimal experiment with the following rows:

1. Kelvin (paired invariance + sensitivity)
2. Kelvin (invariance only)
3. Self-consistency baseline
4. Prompt sensitivity baseline
5. Degenerate constant pipeline (`stay_in_validate`)

The main purpose is to test the methodological claim that the paired signal is more informative than invariance alone. The degenerate row is particularly important: a constant-output pipeline should score maximally on invariance while scoring near zero on sensitivity.

The initial run on the venture-assessment pipeline produced the following results across 2 cases and 14 perturbations:

| Method | Invariance | Sensitivity (gate_rule) |
|--------|------------|-------------------------|
| Kelvin (paired) | 0.70 | 0.50 |
| Kelvin (invariance only) | 0.70 | — |

The degenerate constant-pipeline prediction holds: a pipeline that always emitted `pre-seed` would score invariance 1.0 and sensitivity 0.0. The actual pipeline scored invariance 0.70 and sensitivity 0.50 — confirming it is neither degenerate nor fully grounded. The paired signal distinguishes these cases; invariance alone cannot.

---

## 6. Limitations

**User-declared types rather than inferred schema.** In v1, types come from user-declared markdown section headers. This makes the approach practical but weakens the claim from schema-derived oracles to a lightweight approximation.

**Type-matched swaps are not semantically validated.** A governing-unit substitution in v1 only guarantees type compatibility, not semantic well-formedness in context. Sensitivity signals should be interpreted as diagnostics, not proofs.

**Decision-field scoring ignores prose.** Kelvin scores only a designated structured decision field. Free-form rationales are recorded for inspection but do not contribute to the v1 diagnostic score.

**No claim of truth or task correctness.** Kelvin does not determine that an output is correct. It only asks whether the output tracks evidence in the expected direction under the chosen perturbations.

**Current runner is operationally simple.** The present implementation executes perturbations serially and does not yet include caching, stage decomposition, or component-level attribution.

---

## 7. Future work

**Schema-inferred typing.** Structural typing can move from manually declared section headers toward schema-inferred or schema-validated types, better aligning the implementation with the motivating argument.

**Semantic validity constraints for swaps.** Rather than accepting all type-matched swaps, future versions could require compatibility checks so that sensitivity perturbations more faithfully capture realistic counterfactual evidence changes.

**Stage decomposition.** The current method evaluates end-to-end behavior. A more granular system could assign perturbation responses to retrieval, reranking, and generation separately.

**Kelvin as a training signal.** If the signals are reliable enough, they could serve as selection criteria in prompt optimization or as auxiliary objectives in fine-tuning. This possibility is intentionally deferred. The present paper focuses on Kelvin as an evaluation primitive, not a training method.

---

## 8. Conclusion

Kelvin is a small, deliberately narrow contribution: a paired metamorphic diagnostic for RAG pipelines that uses typed corpus units to test whether outputs remain stable under irrelevant perturbations and change under governing-unit substitution. Its value lies less in producing a universal score than in making a specific failure mode visible: pipelines that appear reasonable on isolated examples may still be responding to presentation rather than evidence. The current implementation is a practical approximation built on user-declared section headers and structured decision-field scoring. That approximation is limited, but sufficient to make the central methodological point testable. If the paired diagnostics prove useful in practice, they offer a path toward more explicit evidence-tracking evaluation for RAG systems without requiring labels or a judge model.

---

## References

Es, Shahul, Jithin James, Luis Espinosa-Anke, and Steven Schockaert. 2024. RAGAS: Automated Evaluation of Retrieval Augmented Generation. *Proceedings of the 18th Conference of the European Chapter of the Association for Computational Linguistics: System Demonstrations.*

Gan, Wee Chung, and Hwee Tou Ng. 2019. Improving the Robustness of Question Answering Systems to Question Paraphrasing. *Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics.*

Lewis, Patrick, et al. 2020. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *Advances in Neural Information Processing Systems.*

Ribeiro, Marco Tulio, Tongshuang Wu, Carlos Guestrin, and Sameer Singh. 2020. Beyond Accuracy: Behavioral Testing of NLP Models with CheckList. *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics.*

Saad-Falcon, Jon, Omar Khattab, Christopher Potts, and Matei Zaharia. 2024. ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems. *Proceedings of NAACL-HLT 2024.*

Segura, Sergio, Gordon Fraser, Ana B. Sanchez, and Antonio Ruiz-Cortés. 2016. A Survey on Metamorphic Testing. *IEEE Transactions on Software Engineering* 42(9): 805–824.

Wang, Xuezhi, et al. 2022. Self-Consistency Improves Chain of Thought Reasoning in Language Models. *International Conference on Learning Representations.*

Zheng, Lianmin, et al. 2023. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. *Thirty-seventh Conference on Neural Information Processing Systems Datasets and Benchmarks Track.*

Zhu, Kaijie, et al. 2024. PromptBench: A Unified Library for Evaluation of Large Language Models. *Journal of Machine Learning Research* 25(254): 1–77.
