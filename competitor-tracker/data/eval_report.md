# Competitor Tracker Evaluation Report

- **Date**: 2026-11-24T08:33:43.368870+00:00
- **Split**: `dev` (26 cases)
- **Dry Run**: `False`
- **Prompt Hash (SHA-256)**: `ad466be094c6ffc8862cf72194ff821ca37aef398359529cf78e23cf6b9c4088`

## Per-Ablation Metrics

| Ablation | Precision | Recall | F1 | Threat Accuracy | False Alerts | Invalid Evidence | Parse Failures | LLM Calls / Event | Avg Tokens / Event |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `full` | 1.000 | 1.000 | 1.000 | 0.900 | 0 | 0 | 0 | 0.00 | 1444.2 |
| `no_classifier` | 0.385 | 1.000 | 0.556 | 0.800 | 13 | 2 | 1 | 0.04 | 1572.9 |
| `single_agent` | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1 | 1 | 0.04 | 1823.1 |

## Paired Comparison (full vs. single_agent)

- **False Alerts Delta (`full - single_agent`)**: 0
- **Classifier F1 Delta (`full - single_agent`)**: 0.0

## Threat Confusion Matrices (True Launches)

### `full`

| Actual \ Predicted | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|
| **HIGH** | 3 | 0 | 0 |
| **MEDIUM** | 0 | 3 | 1 |
| **LOW** | 0 | 0 | 3 |

### `no_classifier`

| Actual \ Predicted | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|
| **HIGH** | 3 | 0 | 0 |
| **MEDIUM** | 0 | 2 | 2 |
| **LOW** | 0 | 0 | 3 |

### `single_agent`

| Actual \ Predicted | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|
| **HIGH** | 3 | 0 | 0 |
| **MEDIUM** | 0 | 4 | 0 |
| **LOW** | 0 | 0 | 3 |

## Interpretation

On the `dev` split (26 labeled cases), the `full` multi-agent pipeline recorded 0 false alert(s) compared with 13 when removing the Classifier (`no_classifier`) and 0 under the collapsed `single_agent` baseline (Classifier F1 1.000 vs 1.000). Enforcing an isolated Classifier gate and deterministic verbatim evidence checks prevents non-launch noise from reaching strategic action logs.
