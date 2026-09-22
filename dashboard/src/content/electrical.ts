import type { ModeData } from "../data";
import type { ChapterText, FaultCardText, GlossaryEntry, ModeContent } from "./types";

// ---- 도우미: 숫자는 전부 JSON 에서 ----
const fault = (d: ModeData, key: string) => d.faults.items.find((f) => f.key === key);
const row = (d: ModeData, st: string) => d.thresholds.electrical.rows.find((r) => r.status === st)!;
const A = (v: number) => `${v.toFixed(1)} A`;
const pct = (v: number) => `${(v * 100).toFixed(0)} %`;
const at = (d: ModeData, i: number) => ({
  a: d.timeseries.current_rms_A.A[i], b: d.timeseries.current_rms_A.B[i], c: d.timeseries.current_rms_A.C[i],
  i2: d.timeseries.i2_over_i1[i], sa: d.timeseries.current_status.A[i], sb: d.timeseries.current_status.B[i], sc: d.timeseries.current_status.C[i],
});
const label = (d: ModeData, st: string) => d.thresholds.electrical.status_labels[st as keyof typeof d.thresholds.electrical.status_labels];

const chapter = (id: string, d: ModeData, i: number): ChapterText => {
  const e = d.thresholds.electrical, I = e.rated_line_A, x = at(d, i);
  const od = row(d, "over_danger"), ud = row(d, "under_danger");
  const healthy = e.i2i1_marks.find((m) => m.case === "healthy")?.value;
  switch (id) {
    case "healthy": return {
      see: `세 케이블 모두 초록 입자가 같은 속도로 흐릅니다. 지금 A ${A(x.a)} / B ${A(x.b)} / C ${A(x.c)} — 정격 선전류 ${A(I)} 근처이고, 균형 지표 I₂/I₁ 은 ${x.i2.toFixed(3)} 입니다.`,
      why: `세 상 전압이 고르고 권선이 온전하면 세 전류의 크기가 같고 위상이 120° 씩 벌어집니다. 그러면 역상분(균형을 깨는 성분)이 거의 0 이라 I₂/I₁ 이 ${healthy} 수준에 머뭅니다.`,
      act: `이 값이 기준선입니다. VIGENT 는 전류 크기뿐 아니라 이 균형 지표를 계속 감시합니다.`,
    };
    case "itsc_4turn": {
      const f = fault(d, "itsc_4turn");
      return {
        see: `A상 케이블과 권선 오버레이가 빨강으로 바뀌고, 권선 안에 빨간 단락 루프가 나타납니다. 지금 A ${A(x.a)} (${pct(x.a / I)}, ${label(d, x.sa)}) — B·C 는 그대로. I₂/I₁ 은 ${x.i2.toFixed(3)}.`,
        why: `권선 코일 4턴의 절연이 깨져 서로 붙으면(ITSC) 그 상의 임피던스가 낮아져 전류가 늘고 세 상의 균형이 깨집니다. 이 화면은 목표 I₂/I₁ ${f?.target_i2i1} 을 재현한 해석식 등가 표현입니다.`,
        act: `절연 저항 측정과 권선 점검을 계획합니다. 초기 단락은 전류 크기 변화가 작을 수 있어 I₂/I₁ 같은 균형 지표로 잡는 것이 빠릅니다.`,
      };
    }
    case "itsc_12turn": {
      const f = fault(d, "itsc_12turn");
      return {
        see: `A상이 더 진한 빨강이고 입자가 빨라집니다. 지금 A ${A(x.a)} (${pct(x.a / I)}) — 위험 과전류 기준 ${A(od.line_A ?? 0)} (×${od.ratio}) 를 크게 넘습니다. I₂/I₁ ${x.i2.toFixed(3)}.`,
        why: `단락된 턴 수가 12 로 늘면 그 상의 전류가 훨씬 커지고 단락 루프에는 큰 순환 전류가 흐릅니다. 이 열이 권선을 국부적으로 태웁니다 (목표 I₂/I₁ ${f?.target_i2i1}).`,
        act: `즉시 정지하고 권선을 점검·재권선합니다. 여기까지 오면 예방이 아니라 수리 단계입니다 — VIGENT 의 목표는 앞 장면(4턴)에서 알리는 것입니다.`,
      };
    }
    case "overload": return {
      see: `세 케이블이 함께 빨강이 되고 입자가 모두 빨라집니다. 지금 A ${A(x.a)} / B ${A(x.b)} / C ${A(x.c)} — 모두 ${label(d, x.sa)}. 그런데 I₂/I₁ 은 ${x.i2.toFixed(3)} 으로 낮습니다.`,
      why: `무거운 짐을 들면 세 상이 똑같이 더 많은 전류를 끌어옵니다. 균형은 유지되므로 역상분은 생기지 않습니다. 즉 '크기'는 문제지만 '균형'은 정상 — 이것이 과부하와 권선 단락을 구분하는 단서입니다.`,
      act: `하중을 정격 이하로 줄입니다. 과전류가 이어지면 권선 온도가 올라가므로 기계적 결함 대시보드의 과부하 장면과 함께 보면 좋습니다.`,
    };
    case "voltage_unbalance": return {
      see: `케이블 색은 세 상 모두 초록인데(지금 A ${A(x.a)} / B ${A(x.b)} / C ${A(x.c)}, 전부 정상 범위), I₂/I₁ 만 ${x.i2.toFixed(3)} 으로 정상값 ${healthy} 의 열 배 가까이 올라갑니다.`,
      why: `공급 전압이 상마다 몇 % 만 달라도 전류 불평형은 그보다 훨씬 크게 나타납니다. 크기 기준으로는 아직 '정상' 이지만 균형은 이미 무너진 상태 — 색보다 숫자가 먼저 말해 주는 장면입니다.`,
      act: `변압기 탭·접속부·한 상에 몰린 단상 부하를 점검합니다. 불평형이 계속되면 한 상이 과열되므로 조기에 잡아야 합니다.`,
    };
    case "single_phasing": return {
      see: `A상 케이블은 파랑(입자가 거의 멈춤), B·C 는 빨강입니다. 지금 A ${A(x.a)} (${label(d, x.sa)}) / B ${A(x.b)} / C ${A(x.c)} (${label(d, x.sb)}). I₂/I₁ ${x.i2.toFixed(3)}.`,
      why: `한 상이 끊기면(결상) 모터는 남은 두 상만으로 같은 힘을 내려고 하므로 그 두 상에 전류가 몰립니다. 끊긴 상은 위험 저전류 기준 ${A(ud.line_A ?? 0)} (×${ud.ratio}) 아래로 떨어져 파랑이 됩니다.`,
      act: `즉시 정지합니다. 퓨즈·접촉기·케이블 접속부를 점검합니다. 결상 운전은 몇 분 안에 권선을 태울 수 있습니다.`,
    };
    case "no_load": return {
      see: `세 케이블이 모두 파랑이고 입자가 느립니다. 지금 A ${A(x.a)} / B ${A(x.b)} / C ${A(x.c)} — 정격의 ${pct(x.a / I)} 로 ${label(d, x.sa)} 범위. 균형은 유지되어 I₂/I₁ ${x.i2.toFixed(3)}.`,
      why: `짐이 없으면 힘을 낼 필요가 없어 자화 전류(자석 역할을 만드는 최소 전류)만 흐릅니다. 결상과 달리 세 상이 고르게 낮은 것이 특징입니다.`,
      act: `그 자체는 고장이 아닙니다. 다만 기동 후에도 계속 이 상태면 커플링 이탈·와이어 로프 이상처럼 부하가 실제로 걸리지 않는 문제를 의심합니다.`,
    };
    default: return { see: "", why: "", act: "" };
  }
};

const faultCards = (d: ModeData): FaultCardText[] => {
  const e = d.thresholds.electrical, I = e.rated_line_A;
  const od = row(d, "over_danger"), oc = row(d, "over_caution"), uc = row(d, "under_caution"), ud = row(d, "under_danger");
  const f = (k: string) => fault(d, k);
  const rms = (k: string) => (f(k)?.rms_A ?? []).map((v) => v.toFixed(1)).join(" / ");
  return [
    {
      key: "itsc", name: "턴간 단락 ITSC (4턴 → 12턴)", easy: "권선 코일의 선끼리 절연이 깨져 붙어버린 고장",
      cause: "절연 노화(과열·습기·진동), 제조 결함, 서지 전압",
      seen: "고장 상(A) 케이블·권선이 빨강, 권선 안에 빨간 단락 루프가 맥동. 나머지 상은 초록",
      criteria: `A/B/C RMS ${rms("itsc_4turn")} A (4턴) → ${rms("itsc_12turn")} A (12턴) · I₂/I₁ ${f("itsc_4turn")?.target_i2i1} → ${f("itsc_12turn")?.target_i2i1} · 위험 과전류 기준 ${od.line_A} A (×${od.ratio})`,
      ifIgnored: "단락 범위 확대 → 권선 소손, 상간 단락, 화재 위험",
      action: "절연 저항 측정, 서지 비교 시험, 재권선",
      signals: ["I₂/I₁ (역상분 비율)", "상 전류 불평형", "권선 온도"], stepId: "itsc_4turn",
    },
    {
      key: "overload", name: "과부하", easy: "정격보다 무거운 짐을 들어 세 상 전류가 함께 커진 상태",
      cause: "정격 초과 하중, 기계적 저항 증가, 잦은 기동",
      seen: "세 케이블 모두 빨강, 입자 속도 증가. I₂/I₁ 은 낮게 유지",
      criteria: `A/B/C RMS ${rms("overload")} A · 주의 과전류 ${oc.line_A} A (×${oc.ratio}) / 위험 ${od.line_A} A (×${od.ratio}) · I₂/I₁ ≈ ${f("overload")?.i2_over_i1}`,
      ifIgnored: "권선 과열 → 절연 열화 (기계적 결함 대시보드 참고)",
      action: "하중 제한, 운전 패턴 조정",
      signals: ["상 전류 크기 (세 상 동반)", "권선 온도"], stepId: "overload",
    },
    {
      key: "voltage_unbalance", name: "공급전압 불평형", easy: "세 상의 전압이 조금씩 달라 전류 균형이 깨진 상태",
      cause: "변압기 탭 불일치, 접속부 저항, 한 상에 몰린 단상 부하",
      seen: "케이블 색은 초록(정상 범위)인데 I₂/I₁ 게이지만 올라감",
      criteria: `A/B/C RMS ${rms("voltage_unbalance")} A (정상 ${uc.line_A}~${oc.line_A} A 안) · I₂/I₁ ≈ ${f("voltage_unbalance")?.i2_over_i1} (정상 ${e.i2i1_marks.find((m) => m.case === "healthy")?.value})`,
      ifIgnored: "특정 상 과열, 토크 맥동, 베어링 수명 단축",
      action: "전원 측 전압 측정, 접속부·탭 점검, 부하 재배분",
      signals: ["I₂/I₁ (역상분 비율)"], stepId: "voltage_unbalance",
    },
    {
      key: "single_phasing", name: "결상 (한 상 끊김)", easy: "세 줄 중 한 줄이 끊겨 두 줄로만 도는 상태",
      cause: "퓨즈 용단, 접촉기 접점 불량, 케이블 단선·접속 풀림",
      seen: "끊긴 상은 파랑(입자 정지), 남은 두 상은 빨강",
      criteria: `A/B/C RMS ${rms("single_phasing")} A · 위험 저전류 ${ud.line_A} A (×${ud.ratio}) 아래 + 나머지 상 위험 과전류 · I₂/I₁ ≈ ${f("single_phasing")?.i2_over_i1}`,
      ifIgnored: "수 분 내 권선 소손 — 가장 급한 전기 결함",
      action: "즉시 정지, 퓨즈·접촉기·접속부 점검",
      signals: ["상 전류 (한 상 소실)", "I₂/I₁ 급증"], stepId: "single_phasing",
    },
    {
      key: "no_load", name: "무부하 (저전류)", easy: "짐 없이 돌아 자화 전류만 흐르는 상태",
      cause: "부하 미연결, 커플링 이탈, 로프·훅 이상",
      seen: "세 케이블 모두 파랑, 입자 느림, 균형은 유지",
      criteria: `A/B/C RMS ${rms("no_load")} A · 정격 ${I} A 의 ${pct((f("no_load")?.rms_A?.[0] ?? 0) / I)} · 위험 저전류 기준 ${ud.line_A} A 아래`,
      ifIgnored: "고장은 아니지만 부하가 걸리지 않는 원인을 찾아야 함",
      action: "커플링·로프·훅 연결 상태 확인",
      signals: ["상 전류 (세 상 동반 저하)"], stepId: "no_load",
    },
  ];
};

const glossary = (d: ModeData): GlossaryEntry[] => {
  const e = d.thresholds.electrical, m = d.thresholds.motor;
  return [
    { term: "이 화면의 빨강·파랑은 '전류'입니다", body: "애니메이션의 색은 전류가 많은가(빨강) 적은가(파랑)를 뜻합니다. 전압이 아닙니다. 전압 이상은 전류 이상을 일으키는 '원인' 쪽이며, 아래에 그 관계를 풀어 두었습니다." },
    { term: "저전압 → 과전류 (직관과 반대)", body: "전압이 낮아지면 전류도 줄 것 같지만, 짐을 든 유도전동기는 같은 힘을 내야 하므로 부족한 전압을 더 많은 전류로 메웁니다. 그래서 저전압에서 오히려 케이블이 빨강이 되고 권선이 뜨거워집니다." },
    { term: "과전압", body: "무부하나 가벼운 부하에서 전압이 높아지면 자석을 만드는 여자 전류가 늘어 전류가 커지고, 코어의 철손이 늘어 발열합니다. 정성적인 설명이며, 구체적인 배율은 규격 출처가 있을 때만 씁니다." },
    { term: "전압 불평형 → 전류 불평형", body: "세 상 전압이 몇 % 만 달라도 전류 불평형은 훨씬 크게 나타납니다. 그래서 화면에서는 특정 상만 색이 다르거나, 색은 정상인데 I₂/I₁ 만 오르는 모습으로 보입니다." },
    { term: "결상", body: "세 상 중 한 상이 끊긴 것입니다. 끊긴 상은 파랑(저전류), 남은 두 상은 그 몫을 떠안아 빨강(과전류)이 됩니다. 가장 급하게 정지해야 하는 상태입니다." },
    { term: "선전류와 상전류", body: `케이블을 흐르는 전류가 선전류(정격 ${e.rated_line_A} A), 권선 코일 안을 흐르는 전류가 상전류(정격 ${e.rated_phase_A} A)입니다. 이 모터는 ${m.connection === "delta" ? "Δ결선" : m.connection}이라 둘이 √3 배 차이가 나므로 기준표에서 두 열로 나눕니다.` },
    { term: "RMS (실효값)", body: "교류는 순간마다 방향과 크기가 바뀌므로, 같은 열을 내는 직류 크기로 환산한 값(RMS)으로 표시합니다. 차트의 상별 전류가 이 값입니다." },
    { term: "I₂/I₁ (역상분 비율)", body: `세 상 전류를 '같이 도는 성분(정상분 I₁)' 과 '거꾸로 도는 성분(역상분 I₂)' 으로 나눈 뒤 그 비율을 본 것입니다. 균형이 완벽하면 0 에 가깝고(정상 ≈ ${e.i2i1_marks.find((x) => x.case === "healthy")?.value}), 한 상만 달라지면 커집니다. 권선 단락은 전류 크기보다 이 숫자에서 먼저 드러납니다.` },
    { term: "ITSC (권선 층간단락)", body: "코일 선끼리 절연이 깨져 붙어버리는 고장입니다. 붙은 턴 수가 늘수록(4턴 → 12턴) 그 상의 전류와 I₂/I₁ 이 커집니다. 이 화면의 ITSC 는 목표 I₂/I₁ 을 재현한 해석식 등가 표현이며, 전자계 해석(FEM)이나 실측이 아닙니다." },
    { term: "슬로모션", body: `실제 ${m.frequency_Hz} Hz 전류는 1초에 ${m.frequency_Hz}번 방향이 바뀌어 눈으로 볼 수 없습니다. 입자 흐름은 ${Math.round(1 / e.slowmo_factor)}배 느리게 그린 것입니다.` },
  ];
};

export const electrical: ModeContent = { chapter, faultCards, glossary };
