# apply_channelmod.c Branch Comparison (OAI RF Simulator)

This README compares two versions of the OAI RF simulator channel application code:

- **Old branch:** `slicing-spring-of-code`  
  - File: `apply_channelmod_modified.c` (lab-modified)
- **New branch:** `2025.w34`  
  - File: `apply_channelmod.c` (latest upstream branch)

The older file was modified by the lab to correct channel-model mathematics and improve interpretability. The newer branch is a broader architectural update (including expanded modeling features), but it changes the numerical assumptions in ways that can reintroduce (or obscure) earlier mathematical errors if not carefully validated.

---

## 1) High-Level Summary of Changes

### A. Output / Signal Representation
**Old (`slicing-spring-of-code` / modified)**
- Writes channel output as **quantized complex int16** (`c16_t`).
- Uses explicit rounding (`lround`) and integer clipping semantics implicit to int16.
- Noise and channel gain effectively operate in a **fixed-point-ish** regime (even if computed in double).

**New (`2025.w34`)**
- Writes channel output as **complex float** (`cf_t`).
- Accumulates directly into float output buffers:
  - `out_ptr->r += ...`
  - `out_ptr->i += ...`
- This is more flexible and avoids quantization artifacts, but requires **clean, dimensionally consistent noise scaling** (power vs amplitude) because there is no implicit “int16 amplitude” normalization.

**Impact:** architectural modernization (float domain) is good, but any noise-parameter semantics must be re-established explicitly.

---

## 2) OAI Mathematical Errors (What Was Fixed in the Lab Variant)

The lab modifications in `apply_channelmod_modified.c` were intended to correct common channel/noise modeling mistakes that can materially bias SNR, BLER, and throughput under concurrency.

### A. AWGN Scaling: Power vs Standard Deviation (Sigma)
A recurring error pattern in channel simulation code is treating a **power quantity** (linear) as if it were an **amplitude standard deviation** (sigma).

If `noise_power_dB` represents **complex noise power** \(P\) in dB, then:

- Convert dB to linear power:
  \[
  P = 10^{\frac{noise\_power\_dB}{10}}
  \]
- For circular complex Gaussian noise \(n = n_I + j n_Q\) with equal I/Q variance:
  \[
  P = \mathbb{E}[|n|^2] = 2\sigma^2 \quad \Rightarrow \quad \sigma = \sqrt{\frac{P}{2}}
  \]

**Lab fix (old/modified file):**
- Converts `noise_power_dB` → linear power → derives **per-dimension sigma** using:
  - `sigma = sqrt(P / 2)`

**Problem in the new branch (risk):**
- The new file computes something proportional to `10^(dB/10)` and multiplies it directly by a Gaussian draw as if it were sigma.
- That is dimensionally inconsistent if the variable is truly noise *power*.

**Consequence:** The simulator can inject noise that is systematically too large or too small (often off by a square root and/or factor of 2), leading to incorrect SNR and invalid comparisons across experiments.

> Practical rule: if you multiply `N(0,1)` by a term derived from dB power, you almost always need a `sqrt()` step (and usually a `/sqrt(2)` for complex I/Q).

---

### B. I/Q Power Split (Factor-of-2 Error)
Even if power-to-sigma conversion is present, a second common error is forgetting the **two dimensions** (I and Q) for complex baseband noise.

**Correct relationship:**
- total complex noise power \(P\) is split across I and Q:
  - \( \sigma_I^2 = \sigma_Q^2 = P/2 \)

**Lab fix (old/modified file):**
- Explicitly divides by 2 inside the square root.

**Consequence if missing:** noise injected per dimension will be too strong, shifting SNR by ~3 dB.

---

### C. Channel Offset / Delay Sign Handling (Indexing Correctness)
The channel application loop uses `channel_offset`/delay in the tap indexing expression. If the offset can be negative (or interpreted as signed), mishandling can silently produce huge index shifts.

**Lab behavior (old/modified file):**
- Uses an absolute value on channel offset before applying it in the modulo index path.

**New branch risk:**
- If `channel_offset` is treated as unsigned or used without sign protection, a negative value can wrap into a very large positive value and break indexing.

**Consequence:** incorrect convolution alignment, effectively applying the wrong channel impulse response time shift and corrupting received samples in a way that looks like “random channel instability.”

---

## 3) Software Architecture Differences Across Branches

### Old: `slicing-spring-of-code`
- Focused on RFSim channel application in a workflow where output is often **int16**.
- Lab modifications were “surgical,” targeting **mathematical correctness**:
  - noise power conversion
  - correct sigma derivation for complex AWGN
  - safer delay handling
  - clearer debug outputs for validation

### New: `2025.w34`
- A more expansive implementation:
  - shifts to **float output buffers** (`cf_t`)
  - introduces additional modeling components (e.g., more dynamic effects and more compositional processing)
- Architecturally more modern and extensible, but it changes scaling assumptions and can reintroduce prior correctness issues if:
  - `noise_power_dB` semantics differ (power vs amplitude)
  - I/Q split is not enforced
  - legacy normalizations (e.g., hard-coded constants) persist without a clear dimensional meaning

**Takeaway:** `2025.w34` is a broader rewrite; correctness is not guaranteed by architecture alone. The lab’s mathematical corrections should be re-applied deliberately in the float-domain implementation.

---

## 4) Where to Stage and Apply Modifications

The correct location to stage changes depends on which repo layout you are using.

Make modifications in **one** of these directories:

- `../../oai-cpu/ext/openairinterface5g/radio/rfsimulator`
- `../../sionna-rk/ext/openairinterface5g/radio/rfsimulator`

After editing `apply_channelmod.c` in the appropriate directory, rebuild OAI docker containers using the corresponding script:

### Rebuild (oai-cpu)
```bash
../../oai-cpu/scripts/build-oai-images.sh
````

### Rebuild (sionna-rk)

```bash
../../sionna-rk/scripts/build-oai-images.sh
```

---

## 5) Suggested Validation Checklist After Any Patch

1. **Noise sanity test (no channel taps):**

   * Set channel to unity/no fading and verify measured noise variance matches expected (P) from `noise_power_dB`.
2. **Complex split check:**

   * Confirm `Var(I) ≈ Var(Q) ≈ P/2`.
3. **SNR regression:**

   * Run a fixed MCS / fixed PRB test and confirm SNR shifts match dB changes linearly.
4. **Delay sign test:**

   * Exercise positive and negative offsets (if supported) and verify time alignment of the CIR application.
5. **Compare old vs new:**

   * With equivalent scaling, confirm the float path reproduces old-path behavior when quantization is emulated.

---

## 6) File Inventory

* `apply_channelmod_modified.c`
  Old branch (`slicing-spring-of-code`), lab-modified to correct channel/noise math.

* `apply_channelmod.c`
  New branch (`2025.w34`), latest implementation with architectural updates (float buffers, expanded modeling).

---

## 7) Bottom Line

* The old/lab-modified file explicitly corrected **noise injection math** (power → sigma, complex I/Q split) and safeguarded **offset handling**.
* The new branch modernizes the architecture but changes representation and scaling in ways that require re-validation.
* If you patch `apply_channelmod.c`, stage the edit in the `.../radio/rfsimulator` directory listed above and rebuild using the matching `build-oai-images.sh`.
