# 2D Mechanical Drawing to 3D CAD

A V1 research project exploring whether a vision-language model (VLM) can convert dimensioned mechanical drawings into build123d CAD code and valid 3D models.

The planned pipeline is:

```text
Drawing -> VLM -> sandboxed build123d code -> STEP -> orthographic renders
                                                    |
                                                    v
                                              comparison/refinement
```

The project intentionally avoids OCR, computer-vision feature detection, cross-view geometric reasoning, and CAD-IR compilation in V1. Those are conditional follow-up areas, driven by experiment results.

## Current Status

The repository currently contains the deterministic CAD foundation:

- Five hand-modeled reference parts in `foundation/`:
  - flat plate with holes
  - L-bracket
  - cylinder
  - flange
  - stepped shaft
- STEP export helpers for each reference part
- GLB export support for the flat plate
- Deterministic first-angle front, top, and side SVG projections in `render/`
- A subprocess-based restricted executor in `executor/`
- Smoke, renderer, and sandbox tests in `tests/`

The VLM client, seed drawing dataset, comparison/refinement loop, evaluation harness, and end-to-end CLI are not implemented yet. See [dev-roadmap.md](dev-roadmap.md) for the build order and acceptance criteria.

## Milestone History

The Git history contains the initial Milestone 1 commit and subsequent cleanup commits; the later milestone work below is also reflected in the current working-tree diffs and generated artifacts rather than in separate milestone commits.

### Milestone 0: CAD Foundation

Five hand-modeled parts were added with STEP exporters, and GLB export was verified for the flat plate. A later Milestone 1.5 visual review found that several parts described as having holes or bores were actually uncut solids: the cutter planes pointed away from, or outside, the target boxes. The foundation geometry was corrected and the affected volume/topology expectations were updated. This issue originated in the foundation even though the defect was discovered later.

### Milestone 0.5: Render Harness

The renderer produces deterministic first-angle front, top, and side orthographic SVG projections. The adopted convention is documented in the harness and its determinism tests. Section generation was later added for the seed dataset; interpreting section views from unknown drawings remains deferred.

### Milestone 1: Safe Executor

The executor runs generated code in a subprocess with a minimal environment allowlist, restricted runtime imports, timeout and memory limits, and filesystem writes limited to the designated output directory. Review found and resolved parent-environment leakage and replaced an ineffective static import-scanning approach with a runtime `__import__` hook and restricted builtins; regression tests cover runtime `eval` and aliased-import attempts. The module-globals and `object.__subclasses__()` traversal escapes remain documented strict `xfail` cases because Python-level restrictions are not OS isolation and the V1 threat model is cooperative generated code.

The executor also gained STEP round-trip validation: an export is successful only when the re-imported result contains at least one solid. A cold-start timeout regression in the geometry test was measured with temporary timing instrumentation and addressed with a documented longer test timeout.

### Milestone 1.5: Seed Dataset

Eight synthetic seed drawings now cover flat plate, bracket, cylinder, flange, shaft, hole pattern, stepped part, and sectioned part, each with `drawing.png` and `ground_truth.step`. `render_section()` generates a real section profile with hatching for a known solid and cutting plane; interpreting section geometry from an unknown drawing is still deferred.

Visual review found issues that automated checks had missed and resolved them:

- Foundation cutters that pointed away from their target solids, leaving intended holes/bores uncut.
- PNG compositing that dropped SVG circles; `_svg_png()` now handles circles, ellipses, and sampled SVG path segments.
- Independent X/Y scaling that stretched circles into ellipses; compositing now uses uniform scaling with centered letterboxing.
- Section hatching that crossed cavity space; hatching is clipped to closed section-profile loops with an SVG `clipPath`.
- A section-sheet height label overlapping `SECTION (FRONT)`; the label was moved to a clear position.

See [dev-roadmap.md](dev-roadmap.md) for milestone acceptance criteria and [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) for the architecture, contracts, and deferred scope.

## Requirements

- Python 3.11 or newer
- `build123d` and its OpenCascade dependencies
- `pytest` for tests

## Setup

From PowerShell at the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Activate the environment when desired:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The tests build the foundation parts, validate STEP/GLB exports, verify deterministic render output, and exercise sandbox failure handling. Generated caches and outputs are ignored by Git.

## Useful Commands

Generate a foundation STEP file directly:

```powershell
.\.venv\Scripts\python.exe -m foundation.cylinder_part
```

Generate the flat plate STEP and GLB files:

```powershell
.\.venv\Scripts\python.exe -m foundation.flat_plate_with_holes
```

Render a STEP file from Python:

```python
from render.harness import render

views = render("path/to/model.step", "render/output")
print(views.front, views.top, views.side)
```

Run generated build123d code in the executor:

```python
from executor.sandbox import run_code_in_sandbox

result = run_code_in_sandbox(code, output_dir="sandbox-output")
```

## Repository Layout

```text
foundation/     Hand-modeled reference parts and export helpers
render/         STEP to deterministic orthographic projection rendering
executor/       Restricted subprocess execution for generated code
tests/          Automated tests for the current deterministic modules
SYSTEM_DESIGN.md
                Architecture, contracts, constraints, and threat model
dev-roadmap.md  Milestones and acceptance criteria
```

## Sandbox Scope

The executor is designed for cooperative, potentially buggy AI-generated code. It runs code in a subprocess, applies a timeout and memory limit, restricts imports, blocks network access, and limits filesystem writes to the designated output directory.

It is not an adversarial security boundary. Deliberately hostile Python may still reach already-loaded modules or object internals. True isolation requires an OS-level sandbox such as a container or seccomp-based policy and is outside the V1 scope.

## Design References

- [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md) - architecture and module contracts
- [dev-roadmap.md](dev-roadmap.md) - milestone plan and project progress
