# Judging Engine & Scoring Architecture — DOGFOOD 2026

## 1. Overview & Objectives

In competitive hackathons, judging is inherently subject to variance:
- **Harsh vs. Generous Judges**: An 8/10 from a strict judge may represent a superior project to a 10/10 from an overly lenient judge.
- **Sparse Assignments**: Not every judge evaluates every project.
- **Incomplete Batches**: Judges may drop out before reviewing all allocated submissions.

This document details the judging architecture, confidentiality safeguards, rubric weighting, and the mathematical normalization models designed for Tier 2 and beyond.

---

## 2. Rubric & Criteria Weighting

Organizers configure weighted evaluation criteria per track or event:

$$\text{RawScore}(p, j) = \sum_{c \in C} w_c \cdot s_{p, j, c}$$

Where:
- $p$ is the project, $j$ is the judge.
- $C$ is the set of criteria (e.g., *Functionality*, *Technical Quality*, *Design*, *Novelty*).
- $w_c \in [0, 1]$ is the organizer-assigned criterion weight with $\sum w_c = 1$.
- $s_{p, j, c} \in [1, 5]$ is the discrete rubric score.

---

## 3. Judge Isolation & Confidentiality Threat Model

### Confidentiality Invariant
> **No judge shall ever have access to another judge's raw scores, comments, or evaluations prior to public results publication.**

### Attack Surface & Mitigations
1. **API Parameter Tampering (`/api/judge/scores?judge=jdg_a`)**:
   - *Threat*: Judge B crafts a request substituting Judge A's identifier.
   - *Mitigation*: The session token is resolved server-side. The endpoint strictly verifies `authenticated_judge_id == target_judge_id`. Any cross-judge inquiry returns `HTTP 403 Forbidden`.
2. **Participant Privilege Escalation**:
   - *Threat*: Registered participants attempt to read judging queues or scorecards.
   - *Mitigation*: Endpoint permissions enforce `EventRole.JUDGE`. All non-judge requests return `HTTP 403 Forbidden`.
3. **Database Row Level Security (RLS)**:
   - PostgreSQL RLS policies restrict `SELECT` queries on `scores` to `auth.uid() = judge_id` or `auth.is_organizer()`.

---

## 4. Score Normalization Proof & Mathematical Formulation

To neutralize the "harsh vs. generous judge" anomaly, the platform incorporates **Z-Score Normalization** across judge scoring distributions.

### Standardized Z-Score Formulation
For each judge $j$ who scored $N_j$ projects:

$$\mu_j = \frac{1}{N_j} \sum_{i=1}^{N_j} \text{RawScore}(p_i, j)$$

$$\sigma_j = \sqrt{\frac{1}{N_j} \sum_{i=1}^{N_j} (\text{RawScore}(p_i, j) - \mu_j)^2 + \epsilon}$$

Where $\epsilon = 10^{-6}$ prevents division by zero when a judge awards identical scores across their entire batch.

The normalized score assigned by judge $j$ to project $p$ is:

$$Z(p, j) = \frac{\text{RawScore}(p, j) - \mu_j}{\sigma_j}$$

### Global Projection
To project Z-scores back onto a human-readable scale $[0, 100]$:

$$\text{FinalScore}(p) = \frac{1}{|J_p|} \sum_{j \in J_p} \left( 50 + 15 \cdot Z(p, j) \right)$$

Where $J_p$ is the set of judges who evaluated project $p$.

### Mathematical Invariants & Proof of Fairness
1. **Zero-Mean Invariant**: For every judge $j$, $\sum_p Z(p, j) = 0$. Lenient judges and harsh judges are centered on the identical mean.
2. **Unit Variance Invariant**: $\text{Var}(Z(\cdot, j)) = 1$. The spread and confidence of each judge's opinions are equally weighted.
3. **Monotonicity**: If judge $j$ scores $p_1 > p_2$, then $Z(p_1, j) > Z(p_2, j)$ strictly holds.

---

## 5. Pairwise Bradley-Terry Comparative Engine (Bonus Challenge)

In addition to scalar scoring, the system supports a **pairwise comparison model** using the **Bradley-Terry probability framework**:

$$P(p_A \succ p_B) = \frac{e^{\theta_A}}{e^{\theta_A} + e^{\theta_B}}$$

Where $\theta_p$ represents the latent latent skill rating of project $p$.
Maximum Likelihood Estimation (MLE) converges to an optimal ranking even under sparse, incomplete judge coverage where judges compare heads-up pairs rather than filling numerical cards.

---

## 6. Organizer CSV Export Specification

The organizer export route (`GET /api/export.csv`) compiles the complete judging dataset:

```csv
project_id,project_title,track,team_name,judge_count,raw_avg,normalized_score,rank
prj_01,Quiet Hours,Developer tools,Nightshift,3,3.67,78.4,1
prj_02,Local First Sync,Developer tools,Solo,2,3.50,75.1,2
```
