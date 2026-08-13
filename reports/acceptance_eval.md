# UML acceptance evaluation

Deterministic Stage-1 JSON (heuristic + concept grounding) → PlantUML builder → PlantUML -checkonly → render → UML structure rules → requirement↔UML semantic/traceability. Adaptive repair max 3. VLM scoring is a separate paper gate and is not included here.

```text
Golden regression
Total test cases: 6
Generated successfully: 6/6
PlantUML compiled: 6/6
Syntax valid: 6/6
Rendered: 6/6
UML rule validation: 6/6
Semantic validation: 6/6
Full pipeline accepted: 6/6
Average repair iterations: 0.0
Remaining failures: 0

Benchmark (requirements.txt × 4 types)
Total test cases: 200
Generated successfully: 200/200
PlantUML compiled: 200/200
Syntax valid: 200/200
Rendered: 200/200
UML rule validation: 200/200
Semantic validation: 200/200
Full pipeline accepted: 200/200
Average repair iterations: 0.0
Remaining failures: 0

Negative controls (must reject)
Total negative controls: 5
Correctly rejected: 5/5
False accepts: 0
True-negative rate: 1.0

```
