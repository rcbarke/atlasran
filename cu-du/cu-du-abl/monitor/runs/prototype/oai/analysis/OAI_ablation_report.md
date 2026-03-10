# CU/DU Ablation Post-Processing Report

Generated: 2026-02-23T20:02:23.396484+00:00

## Runs analyzed
- `20260219_172332_ues0` (ue_count=0)
- `20260219_172441_ues1` (ue_count=1)
- `20260219_172959_ues3` (ue_count=3)
- `20260219_173535_ues6` (ue_count=6)
- `20260219_174039_ues12` (ue_count=12)

## Summary

| UEs | UL total (Mbps) | UL/UE (Mbps) | DU CPU mean/p95 (%) | CU CPU mean/p95 (%) | LDPC thread mean/p95 (us) | LDPC cum mean/p95 (us) | LDPC thr/cum events/s |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | NA | NA | 213.53/216.88 | 1.70/2.60 | 79.85/94.46 | 319.41/377.86 | 0.988/3.954 |
| 1 | 113.84 | 113.84 | 329.26/332.28 | 22.68/25.37 | 256.27/262.18 | 1025.07/1048.71 | 1.011/4.043 |
| 3 | 64.27 | 21.42 | 288.06/296.97 | 16.41/17.83 | 260.15/268.52 | 1040.61/1074.09 | 1.016/4.065 |
| 6 | 32.40 | 5.40 | 202.29/209.68 | 8.62/9.37 | 275.29/287.92 | 1101.16/1151.68 | 1.015/4.062 |
| 12 | 15.79 | 1.32 | 152.78/158.90 | 5.54/6.10 | 276.66/296.23 | 1106.63/1184.91 | 1.014/4.056 |

## Key deltas vs baseline (UEs=0)

| UEs | UL total Δ | DU CPU mean Δ | GPU power mean Δ | LDPC mean Δ | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | NA | +54.2% | NA | +220.9% |  |
| 3 | NA | +34.9% | NA | +225.8% |  |
| 6 | NA | -5.3% | NA | +244.7% |  |
| 12 | NA | -28.4% | NA | +246.5% | iperf missing end: 12, iperf warn-prefix: 12 |

## Per-run notes (data quality + errors)

### 20260219_172332_ues0 (UEs=0)

- Missing files: none
- iperf3: files=0 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cpu): threads_assumed=4 thread_n=59 mean/p95_us=79.85/94.46 cum_n=59 mean/p95_us=319.41/377.86 events_per_s(thread/cum)=0.988/3.954
- ZMQ: lines=595 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260219_172441_ues1 (UEs=1)

- Missing files: none
- iperf3: files=1 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cpu): threads_assumed=4 thread_n=60 mean/p95_us=256.27/262.18 cum_n=60 mean/p95_us=1025.07/1048.71 events_per_s(thread/cum)=1.011/4.043
- ZMQ: lines=600 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260219_172959_ues3 (UEs=3)

- Missing files: none
- iperf3: files=3 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cpu): threads_assumed=4 thread_n=60 mean/p95_us=260.15/268.52 cum_n=60 mean/p95_us=1040.61/1074.09 events_per_s(thread/cum)=1.016/4.065
- ZMQ: lines=838 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260219_173535_ues6 (UEs=6)

- Missing files: none
- iperf3: files=6 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cpu): threads_assumed=4 thread_n=60 mean/p95_us=275.29/287.92 cum_n=60 mean/p95_us=1101.16/1151.68 events_per_s(thread/cum)=1.015/4.062
- ZMQ: lines=45 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260219_174039_ues12 (UEs=12)

- Missing files: none
- iperf3: files=12 parse_fail=0 missing_end=12 warn_prefix=12 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cpu): threads_assumed=4 thread_n=60 mean/p95_us=276.66/296.23 cum_n=60 mean/p95_us=1106.63/1184.91 events_per_s(thread/cum)=1.014/4.056
- ZMQ: lines=5 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False
