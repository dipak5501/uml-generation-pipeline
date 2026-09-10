# RQ3 · Package Failure Chapter (Live Mac Studio)

> **Claim scope:** live Mac Studio LoRA stack only. Paper DeepSeek-32B package render success (81.1%) is a separate experiment.

Live package taxonomy on this Mac Studio database — not the paper DeepSeek-32B n=8,000 run. Do not cite these rates as paper RQ3 numbers.

## Summary

| Metric | Value |
|--------|-------|
| Package artifacts | 195 |
| Render successes | 186 |
| Render failures | 9 |
| Failure rate | 4.6% (95% Wilson CI [2.4%, 8.5%]) |
| Mean S (success) | 4.99 |
| Mean S (failure) | 0.00 |
| Majority A among successes | 98.4% |

## Repair win-rate (package only)

| Metric | Value |
|--------|-------|
| Artifacts that attempted repair | 40 |
| Repair attempts | 108 |
| Successful repair attempts | 101 |
| Attempt win-rate | 93.5% |
| Rescued to final render success | 38 |
| Rescue rate (among repaired) | 95.0% |

## Failure taxonomy

| Category | Count | Share of failures | Share of packages |
|----------|------:|------------------:|------------------:|
| `render_engine_error` | 9 | 100.0% | 4.6% |

## Interpretation (for defense)

1. Package diagrams remain the hardest of the four design-phase types on this server, matching the paper ordering class > object > component > package.
2. Taxonomy labels isolate stage-boundary failures (syntax / containment / render engine) so RQ3 is not only a score gap but a failure-mode story.
3. Repair win-rate shows whether the verification→repair loop recovers package failures; cite attempt win-rate and rescue rate separately.

## Examples

### `render_engine_error`

- Artifact #68 · S=0.0 · categories=['render_engine_error']

```
@startuml
skinparam monochrome true
skinparam shadowing false
skinparam backgroundColor white
skinparam defaultFontColor black
skinparam ArrowColor black
skinparam ClassBorderColor black
skinparam PackageBorderColor black
skinparam Componen
```

- Artifact #72 · S=0.0 · categories=['render_engine_error']

```
@startuml
skinparam monochrome true
skinparam shadowing false
skinparam backgroundColor white
skinparam defaultFontColor black
skinparam ArrowColor black
skinparam ClassBorderColor black
skinparam PackageBorderColor black
skinparam Componen
```

- Artifact #76 · S=0.0 · categories=['render_engine_error']

```
@startuml
skinparam monochrome true
skinparam shadowing false
skinparam backgroundColor white
skinparam defaultFontColor black
skinparam ArrowColor black
skinparam ClassBorderColor black
skinparam PackageBorderColor black
skinparam Componen
```


Regenerate: `python scripts/generate_rq3_package_chapter.py`
