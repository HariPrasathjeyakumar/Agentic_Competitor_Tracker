# Competitor Tracker Evaluation Report

- **Date**: 2026-11-23T13:58:43.882637+00:00
- **Split**: `dev` (26 cases)
- **Dry Run**: `True`
- **Prompt Hash (SHA-256)**: `1fbd1edc4c1ef3309af5ed05903782d0bd8f6179f8ef688f72a6cc2c722b3275`

## Per-Ablation Metrics

| Ablation | Precision | Recall | F1 | Threat Accuracy | False Alerts | Invalid Evidence | Parse Failures | LLM Calls / Event | Avg Tokens / Event |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `full` | 1.000 | 1.000 | 1.000 | 0.400 | 0 | 9 | 0 | 1.42 | 1326.6 |
| `no_classifier` | 0.385 | 1.000 | 0.556 | 0.400 | 16 | 9 | 0 | 1.65 | 946.8 |
| `single_agent` | 0.909 | 1.000 | 0.952 | 0.400 | 1 | 9 | 0 | 1.00 | 632.0 |

## Paired Comparison (full vs. single_agent)

- **False Alerts Delta (`full - single_agent`)**: -1
- **Classifier F1 Delta (`full - single_agent`)**: 0.0476

## Threat Confusion Matrices (True Launches)

### `full`

| Actual \ Predicted | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|
| **HIGH** | 0 | 3 | 0 |
| **MEDIUM** | 0 | 4 | 0 |
| **LOW** | 0 | 3 | 0 |

### `no_classifier`

| Actual \ Predicted | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|
| **HIGH** | 0 | 3 | 0 |
| **MEDIUM** | 0 | 4 | 0 |
| **LOW** | 0 | 3 | 0 |

### `single_agent`

| Actual \ Predicted | HIGH | MEDIUM | LOW |
|---|---:|---:|---:|
| **HIGH** | 0 | 3 | 0 |
| **MEDIUM** | 0 | 4 | 0 |
| **LOW** | 0 | 3 | 0 |

## Interpretation

On the `dev` split (26 labeled cases), the `full` multi-agent pipeline recorded 0 false alert(s) compared with 16 when removing the Classifier (`no_classifier`) and 1 under the collapsed `single_agent` baseline (Classifier F1 1.000 vs 0.952). Enforcing an isolated Classifier gate and deterministic verbatim evidence checks prevents non-launch noise from reaching strategic action logs.
