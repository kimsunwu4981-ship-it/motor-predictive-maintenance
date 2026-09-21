import numpy as np, sys, math
d=np.load(sys.argv[1]); t=d["t"]; m=(t>=2)&(t<12); w=d["omega"][m]; fr=w.mean()/(2*math.pi); N=m.sum(); fq=np.fft.rfftfreq(N,1/2560)
for ch in ("T_fault","alpha"):
    x=d[ch][m]; x=x-x.mean(); S=np.abs(np.fft.rfft(x*np.hanning(N)))
    pk=[float(fq[(fq>lo)&(fq<hi)][np.argmax(S[(fq>lo)&(fq<hi)])]) for lo,hi in ((15,25),(95,105),(135,145))]
    print(ch, "fr_omega=%.3f"%fr, "peaks", pk, "theory", [round(fr,3), round(120-fr,3), round(120+fr,3)])
th=d["theta"][m]; print("theta slope/2pi = %.4f" % (np.polyfit(t[m], th, 1)[0]/(2*math.pi)))
