# System design: 2D mechanical drawing → 3D CAD (V1)

This document is the architecture reference for this repository. Read it before generating or modifying pipeline code. It defines the module boundaries, data contracts, and constraints that all V1 code must respect. See `dev-roadmap.md` for build order and milestones.

## 1. Overview

**Goal:** convert a dimensioned 2D mechanical/engineering drawing (image input) into a 3D solid CAD model, exported as STEP (and GLB for visualization).

**Core hypothesis under test in V1:** a VLM, given a drawing image and an iterative render/compare feedback loop, can reliably produce correct build123d code — without deterministic drawing-understanding machinery (OCR, feature detection, cross-view correlation) in front of it.

## 2. Non-goals for V1

Do not implement these unless a milestone in `dev-roadmap.md` explicitly calls for them:
- OCR / dimension extraction as a separate pipeline stage
- CV-based feature/symbol detection (holes, fillets) as a separate stage
- Cross-view correlation / multi-view geometric reasoning
- A CAD-IR intermediate representation or compiler layer
- Assembly reasoning (multiple components, mounting relationships)
- Any live/native integration with Blender or CAD applications — file-based STEP/GLB export only
- Training or fine-tuning a custom model

If code appears to need one of these to work, stop and flag it — that's a signal for Milestone 6 of the roadmap, not something to silently build.

## 3. Architecture (V1)

```
Drawing (image)
      │
      ▼
     VLM  ───────────────────────────────┐
      │  generates build123d code         │
      ▼                                    │
 Safe executor                             │
      │  runs code in sandbox              │
      ▼                                    │
  STEP model                               │
      │                                    │
      ▼                                    │
   Renderer                                │
      │  produces front/top/side images    │
      ▼                                    │
   Compare                                 │
      │  diffs render vs. original drawing │
      ▼                                    │
  VLM refiner ───────────────────────────┘
      (regenerates code with error context, loops up to N times)
```

Two AI-touching stages (VLM, VLM refiner). Everything else is deterministic and independently testable without any API calls.

## 4. Repository structure

```
project/
├── foundation/            # hand-modeled reference parts (Milestone 0)
├── render/
│   └── harness.py           # STEP -> projection images
├── executor/
│   └── sandbox.py           # safe code execution
├── data/
│   └── seed_drawings/
│       └── {drawing_id}/
│           ├── drawing.png
│           └── ground_truth.step
├── pipeline/
│   ├── vlm_client.py         # VLM prompt construction + calls
│   ├── refine_loop.py        # iteration control
│   └── main.py                 # CLI entrypoint
├── eval/
│   └── harness.py
├── experiments/
│   └── phase2_feasibility/
└── output/
    └── {run_id}/
        ├── model.step
        ├── model.glb
        ├── renders/
        └── report.md
```

## 5. Data contracts

These types are the seams between modules. Keep them stable — every stage downstream depends on the exact shape of the one before it.

### `ExecutionResult` (from `executor/sandbox.py`)
```python
@dataclass
class ExecutionResult:
    success: bool
    step_path: str | None       # populated only if success
    stdout: str
    stderr: str
    exception: str | None       # exception type name, if any
    traceback: str | None
    timed_out: bool
```

### `RenderSet` (from `render/harness.py`)
```python
@dataclass
class RenderSet:
    front: str    # path to image
    top: str
    side: str
    section: str | None = None   # stubbed interface, unused in V1
```

### `ComparisonReport` (from `pipeline/refine_loop.py`)
```python
@dataclass
class ComparisonReport:
    matches: bool
    dimension_mismatches: list[str]   # human-readable diffs, e.g. "hole diameter: expected 40mm, got 35mm"
    visual_mismatch_notes: str | None
    iteration: int
```

### `PipelineRunResult` (from `pipeline/main.py`)
```python
@dataclass
class PipelineRunResult:
    drawing_id: str
    converged: bool
    iterations_used: int
    final_step_path: str | None
    final_glb_path: str | None
    history: list[ExecutionResult]     # one entry per attempt
```

## 6. Component specs

### 6.1 Safe executor (`executor/sandbox.py`)
- Run VLM-generated Python in a subprocess, not in-process — a crash or infinite loop must not take down the caller.
- Restricted imports: allow `build123d` and its dependencies only; block `os`, `subprocess`, `socket`, `open()` outside the designated output directory.
- Hard timeout (default 30s). A timeout is a normal `ExecutionResult` outcome (`timed_out=True`), not an unhandled exception.
- Memory cap appropriate to the environment.
- Return `ExecutionResult` in all cases — never raise out of this module.

### 6.2 Render harness (`render/harness.py`)
- `render(step_path: str, output_dir: str) -> RenderSet`
- Produces standard first-angle orthographic projections: front, top, side. This matches the seed dataset convention and must be kept consistent across the render harness.
- `render_section(step_path: str, plane: ..., output_dir: str) -> str` — interface should exist even though unused in V1, so adding real section support later doesn't require touching call sites.
- Pure function relative to its inputs — given the same STEP file, output should be deterministic.

### 6.3 VLM client (`pipeline/vlm_client.py`)
- Wraps calls to the VLM (Claude) for two distinct purposes — keep these as separate functions even if they share underlying call machinery:
  - `generate_code(drawing_image_path: str) -> str` — first-pass code generation
  - `refine_code(drawing_image_path: str, previous_code: str, error_context: ExecutionResult | ComparisonReport) -> str` — regeneration given feedback
- Prompt must include a condensed build123d API reference/cheat sheet as context — do not rely on the model's parametric memory of the library's exact API surface.
- Output is expected to be a single, directly-executable Python script — no markdown fences, no prose, in the response text; parse defensively (strip fences if present) but the prompt should ask for raw code.

### 6.4 Refine loop (`pipeline/refine_loop.py`)
- `run(drawing_path: str, max_iterations: int = 5) -> PipelineRunResult`
- Sequence per iteration: generate/refine code → safe executor → (if success) render → compare → (if match) stop, else continue with error context
- If the executor fails (invalid code), skip straight to refine with the `ExecutionResult` as error context — don't attempt to render/compare a nonexistent STEP file.
- Log every iteration's code, result, and comparison to `history` — this is also the data source for Milestone 2/4's failure categorization.

### 6.5 Comparison (within `refine_loop.py` or a separate `compare.py` if it grows)
- Two signals, both feeding into `ComparisonReport`:
  - Dimension diff: measure the generated solid's geometry (build123d queries) against whatever dimension data is available for the drawing (initially: none — V1 has no OCR stage, so this may only be checkable against seed dataset ground truth during evaluation, not during live inference)
  - Visual diff: compare rendered projections against the original drawing image — start with a VLM call asking "does this match?", structural similarity metrics are a possible deterministic upgrade later
- `matches = True` requires both signals to agree (or be unavailable and not contradicted)

### 6.6 Evaluation harness (`eval/harness.py`)
- Operates on `PipelineRunResult` + the seed dataset's ground truth, not on live inference — this is offline scoring, not part of the runtime pipeline.
- Metrics: dimensional accuracy (against ground-truth STEP), topological correctness (feature count/type match), convergence rate and iteration distribution across a batch of runs.
- Outputs a markdown report per run and can aggregate across a full seed dataset batch.

## 7. Coding conventions

- Python 3.11+
- Type hints on all public function signatures; use `dataclasses` for the contracts in Section 5 rather than raw dicts
- No bare `except:` — catch specific exceptions, especially in `executor/sandbox.py` where exception handling is the module's entire purpose
- Every module in Section 4 should be independently testable without a live VLM call — mock `vlm_client` functions in tests for `render/`, `executor/`, and `eval/`
- Config (API keys, timeouts, iteration limits) via environment variables or a single `config.py`, not hardcoded in pipeline modules

## 8. Environment & dependencies

- `build123d` (+ its OCP/OpenCascade bindings) — primary CAD library
- Claude API — VLM calls (model choice is swappable; don't hardcode a specific model string deep in logic, keep it in config)
- Render harness likely needs build123d's own export/projection utilities; avoid adding a second, separate CAD library just for rendering

## 9. Known risks / open questions

Carry these forward — do not silently resolve them by picking a default deep in implementation code without flagging it:
- **Projection convention** — the seed dataset and render harness use first-angle projection. This is now the repo-standard convention and should be preserved for all generated orthographic views.
- **Cross-view depth inference** — explicitly out of scope for V1, but if Milestone 2 shows this is the dominant failure mode, it's the hardest item in Milestone 6, not a quick fix.
- **Section views** — `render_section` is a stubbed interface only; no logic for interpreting what a section view in the original drawing represents exists yet.
- **Dataset scarcity** — real dimensioned drawings paired with ground-truth CAD are scarce; the seed dataset leans on synthetic generation (known part → rendered fake blueprint) for this reason.
- **VLM code output reliability** — no assumption should be made that generated code is syntactically valid; the safe executor's structured failure handling is not optional error handling, it's a load-bearing part of the refine loop.
- **Sandbox guarantees and limits** — the sandbox now explicitly strips the parent environment down to a minimal allowlist, blocks dynamic import bypasses via a runtime `__import__` hook, removes `eval`/`exec`/`compile` from the available builtins, and blocks direct filesystem writes outside the output directory while allowing read-only access to the Python/runtime dependency files needed by build123d. This meaningfully closes the accidental/naive cases, including the specific `eval`/`__import__`/aliased-import bypasses covered in regression tests.
- **Not guaranteed by a Python-level namespace sandbox** — this is not a true adversarial sandbox: a deliberately hostile actor can still craft Python that reaches already-loaded modules or object internals (for example by walking `__globals__` or `object.__subclasses__()` to reach code paths that themselves hold references to `os`/`subprocess` without any import statements or calls to `eval`/`exec`/`__import__` in the user script). We do not treat that as a solved problem in V1, and we do not add more denylisting in response — that would be a brittle cat-and-mouse cycle rather than a real isolation boundary.
- **Accepted V1 threat model** — the accepted model is “cooperative AI-generated code that may be buggy or occasionally do something unintended,” not “adversarial code actively trying to break out of a Python-level restricted namespace.” True isolation against the latter requires OS-level sandboxing (containers, seccomp, or similar) and is explicitly deferred, not silently assumed solved.

## 10. Milestone traceability

This document describes the target architecture. `dev-roadmap.md` describes the order to build it in and what "done" means at each step — consult it for acceptance criteria before considering any module in Section 4 complete.
