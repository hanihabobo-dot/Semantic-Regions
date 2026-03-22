# PhD direction: online neuro-symbolic planning + RWTH context

This note collects brainstorming for a possible PhD after the **Semantic Boxels** MA work, plus **recent research at RWTH Aachen** (especially i6, KBSG, Till Hofmann, Daniel Swoboda, Tim Niemüller) and **how to access** theses and papers.

**Last updated:** 2026-03-18

---

## 1. Your intuition (unpacked)

The idea maps onto an active area: **neuro-symbolic planning with learned representations**.

| Phrase | Meaning |
|--------|---------|
| **General planning** | Domain-independent symbolic planning (PDDL/STRIPS), not tied only to Panda / boxels / tabletop |
| **Online learning** | The planner’s symbolic model grows **during** execution, not only trained offline then frozen |
| **New atoms + relationships** | **Predicate invention** — new propositions and how they relate (preconditions, effects, co-occurrence) to existing symbols |
| **SOTA open-source autoencoder** | Often a **discrete** model (VQ-VAE, Gumbel-Softmax VAE, Latplan-style SAE) whose latent codes map to symbolic propositions |

---

## 2. How this connects to the MA (Semantic Boxels)

| MA (fixed symbols) | PhD direction (learned + growing) |
|--------------------|-------------------------------------|
| Hand-crafted predicates: `is_shadow`, `blocks_view_at`, `obj_at_boxel` | Predicates discovered or refined from observations |
| Static `BoxelRegistry` at scene init | Registry or symbol set can grow online |
| Fixed types: OBJECT, SHADOW, FREE_SPACE | New abstractions emerge from learned clusters |
| Reactive replanning on failure | Replanning **plus** vocabulary expansion when failure signals missing concepts |
| PDDLStream + fixed domain | Evolving domain (new predicates between replans) |

---

## 3. Core PhD thesis sketch

**Working title:** *Online symbol grounding and predicate invention for classical planning via discrete latent representations*

**One sentence:** A TAMP / planning agent discovers new symbolic atoms from raw observations using a discrete autoencoder, learns their relationships to existing atoms from execution traces, and integrates them into its PDDL (or related) model **online**, so open-world settings where the initial vocabulary is insufficient become tractable.

### Research questions (candidates)

1. Can VQ-VAE / discrete codebook entries serve as **meaningful** planning propositions?
2. On planning or execution failure, can we detect **missing vocabulary** and expand the codebook?
3. From (state, action, next-state) traces, can we learn precondition/effect links for new atoms?
4. Convergence / soundness: does the symbol set stabilize? Are learned action models sound enough for planning?

### Online loop (high level)

1. Plan with current symbolic domain  
2. Execute  
3. Encode new observations  
4. Detect novelty (high reconstruction error, new codes, repeated failure)  
5. Expand codebook / invent predicates  
6. Learn relationships w.r.t. existing atoms  
7. Update domain and replan  

---

## 4. Related work (beyond RWTH)

- **Latplan / SAE** (Asai & Fukunaga): images → PDDL; largely **offline**  
- **VisualPredicator** (2024): online predicate invention from images  
- **CLIMB** (ICRA 2025): continual PDDL building; often LLM-centric  
- **Dynamic predicate invention** (e.g. meta-interpretive learning): online symbolic repair; different from neural autoencoder grounding  
- **VQ models for planning** (e.g. Ozair et al., latent action codes)  
- **RLeap** (Geffner): learning symbolic models from traces / structure — see §5  

**Possible niche:** online predicate invention **grounded in discrete neural representations** (not only LLMs or pure ILP).

---

## 5. RWTH Aachen: institutes and focus

### 5.1 Chair of Machine Learning and Reasoning (i6) — Prof. Hector Geffner

- **Site:** [ml.rwth-aachen.de](https://ml.rwth-aachen.de/)  
- **Theme:** integration of **learning and reasoning**; representation learning for **planning**; symbolic models from data where hand-crafting does not scale  
- **ERC project RLeap:** “Representation Learning for Acting and Planning” (2020–2025); Geffner moved to RWTH ~2023  
- **RLeap goals (summary):** learn **first-order symbolic** representations from raw perceptions without prior symbolic knowledge; bridge deep learners and model-based planners  
- **Publications hub:** [rleap-project.github.io/publications](https://rleap-project.github.io/publications/index.html) — many papers have **arXiv** versions  

#### RWTH / RLeap papers especially relevant to MA + PhD direction

| Paper | Venue / year | Why it matters |
|-------|----------------|----------------|
| **Combined Task and Motion Planning via Sketch Decompositions** | ICAPS 2024 | Sketch-based **TAMP**; interleaved task + motion; [arXiv:2403.16277](https://arxiv.org/abs/2403.16277) |
| **Learning Sketch Decompositions in Planning via Deep Reinforcement Learning** | IJCAI 2025 (Aichmüller, Geffner) | RL for sketch structure |
| **Learning Lifted STRIPS Models from Action Traces Alone** | ICAPS 2025 (Gösgens, Jansen, Geffner) | [arXiv:2411.14995](https://arxiv.org/abs/2411.14995) |
| **Learning Generalized Policies for Fully Observable Non-Deterministic Planning Domains** | IJCAI 2024 (**Till Hofmann**, Geffner) | FOND / generalized policies |
| **Learning First-Order Symbolic Planning Representations That Are Grounded** | ICAPS 2022 workshop | Grounded symbolic models |
| **Target Languages (vs. Inductive Biases) for Learning to Act and Plan** | AAAI 2022 (Geffner) | [arXiv:2109.07195](https://arxiv.org/abs/2109.07195) |

Software mentioned on i6 pages includes tools such as **Mimir**, **DLPlan**, **Plangolin** (see [ml.rwth-aachen.de/software](https://ml.rwth-aachen.de/software/)).

### 5.2 Knowledge-Based Systems Group (KBSG) — Prof. Gerhard Lakemeyer

- **Site:** [kbsg.rwth-aachen.de](https://www.kbsg.rwth-aachen.de/)  
- **Focus:** knowledge representation, cognitive robotics, planning and execution  

---

## 6. People you named: theses and roles

### 6.1 Till Hofmann

- **PhD thesis:** *Towards Bridging the Gap between High-Level Reasoning and Execution on Robots*  
- **Supervisor:** Gerhard Lakemeyer (KBSG); affiliation evolved toward i6 postdoc  
- **Abstract (summary):** High-level planners treat actions as atomic with deterministic effects; real execution has multi-step structure, temporal constraints, noise, and sensing errors. The thesis proposes ways to **close the reasoning–execution gap**.  
- **Open access:**  
  - **arXiv:** [2401.00880](https://arxiv.org/abs/2401.00880) — full thesis PDF  
  - **RWTH DOI:** 10.18154/RWTH-2023-10508  
- **Relevance to Semantic Boxels:** Strong overlap with audit themes (PDDL vs physical drift, hidden sub-actions in sense/pick/place, symbolic/physical desync).

### 6.2 Tim Niemüller

- **PhD thesis (2024):** *Planning and execution for mobile robots using distributed persistent memory*  
- **Advisors:** Gerhard Lakemeyer, Siddhartha Srinivasa  
- **Keywords:** task planning, task execution, goal reasoning, knowledge-based systems, robotics  
- **Open access:** RWTH Publications — record [981068](https://publications.rwth-aachen.de/record/981068), direct PDF link on that page  
- **Summary:** Document-oriented distributed robot memory (e.g. MongoDB), middleware integration, goal-reasoning executive (CLIPS-based), multi-robot coordination; demos in domestic service and factory logistics.

### 6.3 Daniel Swoboda

- **Role:** Researcher at i6; **M.Sc.**; doctoral track / “Doctoral Researcher” in some listings — **verify current degree** on official RWTH pages.  
- **Themes:** multi-agent goal reasoning, Carologistics RoboCup, TAMP-related topics (e.g. skill execution + domain grounding).  
- **Example earlier work:** bachelor’s / student work on promises and requests in multi-agent goal reasoning (with Till Hofmann as advisor context in bibliographic records).  
- **For a full publication list:** [Google Scholar / institute pages](https://scholar.google.com) — search “Daniel Swoboda RWTH”.

---

## 7. Positioning your PhD idea vs RWTH lines

| Your idea | Closest RWTH work | Relation |
|-----------|-------------------|----------|
| Online learning of atoms / predicates | RLeap, lifted STRIPS from traces | RWTH emphasizes learning from traces / structure; **online expansion during deployment** can be positioned as an extension |
| Autoencoder → atoms | RLeap “from perceptions”; Latplan-style work (global literature) | Combining **discrete AEs** with RWTH-style **planning theory** could be distinctive |
| Planner creates atoms + relations | Learning lifted STRIPS, grounded representations | Add **incremental** domain update and **perceptual** grounding |
| General planning beyond one robot demo | General policies, sketches, TAMP via sketches | Natural alignment with i6; your MA is a concrete TAMP testbed |

---

## 8. Access, paywalls, and practical tips

| Resource | Access |
|----------|--------|
| **Till Hofmann thesis** | **Free** on arXiv (2401.00880) |
| **Tim Niemüller thesis** | **Free** PDF on `publications.rwth-aachen.de` |
| **RLeap / Geffner group** | Prefer **arXiv** links from [RLeap publications](https://rleap-project.github.io/publications/index.html) |
| **ICAPS / AAAI / IJCAI** publisher PDFs | May need **institutional login**; use arXiv preprint when available |
| **RWTH PhD theses** | Search [PhD thesis collection](https://publications.rwth-aachen.de/collection/PhDThesis?as=1&ln=en) — many records include open PDFs |

**If a paper is paywalled:** check arXiv, OpenReview, author homepages, and Google Scholar “All versions”. RWTH students should use the **university library** for licensed publisher access.

---

## 9. Suggested reading order (RWTH-heavy)

1. Geffner — *Target Languages for Learning to Act and Plan* (AAAI 2022 / arXiv)  
2. Hofmann — thesis on arXiv (reasoning vs execution)  
3. *Combined TAMP via Sketch Decompositions* (ICAPS 2024 / arXiv)  
4. Gösgens et al. — *Learning Lifted STRIPS Models from Action Traces Alone* (ICAPS 2025 / arXiv)  
5. Niemüller thesis (goal reasoning + persistent memory) if multi-robot / long-horizon execution matters  

---

## 10. Disclaimer

Institutional affiliations, project names, and publication lists change. **Confirm** advisors, open PhD calls, and co-supervision rules on official RWTH / i6 / KBSG pages before applications.

This document is **notes for planning**, not a formal proposal.
