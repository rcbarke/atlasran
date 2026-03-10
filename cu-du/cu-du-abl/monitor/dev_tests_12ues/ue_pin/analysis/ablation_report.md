# CU/DU Ablation Post-Processing Report

Generated: 2026-02-18T21:09:16.559780+00:00

## Runs analyzed
- `20260218_140408_ues0` (ue_count=0)
- `20260218_140549_ues1` (ue_count=1)
- `20260218_141150_ues3` (ue_count=3)
- `20260218_142642_ues6` (ue_count=6)
- `20260218_143506_ues12` (ue_count=12)

## Summary

| UEs | UL total (Mbps) | UL/UE (Mbps) | DU CPU mean/p95 (%) | CU CPU mean/p95 (%) | LDPC mean/p95 (us) | LDPC events/s | GPU util mean/p95 (%) | GPU power mean/p95 (W) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | NA | NA | 211.81/214.99 | 1.95/2.72 | 154.02/154.35 | 0.067 | 0.55/3.00 | 11.46/12.12 |
| 1 | 101.67 | 101.67 | 355.44/360.45 | 19.76/21.55 | 320.88/362.75 | 1.300 | 44.38/49.30 | 38.08/39.48 |
| 3 | 65.60 | 21.87 | 325.04/334.06 | 16.04/17.34 | 346.83/356.46 | 0.836 | 32.59/35.00 | 30.24/31.48 |
| 6 | 32.72 | 5.45 | 232.48/242.06 | 9.22/11.04 | 379.05/426.97 | 0.445 | 19.11/24.00 | 21.81/22.93 |
| 12 | 16.42 | 1.37 | 177.97/188.65 | 5.94/6.88 | 386.65/429.71 | 0.242 | 11.24/14.00 | 17.73/19.30 |

## Key deltas vs baseline (UEs=0)

| UEs | UL total Δ | DU CPU mean Δ | GPU power mean Δ | LDPC mean Δ | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | NA | +67.8% | +232.2% | +108.3% |  |
| 3 | NA | +53.5% | +163.9% | +125.2% |  |
| 6 | NA | +9.8% | +90.3% | +146.1% |  |
| 12 | NA | -16.0% | +54.7% | +151.0% | iperf missing end: 12, iperf warn-prefix: 12 |

## Per-run notes (data quality + errors)

### 20260218_140408_ues0 (UEs=0)

- Missing files: none
- iperf3: files=0 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC decode: n=4 mean_us=154.02 p95_us=154.35 max_us=154.37 events_per_s=0.067
- ZMQ: lines=595 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260218_140549_ues1 (UEs=1)

- Missing files: none
- iperf3: files=1 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC decode: n=77 mean_us=320.88 p95_us=362.75 max_us=427.80 events_per_s=1.300
- ZMQ: lines=595 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260218_141150_ues3 (UEs=3)

- Missing files: none
- iperf3: files=3 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC decode: n=50 mean_us=346.83 p95_us=356.46 max_us=358.34 events_per_s=0.836
- ZMQ: lines=838 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260218_142642_ues6 (UEs=6)

- Missing files: none
- iperf3: files=6 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC decode: n=26 mean_us=379.05 p95_us=426.97 max_us=445.76 events_per_s=0.445
- ZMQ: lines=45 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260218_143506_ues12 (UEs=12)

- Missing files: none
- iperf3: files=12 parse_fail=0 missing_end=12 warn_prefix=12 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC decode: n=13 mean_us=386.65 p95_us=429.71 max_us=431.28 events_per_s=0.242
- ZMQ: lines=5 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False
