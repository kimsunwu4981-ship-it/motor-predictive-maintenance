import numpy as np, sys, math, glob, os, json
D = sys.argv[1]
for pat in ("fault_ecc_dynamic_e10_half_20260835", "baseline_half_20260828", "fault_itsc_t2_rated_20260835"):
    f = os.path.join(D, pat + ".npz"); d = np.load(f); t = d["t"]; w = d["omega"]; m = (t >= 2) & (t < 12)
    fr_w = w[m].mean() / (2 * math.pi)
    # theta 재구성: 결함 토크에서 역산 불가 → npz 에 theta 없음. sin(theta) 성분은 T_fault 에 포함 → T_fault 스펙트럼으로 확인
    N = m.sum(); hz = 2560; fq = np.fft.rfftfreq(N, 1 / hz)
    for ch in ("T_fault", "alpha", "omega"):
        x = d[ch][m]; x = x - x.mean(); S = np.abs(np.fft.rfft(x * np.hanning(N)))
        sel = (fq > 15) & (fq < 25); pk = fq[sel][np.argmax(S[sel])] if S[sel].max() > 0 else None
        sel2 = (fq > 95) & (fq < 105); pk2 = fq[sel2][np.argmax(S[sel2])] if S[sel2].max() > 0 else None
        print(pat, ch, "fr_from_omega=%.4f" % fr_w, "peak15-25=%s" % pk, "peak95-105=%s" % pk2, "rms=%.3g" % np.sqrt((x**2).mean()))
    # 속도 리플 크기
    print(pat, "omega ripple pp=%.4f rad/s" % (w[m].max() - w[m].min()))
