# RQ3 · Package Failure Chapter (Live Mac Studio)

> **Claim scope:** live Mac Studio LoRA stack only. Paper DeepSeek-32B package render success (81.1%) is a separate experiment.

Live package taxonomy on this Mac Studio database — not the paper DeepSeek-32B n=8,000 run. Do not cite these rates as paper RQ3 numbers.

## Summary

| Metric | Value |
|--------|-------|
| Package artifacts | 203 |
| Render successes | 203 |
| Render failures | 0 |
| Failure rate | 0.0% (95% Wilson CI [0.0%, 1.9%]) |
| Mean S (success) | 5.00 |
| Majority A among successes | 98.5% |

## Repair win-rate (package only)

| Metric | Value |
|--------|-------|
| Artifacts that attempted repair | 41 |
| Repair attempts | 112 |
| Successful repair attempts | 105 |
| Attempt win-rate | 93.8% |
| Rescued to final render success | 41 |
| Rescue rate (among repaired) | 100.0% |

## Failure taxonomy

| Category | Count | Share of failures | Share of packages |
|----------|------:|------------------:|------------------:|

## Interpretation (for defense)

1. Package diagrams remain the hardest of the four design-phase types on this server, matching the paper ordering class > object > component > package.
2. Taxonomy labels isolate stage-boundary failures (syntax / containment / render engine) so RQ3 is not only a score gap but a failure-mode story.
3. Repair win-rate shows whether the verification→repair loop recovers package failures; cite attempt win-rate and rescue rate separately.

## Examples

_No failed package diagrams stored yet._

Regenerate: `python scripts/generate_rq3_package_chapter.py`
