# CU/DU Ablation Post-Processing Report (Optimized)

Generated (UTC): 2026-02-26T01:07:26.512104+00:00

## Notes on metric semantics

- **CPU/GPU utilization is windowed** to the inferred iperf test interval (with a small trim) when possible.
- **LDPC prints are treated as samples**, not true per-decode event counts; `LDPC samples/s` reflects log print rate.
- **LDPC core-proxy** approximates CPU core-time in the LDPC decode region using either (a) per-bucket summation (if multiple samples arrive within a small bucket) or (b) scaling by `min(threads_cfg, segments_est)` from `(us/us_per_seg)`.
- **Slot rate / RTF** is a direct harness fidelity KPI: if RFSim/host scheduling slows, slots/sec drops and RTF < 1.

## Runs analyzed
- `20260225_184233_ues0` (ue_count=0, test_window_source=manifest_start+fallback_duration)
- `20260225_184947_ues1` (ue_count=1, test_window_source=iperf)
- `20260225_185307_ues3` (ue_count=3, test_window_source=iperf)
- `20260225_190248_ues6` (ue_count=6, test_window_source=iperf)
- `20260225_190743_ues12` (ue_count=12, test_window_source=iperf)

## Summary (windowed)

| UEs | UL total (Mbps) | UL/UE (Mbps) | iperf end-rate | Jain | DU CPU mean/p95 (%) | CU CPU mean/p95 (%) | SYS CPU mean/p95 (%) | LDPC wall mean/p95 (us) | LDPC core-proxy mean/p95 (us) | LDPC samples/s | Slot rate (slots/s) | RTF | GPU util mean/p95 (%) | GPU power mean/p95 (W) | ZMQ pub-rate (ctr/s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | NA | NA | NA | NA | 212.87/216.09 | 1.87/2.84 | 15.08/17.00 | NA/NA | NA/NA | 0.000 | 3693.0 | 3.693 | 1.29/3.70 | 11.48/12.11 | NA |
| 1 | 103.34 | 103.34 | 1.000 | 1.000000 | 349.31/351.64 | 20.73/22.54 | 27.86/29.74 | 316.02/350.83 | 316.02/350.83 | 1.296 | 1702.6 | 1.703 | 44.85/47.00 | 38.48/39.11 | NA |
| 3 | 66.44 | 22.15 | 1.000 | 1.000000 | 329.73/339.57 | 17.21/18.11 | 29.25/31.82 | 316.90/347.89 | 316.90/347.89 | 0.846 | 1060.9 | 1.061 | 29.28/34.00 | 29.73/30.54 | NA |
| 6 | 35.01 | 5.84 | 1.000 | 0.999930 | 231.60/244.69 | 9.77/10.75 | 24.23/26.08 | 369.47/392.66 | 369.47/392.66 | 0.438 | 551.0 | 0.551 | 19.34/22.00 | 22.25/23.14 | NA |
| 12 | 16.15 | 1.35 | 0.000 | 0.999998 | 172.91/176.62 | 5.80/6.78 | 19.46/20.70 | 345.17/373.05 | 345.17/373.05 | 0.239 | 282.2 | 0.282 | 9.45/11.00 | 17.08/17.60 | NA |

## Deltas vs baselines

### Relative to UE=1 (scaling reference)

| UEs | UL total Δ | Slot rate Δ | RTF Δ | Notes |
| --- | --- | --- | --- | --- |
| 0 | NA | +116.9% | +116.9% |  |
| 3 | -35.7% | -37.7% | -37.7% |  |
| 6 | -66.1% | -67.6% | -67.6% |  |
| 12 | -84.4% | -83.4% | -83.4% | iperf missing_end=12 |

### Relative to UE=0 (idle baseline)

| UEs | DU CPU mean Δ | CU CPU mean Δ | SYS CPU mean Δ | GPU power mean Δ | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | +64.1% | +1010.1% | +84.8% | +235.0% |  |
| 3 | +54.9% | +821.4% | +94.0% | +158.9% |  |
| 6 | +8.8% | +423.2% | +60.7% | +93.8% |  |
| 12 | -18.8% | +210.7% | +29.0% | +48.7% | iperf_end_rate=0.000 |

## Per-run notes (data quality + errors)

### 20260225_184233_ues0 (UEs=0)

- Test window: source=manifest_start+fallback_duration start=1772062953211 end=1772063013211 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=0 files=0 parse_ok_rate=NA end_present_rate=NA missing_end=0 warn_prefix=0 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- Slot rate: mean_sps=3693.0 p50/p95_sps=3678.2/3764.7 RTF=3.693 slots_per_frame=10
- LDPC (unknown): threads_cfg=None wall_mean/p95_us=NA/NA core_proxy_mean/p95_us=NA/NA method=eff_parallelism_scaling samples_per_s=0.000 segments_est_mean=NA effpar_mean=NA
- ZMQ: lines=600 duration_s=59.7 ctr_rate_sps=NA line_rate_sps=0.00 unique_rnti=0 usage_error=False

### 20260225_184947_ues1 (UEs=1)

- Test window: source=iperf start=1772063387000 end=1772063447000 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=1 files=1 parse_ok_rate=1.000 end_present_rate=1.000 missing_end=0 warn_prefix=0 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- Slot rate: mean_sps=1702.6 p50/p95_sps=1667.8/1684.5 RTF=1.703 slots_per_frame=10
- LDPC (cuda): threads_cfg=1 wall_mean/p95_us=316.02/350.83 core_proxy_mean/p95_us=316.02/350.83 method=eff_parallelism_scaling samples_per_s=1.296 segments_est_mean=6.21 effpar_mean=1.00
- ZMQ: lines=595 duration_s=59.2 ctr_rate_sps=NA line_rate_sps=0.00 unique_rnti=0 usage_error=False

### 20260225_185307_ues3 (UEs=3)

- Test window: source=iperf start=1772063588000 end=1772063648000 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=3 files=3 parse_ok_rate=1.000 end_present_rate=1.000 missing_end=0 warn_prefix=0 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- Slot rate: mean_sps=1060.9 p50/p95_sps=1063.1/1071.0 RTF=1.061 slots_per_frame=10
- LDPC (cuda): threads_cfg=1 wall_mean/p95_us=316.90/347.89 core_proxy_mean/p95_us=316.90/347.89 method=eff_parallelism_scaling samples_per_s=0.846 segments_est_mean=5.90 effpar_mean=1.00
- ZMQ: lines=826 duration_s=59.0 ctr_rate_sps=NA line_rate_sps=0.00 unique_rnti=0 usage_error=False

### 20260225_190248_ues6 (UEs=6)

- Test window: source=iperf start=1772064169000 end=1772064229000 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=6 files=6 parse_ok_rate=1.000 end_present_rate=1.000 missing_end=0 warn_prefix=0 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=1, segfault=0, timeout=0
- Slot rate: mean_sps=551.0 p50/p95_sps=546.8/573.3 RTF=0.551 slots_per_frame=10
- LDPC (cuda): threads_cfg=1 wall_mean/p95_us=369.47/392.66 core_proxy_mean/p95_us=369.47/392.66 method=eff_parallelism_scaling samples_per_s=0.438 segments_est_mean=4.78 effpar_mean=1.00
- ZMQ: lines=35 duration_s=1.5 ctr_rate_sps=NA line_rate_sps=0.00 unique_rnti=0 usage_error=False

### 20260225_190743_ues12 (UEs=12)

- Test window: source=iperf start=1772064465000 end=1772064525000 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=12 files=12 parse_ok_rate=1.000 end_present_rate=0.000 missing_end=12 warn_prefix=12 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- Slot rate: mean_sps=282.2 p50/p95_sps=282.2/284.1 RTF=0.282 slots_per_frame=10
- LDPC (cuda): threads_cfg=1 wall_mean/p95_us=345.17/373.05 core_proxy_mean/p95_us=345.17/373.05 method=eff_parallelism_scaling samples_per_s=0.239 segments_est_mean=4.49 effpar_mean=1.00
- ZMQ: lines=5 duration_s=NA ctr_rate_sps=NA line_rate_sps=NA unique_rnti=0 usage_error=False
