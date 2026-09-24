# Development roadmap — 2D mechanical drawing → 3D CAD (V1)

## Guiding philosophy
Prove the core hypothesis before building infrastructure around it. The question V1 exists to answer:

> **Can a VLM, given a dimensioned mechanical drawing and an iterative render/compare feedback loop, reliably produce a correct build123d/STEP model — without any deterministic drawing-understanding machinery (OCR, feature detection, cross-view correlation) in front of it?**

Every milestone below either builds toward running that experiment, or expands the system *in response to* what the experiment shows fails — not in anticipation of it. Do not build Milestone 6's sub-items until Milestone 2/4 data tells you which ones you actually need.

---

## Milestone 0 — CAD foundation
**Goal:** confirm the tooling works before any AI touches it.

- [ ] Set up Python environment with `build123d` + OCP bindings
- [ ] Hand-model 5 test parts covering the target part families: flat plate with holes, L-bracket, cylinder, flange, stepped shaft
- [ ] Export each to STEP; open in a viewer (FreeCAD, or any online STEP viewer) to confirm validity
- [ ] Confirm `export_gltf()` works for at least one part (this is the Blender-facing export path)

**Deliverable:** `foundation/` — hand-written build123d scripts + their STEP/GLB outputs
**Exit criteria:** 5/5 parts model and export cleanly, no manual fixes needed

---

## Milestone 0.5 — Render harness
**Goal:** a reusable function that turns any STEP model into comparison-ready images. Every later milestone depends on this.

- [ ] `render(step_path) -> {front, top, side}` producing orthographic projection images
- [ ] Stub a `render_section(step_path, plane) -> image` even if unused in V1 — the interface should exist so section-view support isn't a rearchitecture later
- [ ] Verify against Milestone 0's 5 parts — renders should be visually recognizable as the part

**Deliverable:** `render/harness.py`
**Exit criteria:** given any of the Milestone 0 STEP files, produces 3 projection images automatically, no manual steps

---

## Milestone 1 — Safe executor
**Goal:** run VLM-generated code without trusting it.

- [ ] Sandboxed subprocess execution: restricted builtins, no filesystem access outside a designated output dir, no network access, hard timeout (e.g. 30s), memory cap
- [ ] Structured result: `{success, step_path, stdout, stderr, exception, traceback}` — the refine loop (Milestone 4) needs this structure to diagnose failures
- [ ] Fails safe: a timeout, crash, or resource violation is a normal, expected result type, not an unhandled exception

**Deliverable:** `executor/sandbox.py`
**Exit criteria:** executes arbitrary syntactically-valid build123d scripts in isolation; a deliberately broken script (infinite loop, bad import, invalid geometry) returns a clean structured failure, not a crash of the harness itself

---

## Milestone 1.5 — Seed dataset
**Goal:** 8–10 real or synthetic drawings to run every experiment against.

- [x] Cover these categories, one drawing each: flat plate, bracket, cylinder, flange, shaft, hole pattern, stepped part, sectioned part
- [x] Prefer synthetic generation where real drawings aren't available: hand-model a known part (Milestone 0 style), render its orthographic views back out with dimension annotations — this gives you ground-truth STEP for free, which real scanned drawings don't
- [x] Each drawing gets a ground-truth STEP file alongside it, even if hand-modeled and imperfect

**Deliverable:** `data/seed_drawings/` — `{drawing_id}/drawing.png` + `{drawing_id}/ground_truth.step`
**Exit criteria:** 8–10 labeled pairs, spanning the category list above

---

## Milestone 2 — VLM feasibility experiment
**Goal:** answer the core hypothesis question. This is the most important milestone in the roadmap — it decides what Milestones 6+ actually contain.

- [ ] For each seed drawing: VLM(drawing image) → build123d code → safe executor → STEP → render
- [ ] Manually compare each render against the original drawing
- [ ] Categorize every failure into one of: dimension-misread, feature-missed, depth/view-inference-wrong, invalid-code, visually-close-but-wrong
- [ ] Tally failure categories across all 8–10 drawings

**Deliverable:** `experiments/phase2_feasibility/` notebook + a failure log (one row per drawing: category, notes)
**Exit criteria:** every seed drawing has a categorized outcome; you can state which failure category is most common

---

## Milestone 3 — Minimal end-to-end V1 loop
**Goal:** package Milestone 2's manual experiment into a runnable pipeline, no auto-refinement yet.

- [ ] Single CLI entrypoint: `python main.py --input drawing.png --output out/`
- [ ] Wires: drawing → VLM → build123d code → safe executor → STEP → render → write outputs to disk
- [ ] No comparison/refinement logic yet — output is for human review

**Deliverable:** working CLI pipeline
**Exit criteria:** runs on all seed drawings without crashing; produces STEP + render images per drawing

---

## Milestone 4 — Closed-loop refinement
**Goal:** the cad3dify-style self-correction loop.

- [ ] Compare stage: dimension diff (parse expected dimensions from the drawing or a lightweight structured note, compare to measured geometry) + visual diff (structural similarity or a VLM-based "does this match?" call) between rendered output and original drawing
- [ ] Refiner: given a mismatch report, VLM regenerates code (not from scratch — sees the previous code + the diagnosed error)
- [ ] Loop up to N iterations (start with N=5), logging every attempt's code, render, and diff
- [ ] Track per-drawing: iterations to converge, or "did not converge" if N is exhausted

**Deliverable:** `pipeline/refine_loop.py`
**Exit criteria:** convergence stats across the full seed dataset — iteration count distribution, overall convergence rate

---

## Milestone 5 — Evaluation harness
**Goal:** move from "looks right" to measured accuracy.

- [ ] Dimensional accuracy: compare generated STEP's measured dimensions (via build123d geometry queries) against ground truth
- [ ] Topological correctness: feature count/type match (holes, fillets present and roughly correctly placed)
- [ ] Convergence stats (from Milestone 4) folded into the same report
- [ ] Output a single scorecard per pipeline run

**Deliverable:** `eval/harness.py` + generated `eval/report.md` per run
**Exit criteria:** running the harness against any pipeline output produces a scorecard without manual measurement

---

## Milestone 6 — Evidence-driven expansion (conditional)
**Do not start this milestone until Milestone 2 and Milestone 4 have produced failure data.** Which sub-items you build depends entirely on what that data shows:

- If **dimension-misread** dominates → add an OCR + dimension-association stage in front of the VLM call
- If **feature-missed** dominates → add a CV/detection stage for holes, fillets, chamfers
- If **depth/view-inference-wrong** dominates → this is the cross-view correlation problem flagged as the hardest part of the whole project — budget real time here, don't treat it as a quick add-on
- If **invalid-code** dominates → strengthen the safe executor's error feedback to the VLM (better stack trace summarization, retry-with-context)
- If **visually-close-but-wrong** dominates → the compare stage (Milestone 4) needs a better diff signal, likely dimension-diff over visual-diff

Only after this milestone — and only if direct VLM→code generation is confirmed to be *the* bottleneck rather than upstream drawing understanding — does introducing a CAD-IR intermediate representation + compiler layer become worth its added engineering cost. That is a v2 decision, not a v1 task.

---

## Milestone 7 — Output packaging
- [ ] Bundle STEP + GLB (`export_gltf`) + eval report per run into a consistent output directory structure
- [ ] Verify GLB imports cleanly into Blender
- [ ] Confirm the full pipeline (Milestone 3 + 4) produces this bundle end to end

**Deliverable:** finalized `output/{run_id}/` bundle format
**Exit criteria:** a bundle from any seed drawing opens correctly in Blender with no manual fixes

---

## Explicitly out of scope for V1
- CAD-IR + compiler layer (deferred to v2, conditional on Milestone 6 findings)
- Assembly reasoning / multi-component drawings (deferred to v3, conditional on confirming assemblies are actually in scope)
- Native 3D application integration (stretch goal, file-based STEP/GLB handoff is the intentional seam for this later)
- Section-view semantic understanding beyond the render-harness stub (Milestone 0.5's `render_section` interface exists, but resolving *what* a section view means from the original drawing is deferred)

---

## Suggested repo layout
```
project/
├── foundation/           # Milestone 0 hand-modeled test parts
├── render/                # Milestone 0.5 render harness
├── executor/              # Milestone 1 safe executor
├── data/
│   └── seed_drawings/     # Milestone 1.5
├── experiments/
│   └── phase2_feasibility/# Milestone 2
├── pipeline/
│   ├── vlm_client.py
│   ├── refine_loop.py      # Milestone 4
│   └── main.py              # Milestone 3 CLI entrypoint
├── eval/                   # Milestone 5
└── output/                 # Milestone 7 bundles
```

## Immediate next action
Start Milestone 0. Nothing downstream can be validated until the CAD tooling itself is confirmed working.
