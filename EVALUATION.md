# CodeSentinel — Evaluation Report

## Methodology

To evaluate CodeSentinel's bug-detection accuracy, 11 bugs were deliberately planted
across 5 Python files in a test repository (`codesentinel-test-repo`), without any
comments or hints revealing the bugs. The agent was then run independently on each
file (via `evaluate.py`), and its output was compared against the known ground truth
(`ground_truth.py`) to calculate Precision and Recall.

## Results Summary

| Metric | Score |
|---|---|
| **Recall** (bugs found / bugs planted) | 10 / 11 (90.9%), or 10.5/11 (~95.5%) counting partial matches |
| **Precision** (correct findings / total findings) | ~100% — no false or fabricated issues found |

## Detailed Comparison

| # | File | Function | Planted Bug | Detected? |
|---|---|---|---|---|
| 1 | todo.py | remove_task | No bounds check on index | ✅ Yes |
| 2 | todo.py | get_first_task | Crashes on empty list | ✅ Yes |
| 3 | todo.py | count_pending | Uses `=` instead of `==` | ✅ Yes |
| 4 | calculator.py | divide | No zero-division guard | ✅ Yes |
| 5 | calculator.py | average | Divide by zero on empty list | ✅ Yes |
| 6 | validators.py | is_valid_task_name | Missing explicit `return False` | ✅ Yes |
| 7 | validators.py | is_valid_priority | No upper-bound / range check | ⚠️ Partial (flagged missing type-check, missed range issue) |
| 8 | validators.py | is_valid_email | Weak validation (length only) | ✅ Yes |
| 9 | storage.py | load_tasks | No error handling for missing file | ✅ Yes |
| 10 | storage.py | delete_task_file | No existence check before deletion | ✅ Yes |
| 11 | main.py | main | Calls divide(10, 0), will crash | ✅ Yes |

## Additional Valid Findings (Beyond Ground Truth)

The agent also surfaced several legitimate issues that were not part of the original
planted bug set, such as:
- Missing type/structure validation in `TodoList.add_task`
- Unused import (`average`) in `main.py`
- Lack of input-type validation across `validators.py` functions

These are not counted as false positives, since manual review confirmed they are
genuine code quality issues — they reflect the agent's ability to generalize beyond
the specific bugs it was tested against.

## Conclusion

CodeSentinel correctly identified 10 out of 11 deliberately planted bugs (with one
partial match), achieving strong recall, and reported zero fabricated or incorrect
issues, indicating high precision. The one partially-missed case (a range-validation
edge case) suggests an area for future prompt refinement.