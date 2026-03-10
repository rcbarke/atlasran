# Initial iperf3 Throughput Analysis

iperf3 client at UE, iperf3 server at 5GC. Two samples at each attenuation level.

On the UE:
```
srk-ue@IS-WiN-PC14:~/aerial-dgx-spark/experiments/srk/channel_mod/sionna-rk/nr-UE$ docker exec -it oai-nr-ue   iperf3 -s
```

On the DGX Spark:
'''
## TCP
srk@spark-ecf8:~/aerial-dgx-spark/experiments/srk/channel_mod/sionna-rk/nr-UE$ docker exec -it oai-ext-dn   iperf3 -t 30 -i 1 -B 192.168.72.135 -c 12.1.1.2 -J > downlink_30dB_attenuation.json

srk@spark-ecf8:~/aerial-dgx-spark/experiments/srk/channel_mod/sionna-rk/nr-UE$ docker exec -it oai-ext-dn   iperf3 -t 30 -i 1 -B 192.168.72.135 -c 12.1.1.2 -R -J > uplink_30dB_attenuation.json

## UDP
srk@spark-ecf8:~/aerial-dgx-spark/experiments/srk/channel_mod/sionna-rk/nr-UE$ docker exec -it oai-ext-dn \
  iperf3 -u -t 30 -i 1 -b 0 -B 192.168.72.135 -c 12.1.1.2 -J \
  > downlink_capacity_udp_30dB_attenuation.json

srk@spark-ecf8:~/aerial-dgx-spark/experiments/srk/channel_mod/sionna-rk/nr-UE$ docker exec -it oai-ext-dn   iperf3 -u -t 30 -i 1 -b 0 -B 192.168.72.135 -c 12.1.1.2 -R -J   > uplink_capacity_udp_30dB_attenuation.json
'''

---

## 1. Test context (what matters for interpreting the numbers)

**Architecture**

* SRK gNB on DGX/Jetson host
* x86 CPU-only OAI NR-UE in Docker
* USRP B210 (USB 3 confirmed)
* Band n78, numerology μ=1
* Configured **51 PRBs**
* Observed **DL MCS ≤ ~12** during tests

**RF path**

* Fixed attenuators: **30 dB**
* SMA + cable loss: estimated **+1–3 dB**
* Effective path loss: **~31–33 dB**

**Measurement tools**

* iperf3 TCP (single stream)
* iperf3 UDP (both saturated `-b 0` and observed receiver-limited cases)
* Reference: `iperf3.md` 

---

## 2. Summary of results (30 dB attenuation)

### Downlink (gNB → UE)

| Mode                             | Result                                          | Stability                       |
| -------------------------------- | ----------------------------------------------- | ------------------------------- |
| **TCP (single stream, -R)**      | ~**4.0–4.5 Mbps** sustained                     | Clean, no RRC churn             |
| **UDP (receiver-limited)**       | ~**4.3–4.6 Mbps** received, <0.1% loss          | Mostly stable                   |
| **UDP (`-b 0`, sender-limited)** | Sender pushes multi-Gbps; UE receives ~4.5 Mbps | **Unstable** (buffer overflows) |

Evidence:

* TCP DL receiver throughput ≈ **4.0–4.1 Mbps** 
* UDP DL received throughput ≈ **4.55 Mbps**, loss ≈ **0.07%** 

**Interpretation**

* TCP and UDP **agree on the same ceiling**.
* This indicates the DL is **not TCP-limited**.
* The effective downlink “pipe” to the UE is **~4–5 Mbps** under these conditions.

---

### Uplink (UE → gNB)

| Mode                    | Result                                 | Stability               |
| ----------------------- | -------------------------------------- | ----------------------- |
| **TCP (single stream)** | ~**2.3–3.0 Mbps**                      | Clean                   |
| **UDP (`-b 0`)**        | UE host saturates CPU; receiver sees 0 | **Invalid measurement** |

Evidence:

* TCP UL receiver ≈ **2.3–2.4 Mbps** 
* UDP UL `-b 0` shows **host CPU ~99%**, control socket closes, no valid RX 

**Interpretation**

* UL capacity is **lower than DL**, consistent with:

  * TDD DL/UL split
  * Scheduler bias
  * Conservative UL MCS
* UDP `-b 0` **cannot be used** for UL capacity here; it overwhelms the UE host before the radio path is exercised.

---

## 3. Control-plane and buffer observations (important)

Even at ~30 dB attenuation, during **UDP tests only**, you observed:

* **SDU buffer overflows**
* **RLC buffer overflows**
* **RRC re-establishments**
* **C-RNTI churn**

These did **not** appear during TCP tests.

**Interpretation**

* UDP at or above capacity **removes all backpressure**.
* Offered load exceeds what MAC/RLC can drain → queues explode.
* This cascades into timing failures and RRC instability.
* This is **expected behavior** when deliberately saturating beyond the scheduler’s stable operating point.

TCP remains clean because congestion control naturally throttles before buffers destabilize.

---

## 4. Why 60 dB attenuation failed

At ~60 dB attenuation:

* gNB started
* UE **failed to decode SIB1**
* PHY crashed shortly thereafter

**Interpretation**

* At ~60 dB, SNR fell below what your current:

  * MCS cap (≤12),
  * PRB allocation,
  * and receiver configuration
    can tolerate for **broadcast channel (SSB/PBCH/SIB1)** decoding.
* This is a **PHY-limited failure**, not a transport or iperf issue.

In other words:

> 30 dB → system is **scheduler/buffer-limited**
> 60 dB → system becomes **PHY-limited**

That transition point is exactly what you would expect to see in a controlled attenuation sweep.

---

## 5. What the numbers mean for your architecture (key conclusions)

1. **Effective UE throughput at ~30 dB**

   * DL: **~4–5 Mbps**
   * UL: **~2–3 Mbps**

2. **This is not a TCP artifact**

   * UDP receiver-limited results confirm the same ceiling.

3. **Primary limiting factors**

   * Small effective PRB allocation per TTI
   * Conservative MCS (observed ≤12)
   * TDD UL/DL split
   * RLC/MAC buffering limits under unthrottled load

4. **UDP `-b 0` is a stress test, not a capacity measurement**

   * Useful for finding the knee
   * Expected to cause RLC/RRC churn when pushed past stability

5. **RF headroom**

   * ~30 dB path loss is workable
   * ~60 dB exceeds current PHY robustness for SIB1
   * This brackets your usable operating region nicely

---

## 6. Recommended “capacity” methodology going forward

For **repeatable, meaningful capacity characterization**:

1. **Downlink**

   * UDP **bitrate sweep** (e.g., 1M → 2M → 5M → 10M)
   * Stop at first sustained loss/jitter increase
   * That bitrate ≈ DL capacity

2. **Uplink**

   * Same UDP sweep (do **not** use `-b 0`)
   * Or TCP with `-P 2–4` as a proxy

3. **Always correlate with**

   * gNB MAC stats (RBs allocated, MCS, BLER)
   * UE MAC stats

This will let you cleanly separate:

* **PHY-limited**
* **scheduler-limited**
* **buffer-limited**
  regimes.

---

### Bottom line

Your results are **internally consistent, technically reasonable, and informative**.
They already show a clear picture:

> At ~30 dB attenuation, the SRK + OAI + B210 stack is **scheduler- and buffer-limited**, delivering ~4–5 Mbps DL and ~2–3 Mbps UL to a single UE with stable TCP behavior.
> Pushing beyond that with UDP correctly exposes control-plane and buffering limits, while ~60 dB attenuation crosses into PHY failure (SIB1 decode loss).

