# CU/DU Ablation Post-Processing Report (Optimized)

Generated (UTC): 2026-02-26T00:36:20.143376+00:00

## Notes on metric semantics

- **CPU/GPU utilization is windowed** to the inferred iperf test interval (with a small trim) when possible.
- **LDPC prints are treated as samples**, not true per-decode event counts; `LDPC samples/s` reflects log print rate.
- **LDPC core-proxy** approximates CPU core-time in the LDPC decode region using either (a) per-bucket summation (if multiple samples arrive within a small bucket) or (b) scaling by `min(threads_cfg, segments_est)` from `(us/us_per_seg)`.
- **Slot rate / RTF** is a direct harness fidelity KPI: if RFSim/host scheduling slows, slots/sec drops and RTF < 1.

## Runs analyzed
- `20260225_181048_ues0` (ue_count=0, test_window_source=manifest_start+fallback_duration)
- `20260225_181448_ues1` (ue_count=1, test_window_source=iperf)
- `20260225_181820_ues3` (ue_count=3, test_window_source=iperf)
- `20260225_182155_ues6` (ue_count=6, test_window_source=iperf)
- `20260225_182659_ues12` (ue_count=12, test_window_source=iperf)

## Summary (windowed)

| UEs | UL total (Mbps) | UL/UE (Mbps) | iperf end-rate | Jain | DU CPU mean/p95 (%) | CU CPU mean/p95 (%) | SYS CPU mean/p95 (%) | LDPC wall mean/p95 (us) | LDPC core-proxy mean/p95 (us) | LDPC samples/s | Slot rate (slots/s) | RTF | ZMQ pub-rate (ctr/s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | NA | NA | NA | NA | 210.16/213.27 | 1.71/2.29 | 15.28/16.83 | 79.87/91.10 | 79.87/91.10 | 1.002 | 3741.2 | 3.741 | NA |
| 1 | 114.59 | 114.59 | 1.000 | 1.000000 | 324.79/326.77 | 22.98/24.43 | 26.73/28.08 | 255.86/262.09 | 1016.74/1048.36 | 1.005 | 1844.4 | 1.844 | NA |
| 3 | 65.21 | 21.74 | 1.000 | 0.999997 | 289.93/291.73 | 16.80/17.68 | 25.11/26.37 | 262.60/268.36 | 1042.06/1073.45 | 1.005 | 1045.9 | 1.046 | NA |
| 6 | 35.09 | 5.85 | 1.000 | 0.999484 | 205.54/207.18 | 9.02/10.63 | 19.58/21.43 | 275.27/286.05 | 1087.42/1144.18 | 1.015 | 551.7 | 0.552 | NA |
| 12 | 16.35 | 1.36 | 0.000 | 0.999997 | 162.38/164.92 | 5.69/6.89 | 16.91/17.95 | 273.18/293.63 | 1063.82/1174.53 | 1.014 | 285.1 | 0.285 | NA |

## Deltas vs baselines

### Relative to UE=1 (scaling reference)

| UEs | UL total Δ | Slot rate Δ | RTF Δ | Notes |
| --- | --- | --- | --- | --- |
| 0 | NA | +102.8% | +102.8% |  |
| 3 | -43.1% | -43.3% | -43.3% |  |
| 6 | -69.4% | -70.1% | -70.1% |  |
| 12 | -85.7% | -84.5% | -84.5% | iperf missing_end=12 |

### Relative to UE=0 (idle baseline)

| UEs | DU CPU mean Δ | CU CPU mean Δ | SYS CPU mean Δ | GPU power mean Δ | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | +54.5% | +1242.3% | +74.9% | NA |  |
| 3 | +38.0% | +881.3% | +64.3% | NA |  |
| 6 | -2.2% | +426.6% | +28.1% | NA |  |
| 12 | -22.7% | +232.4% | +10.6% | NA | iperf_end_rate=0.000 |

## Per-run notes (data quality + errors)

### 20260225_181048_ues0 (UEs=0)

- Test window: source=manifest_start+fallback_duration start=1772061048171 end=1772061108171 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=0 files=0 parse_ok_rate=NA end_present_rate=NA missing_end=0 warn_prefix=0 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- Slot rate: mean_sps=3741.2 p50/p95_sps=3731.8/3832.3 RTF=3.741 slots_per_frame=10
- LDPC (cpu): threads_cfg=4 wall_mean/p95_us=79.87/91.10 core_proxy_mean/p95_us=79.87/91.10 method=eff_parallelism_scaling samples_per_s=1.002 segments_est_mean=1.00 effpar_mean=1.00
- ZMQ: lines=600 duration_s=59.8 ctr_rate_sps=NA line_rate_sps=0.00 unique_rnti=0 usage_error=False

### 20260225_181448_ues1 (UEs=1)

- Test window: source=iperf start=1772061288000 end=1772061348000 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=1 files=1 parse_ok_rate=1.000 end_present_rate=1.000 missing_end=0 warn_prefix=0 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- Slot rate: mean_sps=1844.4 p50/p95_sps=1832.5/1844.4 RTF=1.844 slots_per_frame=10
- LDPC (cpu): threads_cfg=4 wall_mean/p95_us=255.86/262.09 core_proxy_mean/p95_us=1016.74/1048.36 method=eff_parallelism_scaling samples_per_s=1.005 segments_est_mean=7.94 effpar_mean=3.93
- ZMQ: lines=600 duration_s=59.6 ctr_rate_sps=NA line_rate_sps=0.00 unique_rnti=0 usage_error=False

### 20260225_181820_ues3 (UEs=3)

- Test window: source=iperf start=1772061501000 end=1772061561000 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=3 files=3 parse_ok_rate=1.000 end_present_rate=1.000 missing_end=0 warn_prefix=0 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- Slot rate: mean_sps=1045.9 p50/p95_sps=1043.2/1048.3 RTF=1.046 slots_per_frame=10
- LDPC (cpu): threads_cfg=4 wall_mean/p95_us=262.60/268.36 core_proxy_mean/p95_us=1042.06/1073.45 method=eff_parallelism_scaling samples_per_s=1.005 segments_est_mean=7.93 effpar_mean=3.95
- ZMQ: lines=838 duration_s=59.6 ctr_rate_sps=NA line_rate_sps=0.00 unique_rnti=0 usage_error=False

### 20260225_182155_ues6 (UEs=6)

- Test window: source=iperf start=1772061716000 end=1772061776000 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=6 files=6 parse_ok_rate=1.000 end_present_rate=1.000 missing_end=0 warn_prefix=0 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- Slot rate: mean_sps=551.7 p50/p95_sps=550.8/557.3 RTF=0.552 slots_per_frame=10
- LDPC (cpu): threads_cfg=4 wall_mean/p95_us=275.27/286.05 core_proxy_mean/p95_us=1087.42/1144.18 method=eff_parallelism_scaling samples_per_s=1.015 segments_est_mean=7.78 effpar_mean=3.92
- ZMQ: lines=45 duration_s=1.9 ctr_rate_sps=NA line_rate_sps=0.00 unique_rnti=0 usage_error=False

### 20260225_182659_ues12 (UEs=12)

- Test window: source=iperf start=1772062021000 end=1772062081000 trim_s=2.0
- Missing files: none
- iperf3: expected_ues=12 files=12 parse_ok_rate=1.000 end_present_rate=0.000 missing_end=12 warn_prefix=12 stderr_error=0 reverse_n=0
- DU log errors: aborted=0, assert=0, buffer_overflow=0, error=0, failed=0, segfault=0, timeout=0
- Slot rate: mean_sps=285.1 p50/p95_sps=285.7/286.6 RTF=0.285 slots_per_frame=10
- LDPC (cpu): threads_cfg=4 wall_mean/p95_us=273.18/293.63 core_proxy_mean/p95_us=1063.82/1174.53 method=eff_parallelism_scaling samples_per_s=1.014 segments_est_mean=7.35 effpar_mean=3.82
- ZMQ: lines=5 duration_s=0.0 ctr_rate_sps=NA line_rate_sps=0.00 unique_rnti=0 usage_error=False
