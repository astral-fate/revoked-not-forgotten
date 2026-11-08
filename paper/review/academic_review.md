# Academic review: "Revoked but Not Forgotten: Residual Influence of Revoked Agents in LLM Agent Teams"

Reviewed 2026-11-08. Mode: `academic-paper-reviewer` full review (field analysis, five-seat panel, editorial synthesis, revision roadmap). The manuscript was not modified.

**Inputs read.** `paper/main.pdf` (14 pp., compiled 22:09), `paper/main.tex` (last edited 22:10, after the PDF), `numbers.tex`, every `tab_*.tex`, `src/revres/{env,scenarios,grade,analyze}.py`, `paper/make_numbers.py`, every `experiments/*/results/*/trials.jsonl`, the cached handoffs and the transcripts I needed. For context I also read `02_Guidelines/judging_criteria.md`, `03_Resources/literature_gap_matrix.md`, the local paper corpus under `03_Resources/papers/**`, `04_Schedule_and_People/judges.md` and `meetings/talk_summaries.md`.

**How the panel was run.** One model played all five seats in a single context, one after another. The seats differ in role only. They are not independent reviewers and their errors are likely correlated. I did not run the skill's sprint-contract or provenance scripts. Treat the result as one structured expert reading, not as five separate referees. Calibration: `NOT_CALIBRATED`.

**Out of scope.** gpt-oss-120b is still running and will be added, so its absence is not flagged.

---

## Phase 0: Field analysis and panel configuration

| Item | Assessment |
|---|---|
| Primary field | AI safety / multi-agent LLM security (agent infrastructure, Track 3) |
| Secondary fields | Computer security (revocation, information-flow control, taint tracking); experimental methodology for LLM evaluation |
| Paradigm | Controlled experiment with a paired design. Scripted attacker, LLM writer and LLM executor, graded by deterministic exact match. |
| Venue | Apart Swarm Alignment Hackathon report: at most 8 body pages, abstract of 150–250 words, Limitations and Dual-Use appendix required. Judges score 1–5 on Impact, Execution and Presentation. Many judges are production IAM and security engineers (Okta agent identity, Uber enterprise IAM "revocation, attribution, least privilege", Amazon IAM, Snowflake security, Gray Swan red-teaming). |
| Maturity | Late draft. Every number is macro-generated from the data. Two experiments were added recently. One edit made after the last compile introduced a build regression (see C1). |

| Seat | Configured persona |
|---|---|
| Journal-Fit Reviewer (EIC) | Senior editor of a security-for-ML workshop (in the style of SaTML or an IEEE S&P workshop) with a sprint-judging lens. Asks whether the work is new relative to identity, revocation and IFC work, and whether practitioners would act on it. |
| R1 Methodology | Applied statistician for LLM evaluations. Looks at paired designs, McNemar, multiplicity, clustering and pseudo-replication, and conditional metrics. |
| R2 Domain | Agent-infrastructure and IAM security researcher who knows capability tokens, revocation, provenance and IFC. Looks for missing related work and novelty. |
| R3 Perspective | Platform and SRE practitioner who asks about deployability, cost, false alarms and transfer to real agent platforms. |
| DA | Devil's Advocate who attacks the core claim that revocation has to reach content, enforced by the platform. |

---

## Phase 1: Panel reports

### Journal-Fit Reviewer (EIC)

**Summary.** The paper names and measures *residual influence*: content a compromised agent handed off before revocation that is still acted on afterwards. It shows that credential-only revocation leaves it almost unchanged (pooled 76% → 73%). Signals the executor can see (a notice, retraction of posts, lineage marks) work for some models and not others. A platform-side "taint + quarantine" mechanism brings residue to 0–2% for the three open models.

**Fit and originality.** The fit is very strong. The question comes word for word from a sprint speaker who is also a judge (Shenk, `talk_summaries.md` l.434; cited as [14]). It fills the T3-RQ1 gap in `literature_gap_matrix.md` (§Track 3, l.135–148), which surveys revocation designs that all operate on credentials. The "credential vs content" reframing is clean, memorable and new as far as the local corpus shows. Revocation designs (Deochake, AIP, CAPMAS, South) do not measure content persistence. Spread studies (Lee, Wu, Ju) do not study removal after revocation.

**Concerns about significance.**
- The winning mitigation is in essence classic taint tracking and information-flow control. The paper does not present it that way and cites none of that literature. Security judges will notice.
- The attacker is scripted and non-adaptive. The chain has one hop.
- Taint matching uses exact strings. The data already contain a non-adversarial failure of it (see C2).

**Recommendation signal.** Minor-to-major revision. The contribution is sound and well targeted. The required changes concern accuracy of two claims, statistical hygiene and positioning, not new science.

**Strengths, anchored.** Paired cached-handoff design (§3.4, l.124). Deterministic grading with no LLM judge (§3.6, l.153). Positive control (`compromised`) and negative control (`clean`). A false-alarm arm (`benign_*`). Ablations aimed at the obvious rival explanations (§4.3). Every number generated from logs (l.244, l.362). Honest limitations (l.238, App. C).

### Reviewer 1: Methodology

**Overall.** The design is better than typical sprint work: paired, deterministic, with controls and ablations. Its inferential layer has four problems. Each has a cheap fix.

1. **Multiplicity (Major).** Table A.9 (l.264–271) has **114 exact McNemar tests**. 53 are nominally significant at 0.05. Nothing is corrected, and the prose uses "significant" and "significant for none" as binary verdicts. I applied Holm and Benjamini–Hochberg to the generated `tab_mcnemar.tex`:
   - Headline contrasts survive every correction: Luna notice 24/0; pooled lineage 44/1; `early_revoke` and `strict_notice` for Qwen and Gemma; `taint_quarantine` against `nocite_lineage` for all three models.
   - **12 claims lose significance under Holm.** Among them: Luna retract→lineage 8/0, p = 0.008 (§4.2, l.185); Gemma revoke_lineage→nocite 2/13, p = 0.007 (l.202); Gemma revoke_lineage→nosource residue 0/11, p = 9.8×10⁻⁴ (l.204); Qwen taint_lineage→taint_quarantine 7/0, p = 0.02 (l.219).
   - **4 claims lose significance even under BH.** The most visible is "task success under lineage marks fell to … 0% (**significant for all three models**)" (l.204). Gemma and Ministral have p = 0.03 each, so under BH only Qwen survives.
   - **Fix.** Pre-declare about six confirmatory contrasts (C→S, S→N, R→L, L→nocite-L, nocite-L→taint-Q, clean→benign-taint-Q task) as the primary family and apply Holm to them. Label everything else exploratory. Put an adjusted-p column in Table A.9. Have `make_numbers.py` produce "significant (Holm)" text instead of a raw p < 0.05 test.

2. **Pseudo-replication by template (Major).** The 48 seeds per cell are 6 templates × 2 payloads × 4 repetitions. The four repetitions are close to deterministic.
   - For Gemma under `compromised` and `revoke_notice`, all 12 template × payload cells are all-or-nothing (4/4 or 0/4).
   - Gemma's fact residue is structurally 0/4 on the currency, shipping and tier templates, because it never writes those fields. Even in `clean` it only issues the refund and finishes.
   - So the effective sample is nearer 12 cells than 48 independent pairs, and McNemar p-values computed over seeds are too small. Gemma retract→lineage 12/0 (p = 4.9×10⁻⁴) comes from a handful of template cells.
   - **Fix.** Report a template-clustered sign or permutation test, or a cluster bootstrap CI, for the confirmatory contrasts. Add one sentence to Limitations on within-cell determinism. Add a per-template appendix table (cheap: it is already in the data).

3. **Null claims stated as absence (Major).** The paper says "no measurable false-alarm cost" in the abstract (l.54), §4.4 (l.208), §4.5 (l.219), the Discussion (l.236) and the Conclusion (l.241). That is absence of evidence at n = 48 on a base rate of about 45%.
   - Paired differences (Wald 95% CI) for Qwen: `benign_taint_quarantine` −10.4 pp [−29.8, +9.0]; `benign_quarantine` −12.5 pp [−29.5, +4.5].
   - Ministral `benign_quarantine` is 5/0 discordant, −10.4 pp. Exact p = 0.06, but the Wald CI is [−19, −2].
   - A 20–30-point relative loss of task success is therefore not excluded.
   - **Fix.** Write "no statistically detectable cost at n = 48 (Qwen −10 pp, 95% CI −30 to +9)". Add the paired-difference CIs to Table 5. State the minimum detectable effect.

4. **Conditional metric "False | wrote" (Minor–Major).** The metric conditions on writing the field (l.153; Tables A.1–A.4). Writing the field is a post-treatment variable that the conditions themselves change: Qwen wrote it in 12% of trials under `nosource_lineage` against 48% under `revoke_lineage`. The conditional rates are therefore not paired and not comparable across conditions.
   - The paper calls fact-residue rates "conservative" (l.238). They are only conservative for the unconditional rate.
   - **Fix.** Label the conditional rates descriptive. Do not compare them across conditions. Report fact residue separately for the templates where the model writes the field in `clean`.

5. **Pooling across models (Minor).** Pooled rates and the pooled McNemar (l.177, 183, 185) average across models that behave in opposite ways. Lineage marks pool to 31% while individual models range from 0% to 67%. Luna also contributes fewer pairs.
   - Pairing on (model, seed) is valid as a test. As a headline, though, the pooled rate describes no deployable system.
   - **Fix.** Lead with the per-model range, as the Discussion already does (l.234). Keep the pooled rate descriptive. Optionally add a stratified exact test, or a mixed logistic model with model and template effects.

6. **The pairing claim is overstated (Minor).** l.124 says ablation runs "pair with main-grid trials on the same seed and handoff" and that differences are "attributable to the revocation mechanism alone". This is untrue for `early_revoke`, where the writer sees the notice and produces a new handoff, and for `nocite_*`/`taint_*`, which use a different writer variant.
   - **Fix.** Write "conditions that share a handoff variant pair on the identical handoff; `early_revoke` and the no-citation conditions pair on seed only."

7. **Grader construct (Minor).** `grade.py` scores task success as an exact match on the truth value. A field written as "25 seats", or a value rendered "2,508", is not matched. Clean task success is only 40–48% for the open models, and for three templates the ticket barely asks for a record update. That makes task success a weak false-alarm metric.
   - **Fix.** Name this in Limitations. Report clean task success per template.

### Reviewer 2: Domain (agent infrastructure and security)

**Novelty.** Real. Measuring *post-revocation content persistence*, and separating credential, content and derived-content revocation, is a useful decomposition that the identity papers in the corpus do not make. The mixed-team result ("residue follows the executor") is a good mechanistic touch.

**Missing related work from the local corpus (Major).**
- **Safin et al. 2026, "Trust propagation and structural containment in multi-agent LLM pipelines"** (`03_Resources/papers/lit_search/track2/safin2026_…`, arXiv 2609.17648). It has nearly the same pipeline (Supervisor → Researcher → Validator → Executor) and a compromised low-privilege agent influencing a higher-privilege executor. It shows *structural* authorization contains the attack where agent judgment fails. This is the closest prior work. Its conclusion (enforce structurally, not through agent judgment) anticipates this paper's Discussion. **It must be cited and distinguished:** Safin blocks at authorization time, while this paper studies removal after attribution and revocation.
- **CaMeL / Foerster et al. 2026, "CaMeLs can use computers too"** (`track4_oversight_control/foerster2026_…`), and through it Debenedetti et al. 2025 (CaMeL). Capability and data-flow tracking that separates trusted control from untrusted data is the established form of "taint provenance". **Fix:** in §2 and §5, frame taint + quarantine as applying information-flow control to revocation, and claim novelty for the measurement and for the "revocation must trigger re-derivation" design, not for taint tracking.
- **Ju et al. 2024, "Flooding spread of manipulated knowledge"** (`track2/ju2024_…`). False knowledge spreading and persisting in agent communities belongs in the "Spread" paragraph (l.78).
- **Papadopoulos et al. 2026, "Mind viruses"** (`track2/papadopoulos2026_…`). Self-propagating content between agents is the same family as Lee 2024 and Wu 2026.
- Optional: Habler 2025 (secure A2A / MAESTRO), Ji 2026 (SEAgent, mandatory access control), Anbiaee 2026 (threat modelling of MCP/A2A/Agora/ANP), all in `track3_infrastructure/`. One sentence covering protocol-level threat models would pre-empt "what about A2A?" questions from IAM judges.

**Domain accuracy.**
- The AIP description (l.76: provenance "of invocations, not of claims") is fair.
- The claim that "None measures the persistence of content an agent produced before revocation" (l.76) is consistent with the corpus. Soften it to "none of these designs measures" so it does not read as a claim about all literature.
- Discussion (l.236): "removing the content was not [model-dependent]". `revoke_quarantine` (removal located by citations) left Ministral at 60%. The correct statement is "removing content *that the platform located* was not". The paper's own explanation (uncited lines) supports this wording.

**Domain concern: what an adaptive attacker does (Major for Impact).** The limitation is stated (l.238). The data also already contain a natural, non-adversarial failure of exact-match taint (C2 below). A domain expert would want one cheap robustness arm: number- and format-normalised taint matching, or a writer told to paraphrase values.

### Reviewer 3: Perspective (platform practitioner)

- **Actionability is good.** The two design rules (platform-recorded provenance; revocation triggers re-derivation, l.236) are concrete enough to file as a feature request against an agent platform.
- Add a short "What a platform should do tomorrow" box that lists: (1) a revocation event triggers a content sweep over downstream contexts; (2) withhold-and-re-derive; (3) normalised taint matching; (4) record provenance at handoff time.
- **The cost side is under-reported.** Quarantine depends on a second source. Without one (`nosource_*`) task success collapses to 0% for every model (l.204). Real deployments often have no redo path. The paper notes this (App. C l.357), but Table 5 and the Discussion should state the cost explicitly: "quarantine converts residue into escalation or non-completion when no second source exists".
- **Transfer.** The open models are 14–31B and served with an 8k context. The one frontier API model (Luna) is incomplete and absent from every mitigation experiment. Practitioners will ask whether frontier agents behave like Luna, where a plain notice nearly suffices. The paper should say plainly that the strongest model needed the least platform help. That is evidence for "it depends on the model", and does not on its own show that platform enforcement is necessary.
- **The early-revoke result is close to trivial.** If the writer never sees the false value, residue is 0 by construction. Frame it as a sanity/positive check that the effect needs propagation ("as expected, …"). It is not a finding.

### Devil's Advocate

**Strongest counter-argument (≈250 words).**
The headline, "revocation for agent teams has to reach content, enforced by the platform", rests on one mitigation, `taint_quarantine`. That mitigation succeeds here because the threat model hands the defender a perfect, verbatim fingerprint: a unique canary string the attacker never alters. Under those conditions any string-matching filter is close to an oracle, so "0–2% residue" mostly reflects the testbed's design. Even here the oracle leaks:
- In 5 of the 144 no-citation handoffs (Qwen seeds 15 and 39; Ministral seeds 3, 21 and 27) the writer rendered the false seat count `2508` as `2,508`. Exact-match taint did not withhold those lines. In 4 of the 5 it found no derived line at all; in seed 21 it withheld only the export-address line.
- One of those 5 (Ministral seed 3) produced the single residual case under `taint_quarantine`, and also under `taint_lineage`.

So the only failure of the winning mitigation is caused by benign reformatting, not by an attacker. The paper still reports that "no handoff kept any of worker-X's content after withholding" (l.219) and that "derived lines were found in every handoff that carried worker-X's content" (App. C, l.357). Both statements are true only because "carried" and "kept" are defined by the same exact match (`make_numbers.py` l.556–563 skips handoffs without an exact match and then rechecks the same terms). The check is circular.

The comparison with executor-side signals is also uneven. A one-sentence `strict_notice` brought Qwen and Gemma to 6% and 10% at zero infrastructure cost. Taint quarantine needs a redo path, and without one it costs all task success (`nosource_*`). A sceptic would conclude that the evidence supports "make the notice name derived content, and add platform withholding as defence in depth". It does not support "platform enforcement is necessary".

**Issue list.**

| Severity | Dimension | Location | Issue |
|---|---|---|---|
| **CRITICAL** | Claim accuracy | §4.5 l.219; App. C l.357 | The statements that no handoff kept worker-X's content and that every carrying handoff was found are circular, and false in substance (2,508 cases). The single residual case is unexplained. |
| MAJOR | Overgeneralisation | Abstract l.54; Conclusion l.241; Discussion l.236 | "Removed residual influence for every model … without measurable false-alarm cost". Holds only for verbatim canaries, n = 48, three open models, and with a second source present. |
| MAJOR | Alternative explanation | §4.3 l.200; §5 l.236 | `strict_notice` is a cheap rival that is nearly as good for 2 of 3 models. The Discussion should weigh it against taint quarantine directly. |
| MAJOR | Logic | §4.6 l.230 | "Residue follows the executor": with Qwen's well-marked handoffs, Gemma-as-executor reached 71%, **worse** than Gemma alone (50%). That points to a writer × executor interaction, not a pure executor property. Only 4 teams were run, all involving Qwen. Write "mainly". |
| MINOR | Framing | §4.3 l.198 | The early-revoke "finding" holds by construction. |
| MINOR | Cherry-picking risk | Abstract | The abstract's mitigation sentence covers only the best arm. Citation-based quarantine failing for Ministral (60%) is omitted from the abstract. |

**Ignored alternatives.**
- Normalised or semantic taint matching.
- Writer-side mitigation: re-running the writer after revocation, which is cheap and analogous to `early_revoke`.
- Executor-side verification: always re-deriving security-relevant fields.

**Missing stakeholders.** The human escalation queue. Quarantine without a second source moves the load to humans (Qwen escalated in 35% of `nosource_lineage` trials).

**Observations (non-defects).** Deterministic grading, macro-generated numbers and paired caching are exemplary for a sprint paper. Reporting Gemma's 24/24 export *after* the compromise notice is a striking, honest result.

---

## Phase 2: Editorial synthesis and decision

**Consensus across all five seats.**
1. The problem is novel, well motivated and on-agenda.
2. The design is strong: paired, deterministic, controlled.
3. Two claims about taint provenance are inaccurate (C2).
4. The statistics need multiplicity control and clustering acknowledgment.
5. The positioning needs IFC/taint prior work and Safin 2026.

**Points of disagreement.**
- *Is "platform enforcement" over-claimed?* DA: yes, because `strict_notice` is a cheap rival. R3 and the EIC: the claim is defensible because model-dependence is itself the argument, and Ministral ignores even the strict notice (65%). **Adjudication:** keep the conclusion but present the strict notice as a valid cheaper option for some models, and frame platform withholding as the model-independent layer, conditional on locating the content.
- *Is pooling acceptable?* R1 calls it a minor issue. **Adjudication:** keep pooled rates as descriptive.

**DA CRITICAL adjudication.** **Validated.** I reproduced it from the data: `experiments/06_platform_mitigations/results/ministral-3-14b/transcripts/modal-ministral-3-14b__taint_quarantine__3.json` shows a handoff containing "**2,508**" four times, none withheld, and the executor writing `seat_count = 2508`. The statement at l.219 is generated by a circular check (`make_numbers.py` l.556–563). This blocks acceptance until it is corrected. It does not overturn the main result, because 0–2% still holds, but it must be reported honestly. Reported honestly, it becomes a strength: a self-found failure of the paper's own mitigation.

**Decision: MINOR REVISION (bordering on major).** No new experiments are required for acceptance. All Critical items are text or script fixes. One optional cheap experiment (normalised taint) would raise Impact and Execution.

---

## Revision roadmap

### Critical

| # | Location | Problem | Concrete fix |
|---|---|---|---|
| **C1** | `main.tex` l.126 | **Build regression.** Three `\texttt` became a literal TAB followed by `exttt` (`(<TAB>exttt{google/gemma-4-31B-it})`, and likewise for Qwen and Ministral). The PDF predates the edit (PDF 22:09, tex 22:10). The next build will print "exttt…" or drop the model IDs. When gpt-oss is absent, the model list also lacks "and" before Ministral. | Replace each TAB+`exttt` with `\texttt`. Write the list as "…, Qwen3.8 27B (…)\IfN{oss/name}{, Ministral 3 14B (…) and gpt-oss-120b (…)}{ and Ministral 3 14B (…)}". Rebuild and grep the PDF text for "exttt". Find whatever script did the edit (a Python string with an unescaped `\t`) and fix it so the bug does not recur. |
| **C2** | §4.5 l.219 ("no handoff kept any of worker-X's content after withholding"); App. C l.357 ("derived lines were found in every handoff that carried worker-X's content"); `make_numbers.py` l.556–563 | Circular check. "Carried" and "kept" use the same exact match, so reformatted values are invisible. 5 no-citation handoffs (Qwen s15, s39; Ministral s3, s21, s27) carried `2508` as `2,508`. Those lines were not withheld (taint found no line at all in 4 of them). Ministral s3 produced the only `taint_quarantine` residue (and a `taint_lineage` residue). | Replace the sentence with: "Exact-match taint did not withhold the false value in 5 of 144 no-citation handoffs, where the writer had reformatted a seat count (2508→2,508); one of these produced the only residual case under taint quarantine." Change App. C to "…in every handoff that reproduced it verbatim; benign reformatting already defeated it in 5 handoffs". Compute "carried" with digit and punctuation normalisation as well. Optionally rerun taint with normalisation (regex over digits only), which is cheap with the cached handoffs. |
| **C3** | Abstract l.54; §4.4 l.208; §4.5 l.219; §5 l.236; §6 l.241 | "No measurable false-alarm cost" asserts a null without power. Qwen `benign_taint_quarantine` is −10 pp, CI [−30, +9]. | Write "no statistically detectable cost at n = 48 per model (largest drop: Qwen −10 pp, 95% CI −30 to +9)". Add paired-difference CIs to Table 5. |

### Major

| # | Location | Problem | Fix |
|---|---|---|---|
| M1 | Table A.9 (l.264–271); prose throughout §4 | 114 uncorrected tests. 12 claims fail Holm and 4 fail BH. Explicit wrong verdict: "significant for all three models" (l.204; Gemma and Ministral p = 0.03). | Declare a confirmatory family and apply Holm to it. Add an adjusted-p column. Generate the "significant for X" macros from adjusted p. Reword l.204 to "for Qwen; Gemma and Ministral also fell from 12% to 0% (p = 0.03 each, not significant after correction)". |
| M2 | §3.4 l.124–126; §5 Limitations l.238 | Pseudo-replication: 4 near-deterministic repetitions per template × payload cell (Gemma is all-or-nothing in 12/12 cells). | Add a template-clustered permutation or sign test for confirmatory contrasts. Add a sentence: "repetitions within a template–payload cell were often identical; the effective number of independent units is closer to 12 than 48". Add a per-template table in the appendix. |
| M3 | §2 Related Work l.74–80 | Closest prior work and IFC literature missing: Safin 2026 (2609.17648), CaMeL/Foerster 2026 (2601.09923), Ju 2024 (2407.07791), Papadopoulos 2026 (2608.10218). | Add 3–4 sentences. Position taint + quarantine as *information-flow control applied at revocation time*. Distinguish from Safin (containment before execution, not removal after attribution). |
| M4 | §4.2 l.183 → §5 l.236; Conclusion | `strict_notice` is a cheap rival that is not weighed in the Discussion. | Add one sentence in §5: "A notice that names derived content was nearly as effective for Qwen and Gemma (6%, 10%) at no infrastructure cost, but not for Ministral (65%); platform withholding is the layer that does not depend on the model." |
| M5 | §4.6 l.230 | "Residue follows the executor" omits the interaction: Qwen-written, well-marked handoffs gave Gemma 71% against 50% alone. All 4 teams involve Qwen. | Add: "The executor dominated, but writer and executor interact: Gemma acted on Qwen's marked handoffs more often (71%) than on its own (50%)". Keep "mainly". Note that only 4 of the 12 possible pairings were run. |
| M6 | §5 l.236 | "Removing the content was not [model-dependent]" conflicts with `revoke_quarantine` failing for Ministral (60%). | Change to "removing content the platform had located was not". |
| M7 | §4.5 / Table 5 / §5 | The re-derivation dependence (quarantine without a second source drops task success to 0%) is in §4.3 but not tied to the platform recommendation. | Add one sentence in §4.5 or §5 that states the cost and who bears it (the escalation queue). |

### Minor

| # | Location | Problem | Fix |
|---|---|---|---|
| m1 | §4.5 l.219 (rendered p.7, "significant for none of the three models and none of the three models, respectively") | The macro output reads like a stutter. | Write "…was not significant for any model under either design (Table A.9)". |
| m2 | §3.2 l.99 "Each false value … carries a random four-character code" | Untrue for seat counts: the value is `250`+one digit (`scenarios.py` l.69–70), so there are only 9 possible values. | Write "a code derived from the trial seed (four characters; one digit for seat counts)". |
| m3 | §3.4 l.124 | The claim that all ablation runs share a handoff is inaccurate (`early_revoke`, `nocite_*`). | See R1 point 6. |
| m4 | l.153 / Tables A.1–A.4 "False \| wrote" | Conditional on a post-treatment variable. | Mark it descriptive. Do not compare it across conditions. |
| m5 | §4.3 l.198 | The early-revoke result holds by construction. | Reframe it as a check that confirms the mechanism: "as expected". |
| m6 | Tables A.2–A.8 captions | Internal slugs `modal:qwen3.8-27b`, `=>`. | Replace them with HF model IDs. |
| m7 | Figure 2 / Table 3 | The best result (taint quarantine 0–2%) is in no figure. | Add a third panel or a small dumbbell plot: nocite-lineage → taint-quarantine per model. |
| m8 | §4 overall | Dense p-value prose with no worked example. | Add one short boxed example from a transcript, for instance Gemma exporting after the compromise notice, or the 2,508 taint miss. |
| m9 | §5 Limitations l.238 | Missing: exact-match grading undercounts reformatted residue (and task success); one temperature; 8k context. | Add one clause. App. C already says "lower bounds". Link to it. |
| m10 | Page budget | The body ends exactly on p.8. Adding gpt-oss sentences (l.181, l.185) and a fifth column in Table 3 can push it over the limit. | Shorten §4.2 prose (move per-model p-values to Table A.9 references) before adding gpt-oss. |
| m11 | `README.md` (repo) | Trials badge "1,598" against 3,470 in the paper; the Paper badge links `paper/draft.md`; "GPT-6 Luna: 42-44" against 42–45; no exp 06/07 results. Judges clone repos. | Regenerate the README numbers from `numbers.tex`. Link `paper/main.pdf`. |
| m12 | §2 l.76 | "None measures…" | Write "None of these designs measures…". |

---

## Numbers verified against the data

| Claim (location) | Recomputed from `trials.jsonl` | Match |
|---|---|---|
| 3,470 trials, excluding gpt-oss (abstract) | 3,470 | ✓ |
| Pooled residue 76% → 73%, McNemar 10 vs 4, p = 0.18 (§4.1) | 142/188 = 76%, 136/186 = 73%; 10/4, p = 0.180 | ✓ |
| Luna notice 24 vs 0, p = 1.2×10⁻⁷ (§4.2) | 24/0, 1.19×10⁻⁷ | ✓ |
| Pooled retract → lineage 44 vs 1, p = 2.6×10⁻¹² | 44/1, 2.61×10⁻¹² | ✓ |
| Luna read the board in 18 of 42 trials; 10 of those still had residue (§4.1) | 18/42; 10 | ✓ |
| Writers carried the false value into 94% of handoffs | 176/188 = 94%. Exact match only, so a lower bound (reformatted values are missed). | ✓ (lower bound) |
| Pooled clean → benign_lineage task 51% → 50%, 15/14 | ✓ (97/189 and 94/187) | ✓ |
| Mixed teams: 8 of 8 cells closer to the executor | Checked by hand from Table 6 | ✓ |
| "No handoff kept any of worker-X's content" (§4.5) | False in substance: 5 reformatted handoffs kept it; Ministral s3 produced residue | ✗ |
| "Significant for all three models" (§4.3, nosource task) | Nominal only. Gemma and Ministral p = 0.03 fail BH and Holm. | ⚠ |
