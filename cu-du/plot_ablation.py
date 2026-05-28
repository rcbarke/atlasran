import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Load summaries
oai = pd.read_csv("oai_ablation_summary.csv")
srk = pd.read_csv("srk_ablation_summary.csv")

ues = np.array([1, 3, 6, 12], dtype=float)

def get_T(df, ue):
    return float(df.loc[df["ue_count"] == ue].iloc[0]["iperf_total_mbps"])

T_oai = np.array([get_T(oai, int(u)) for u in ues])
T_srk = np.array([get_T(srk, int(u)) for u in ues])

plt.figure(figsize=(10, 6.4))
plt.plot(ues, T_oai, marker="o", linewidth=2, markersize=9, label="OAI (CPU LDPC)")
plt.plot(ues, T_srk, marker="s", linewidth=2, markersize=9, label="SRK (CUDA LDPC)")

plt.xlabel("Number of UEs (N)")
plt.ylabel("Aggregate UL goodput (Mbps)")
plt.xticks(ues.astype(int))
plt.grid(True, linestyle=":", linewidth=1)
plt.legend(loc="upper right")
plt.tight_layout()
plt.savefig("fig_ul_throughput_scaling_updated.png", dpi=200)
