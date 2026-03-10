# NVIDIA MCS Monitoring xApp Logic

* **What the xApp is measuring:** per-UE *scheduled RBs* reported by the MAC stats stream, not the cell’s configured RB capacity (e.g., “106 PRBs”).
* **`PRBs(inst)`** = the instantaneous `dl_sched_rb/ul_sched_rb` snapshot at the print moment.
* **`PRBs(max)`** = max scheduled RBs observed for that UE during the last publish window.
* **`PRBs(delta)`** = sum of per-callback scheduled RB samples across the publish window → effectively **RB·TTI (or RB·ms)** over the interval, not “total PRBs in the carrier.”
* **`PRBs(cum)`** = MAC-provided cumulative aggregate PRB counters since attach (lifetime counter), so it can be nonzero even when `inst/max` are 0 in an idle window.
* **Why the logs report `…/0` when idle:** if the UE has no UL/DL grants in the window, the scheduled RB samples are all zeros ⇒ `inst = max = delta = 0`. That’s expected and does **not** mean the carrier has 0 PRBs.
