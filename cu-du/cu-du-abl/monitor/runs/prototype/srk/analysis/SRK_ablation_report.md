# CU/DU Ablation Post-Processing Report

Generated: 2026-02-23T20:23:50.879570+00:00

## Runs analyzed
- `20260218_191943_ues0` (ue_count=0)
- `20260218_192448_ues1` (ue_count=1)
- `20260218_192836_ues3` (ue_count=3)
- `20260218_193305_ues6` (ue_count=6)
- `20260218_193808_ues12` (ue_count=12)

## Summary

| UEs | UL total (Mbps) | UL/UE (Mbps) | DU CPU mean/p95 (%) | CU CPU mean/p95 (%) | LDPC thread mean/p95 (us) | LDPC cum mean/p95 (us) | LDPC thr/cum events/s | GPU util mean/p95 (%) | GPU power mean/p95 (W) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | NA | NA | 208.90/211.02 | 1.92/2.20 | 208.65/222.09 | 208.65/222.09 | 0.571/0.571 | 1.32/2.30 | 11.83/12.23 |
| 1 | 101.20 | 101.20 | 346.57/348.92 | 20.51/21.84 | 322.55/360.40 | 322.55/360.40 | 1.287/1.287 | 45.43/50.00 | 37.54/39.10 |
| 3 | 64.82 | 21.61 | 326.69/347.02 | 16.63/18.17 | 319.22/344.05 | 319.22/344.05 | 0.827/0.827 | 28.33/33.90 | 28.91/30.40 |
| 6 | 32.78 | 5.46 | 224.35/235.22 | 9.22/11.08 | 342.61/386.26 | 342.61/386.26 | 0.445/0.445 | 15.70/20.00 | 20.89/22.04 |
| 12 | 16.76 | 1.40 | 175.38/182.50 | 5.98/7.16 | 337.65/377.38 | 337.65/377.38 | 0.245/0.245 | 8.71/13.30 | 16.58/17.55 |

## Key deltas vs baseline (UEs=0)

| UEs | UL total Δ | DU CPU mean Δ | GPU power mean Δ | LDPC mean Δ | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | NA | +65.9% | +217.2% | +54.6% |  |
| 3 | NA | +56.4% | +144.3% | +53.0% |  |
| 6 | NA | +7.4% | +76.5% | +64.2% |  |
| 12 | NA | -16.0% | +40.1% | +61.8% | iperf missing end: 12, iperf warn-prefix: 12 |

## Per-run notes (data quality + errors)

### 20260218_191943_ues0 (UEs=0)

- Missing files: none
- iperf3: files=0 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cuda): threads_assumed=1 thread_n=34 mean/p95_us=208.65/222.09 cum_n=34 mean/p95_us=208.65/222.09 events_per_s(thread/cum)=0.571/0.571
- ZMQ: lines=595 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260218_192448_ues1 (UEs=1)

- Missing files: none
- iperf3: files=1 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cuda): threads_assumed=1 thread_n=77 mean/p95_us=322.55/360.40 cum_n=77 mean/p95_us=322.55/360.40 events_per_s(thread/cum)=1.287/1.287
- ZMQ: lines=600 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260218_192836_ues3 (UEs=3)

- Missing files: none
- iperf3: files=3 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cuda): threads_assumed=1 thread_n=49 mean/p95_us=319.22/344.05 cum_n=49 mean/p95_us=319.22/344.05 events_per_s(thread/cum)=0.827/0.827
- ZMQ: lines=838 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260218_193305_ues6 (UEs=6)

- Missing files: none
- iperf3: files=6 parse_fail=0 missing_end=0 warn_prefix=0 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cuda): threads_assumed=1 thread_n=26 mean/p95_us=342.61/386.26 cum_n=26 mean/p95_us=342.61/386.26 events_per_s(thread/cum)=0.445/0.445
- ZMQ: lines=45 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False

### 20260218_193808_ues12 (UEs=12)

- Missing files: none
- iperf3: files=12 parse_fail=0 missing_end=12 warn_prefix=12 stderr_error=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- LDPC (cuda): threads_assumed=1 thread_n=14 mean/p95_us=337.65/377.38 cum_n=14 mean/p95_us=337.65/377.38 events_per_s(thread/cum)=0.245/0.245
- ZMQ: lines=5 published_max=0 ue_lines=0 unique_rnti=0 usage_error=False
