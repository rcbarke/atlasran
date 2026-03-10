import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def fit_powerlaw(N, T):
    x = np.log(N)
    y = np.log(T)
    b, loga = np.polyfit(x, y, 1)
    a = np.exp(loga)

    y_pred = loga + b * x
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot
    return a, b, r2

# Load summaries
oai = pd.read_csv("oai_ablation_summary.csv")
srk = pd.read_csv("srk_ablation_summary.csv")

ues = np.array([1, 3, 6, 12], dtype=float)

def get_T(df, ue):
    return float(df.loc[df["ue_count"] == ue].iloc[0]["iperf_total_mbps"])

T_oai = np.array([get_T(oai, int(u)) for u in ues])
T_srk = np.array([get_T(srk, int(u)) for u in ues])

a_oai, b_oai, r2_oai = fit_powerlaw(ues, T_oai)
a_srk, b_srk, r2_srk = fit_powerlaw(ues, T_srk)

x_line = np.linspace(ues.min(), ues.max(), 200)
y_oai_fit = a_oai * (x_line ** b_oai)
y_srk_fit = a_srk * (x_line ** b_srk)

plt.figure(figsize=(10, 6.4))
plt.plot(ues, T_oai, marker="o", linewidth=2, markersize=9, label="OAI (CPU LDPC)")
plt.plot(ues, T_srk, marker="s", linewidth=2, markersize=9, label="SRK (CUDA LDPC)")

plt.plot(x_line, y_oai_fit, linestyle="--", linewidth=2,
         label=f"OAI fit: {a_oai:.2f}·N^{b_oai:.4f}")
plt.plot(x_line, y_srk_fit, linestyle="--", linewidth=2,
         label=f"SRK fit: {a_srk:.2f}·N^{b_srk:.4f}")

plt.xlabel("Number of UEs (N)")
plt.ylabel("Aggregate UL goodput (Mbps)")
plt.xticks(ues.astype(int))
plt.grid(True, linestyle=":", linewidth=1)
plt.legend(loc="upper right")
plt.tight_layout()
plt.savefig("fig_ul_throughput_scaling_updated.png", dpi=200)

print("OAI fit:", a_oai, b_oai, r2_oai)
print("SRK fit:", a_srk, b_srk, r2_srk)
