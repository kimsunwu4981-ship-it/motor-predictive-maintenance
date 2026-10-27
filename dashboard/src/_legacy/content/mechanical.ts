import type { ModeData } from "../../data";
import type { ChapterText, FaultCardText, GlossaryEntry, ModeContent } from "./types";

// ---- 도우미: 숫자는 전부 JSON 에서 ----
const part = (d: ModeData, key: string) => d.thresholds.thermal.parts.find((p) => p.key === key)!;
const fault = (d: ModeData, key: string) => d.faults.items.find((f) => f.key === key);
const tempAt = (d: ModeData, key: string, i: number) => d.timeseries.temperature_C[key][i];
const stageKo = (d: ModeData, key: string, i: number) => d.thresholds.thermal.stage_labels[d.timeseries.stage[key][i]];
const C = (v: number) => `${v.toFixed(0)} °C`;
const vibAt = (d: ModeData, i: number) => `${d.timeseries.vibration_mms[i].toFixed(1)} mm/s (ISO 20816-3 ${d.timeseries.iso_zone[i]})`;

const chapter = (id: string, d: ModeData, i: number): ChapterText => {
  const brg = part(d, "bearing_de"), wdg = part(d, "winding"), shaft = part(d, "shaft"), frame = part(d, "frame");
  const Tb = tempAt(d, "bearing_de", i), Tw = tempAt(d, "winding", i), Ts = tempAt(d, "shaft", i), Tf = tempAt(d, "frame", i);
  switch (id) {
    case "normal": return {
      see: `모든 부품이 원래 재질 색 그대로입니다. 지금 권선 ${C(Tw)}, 구동측 베어링 ${C(Tb)} — 각각 허용 상한(권선 ${wdg.normal_max_C} °C, 베어링 ${brg.normal_max_C} °C) 아래입니다.`,
      why: `정격 부하에서도 권선에는 동손(전류 때문에 생기는 열), 코어에는 철손, 베어링에는 마찰열이 생기지만, 냉각팬이 그만큼을 밖으로 내보내 온도가 일정하게 유지됩니다.`,
      act: `이 상태의 온도를 '기준선'으로 기록해 둡니다. VIGENT 는 이 기준선에서 벗어나는 순간을 잡아냅니다.`,
    };
    case "bearing_fault": {
      const f = fault(d, "bearing_de_fault");
      return {
        see: `구동측(DE) 베어링만 주황에서 빨강으로 변합니다. 지금 ${C(Tb)} — ${stageKo(d, "bearing_de", i)} 단계 (주의 ${brg.normal_max_C} / 경고 ${brg.caution_max_C} / 위험 ${brg.warning_max_C} °C 초과). 다른 부품은 아직 정상입니다.`,
        why: `윤활이 부족하거나 구름면이 닳으면 마찰 손실이 커집니다. 이 시나리오는 베어링 손실을 ${f?.loss_multiplier}배로 두었고, 진동도 ${vibAt(d, i)} 로 올라갑니다. 열이 국부적으로 나서 베어링 자리만 붉어집니다.`,
        act: `윤활 상태와 진동을 점검하고 베어링 교체를 계획합니다. 아직 베어링만 바꾸면 되는 단계이며, 방치하면 축과 엔드실드까지 상합니다.`,
      };
    }
    case "misalignment": {
      const f = fault(d, "misalignment");
      return {
        see: `베어링 열은 식어 가고, 대신 축(샤프트)과 고정자 코어 쪽이 따뜻해집니다. 지금 축 ${C(Ts)} (허용 ${shaft.normal_max_C} °C), 진동 ${vibAt(d, i)}.`,
        why: `커플링 정렬이 틀어지면 축이 회전할 때마다 휘어 양쪽 베어링에 하중이 걸립니다. 이 시나리오는 베어링 손실 ${f?.loss_multiplier}배에 축 발열을 더했습니다.`,
        act: `레이저 정렬기로 커플링을 재정렬합니다. 정렬 불량은 진동 신호에서 먼저 드러나므로 온도가 오르기 전에 잡을 수 있습니다.`,
      };
    }
    case "fan_failure": {
      const f = fault(d, "fan_failure");
      return {
        see: `특정 부품이 아니라 하우징부터 권선까지 전체가 고르게 올라갑니다. 지금 하우징 ${C(Tf)} (허용 ${frame.normal_max_C} °C), 권선 ${C(Tw)}.`,
        why: `냉각팬이 서면 바람으로 식히던 것이 자연 대류로 바뀌어 열이 빠져나가는 통로가 좁아집니다. 이 시나리오는 외부 방열 저항을 ${f?.r_amb_multiplier}배로 두었습니다. 열원은 그대로인데 출구가 막힌 셈입니다.`,
        act: `팬 커버와 날개를 확인하고 먼지를 제거하거나 팬을 교체합니다. 그 전까지는 부하를 낮춥니다.`,
      };
    }
    case "brake_drag": {
      const f = fault(d, "brake_drag");
      return {
        see: `축이 먼저 붉어지고 로터로 열이 번집니다. 지금 축 ${C(Ts)} — ${stageKo(d, "shaft", i)} 단계.`,
        why: `브레이크가 완전히 떨어지지 않으면 제동면이 계속 스치며 마찰열을 냅니다. 이 시나리오는 ${f?.extra_loss_W} W 의 열이 축으로 들어오는 것으로 두었습니다.`,
        act: `브레이크 간극(에어갭)을 조정하고 라이닝 마모를 점검합니다. 축 온도가 다른 부품보다 먼저 오르는 것이 이 결함의 특징입니다.`,
      };
    }
    case "overload": {
      const f = fault(d, "overload");
      return {
        see: `고정자 권선이 가장 먼저 경고 단계에 닿습니다. 지금 권선 ${C(Tw)} — ${stageKo(d, "winding", i)} (경고 ${wdg.caution_max_C} / 위험 ${wdg.warning_max_C} °C 초과).`,
        why: `부하가 정격의 ${((f?.load_multiplier ?? 1) * 100).toFixed(0)} % 가 되면 전류가 늘고, 권선의 동손은 전류의 제곱에 비례해 커집니다. 그래서 다른 부품보다 권선이 먼저 한계에 닿습니다.`,
        act: `부하를 정격 이하로 제한합니다. 권선 절연은 온도 한계를 넘기면 수명이 급격히 줄어듭니다 (${wdg.note}).`,
      };
    }
    case "cooldown": {
      const lt = d.scenarios.lead_time;
      const lead = lt.lead_sim_s != null ? `시뮬레이션 약 ${(lt.lead_sim_s / 60).toFixed(1)} 분` : "계산 불가";
      return {
        see: `결함을 제거하자 모든 부품이 서서히 식습니다. 지금 권선 ${C(Tw)}, 베어링 ${C(Tb)}.`,
        why: `열원이 사라지고 냉각만 남았기 때문입니다. 온도는 올라갈 때보다 천천히 내려오므로, 결함을 늦게 잡을수록 회복에도 시간이 듭니다.`,
        act: `VIGENT 는 '주의' 단계에 들어서는 순간 경보를 보냅니다. 이 시나리오에서 주의 → 위험까지의 여유(리드 타임)는 ${lead}이며, 그 안에 정비하면 정지 손실을 막을 수 있습니다.`,
      };
    }
    default: return { see: "", why: "", act: "" };
  }
};

const partReason = (key: string): string => ({
  bearing_de: "마모·윤활 부족으로 마찰이 커짐",
  bearing_nde: "마모·윤활 부족으로 마찰이 커짐 (반부하측)",
  winding: "전류가 흐르며 생기는 동손(I²R) — 과부하·단락에서 급증",
  rotor: "슬립에 따른 로터 손실, 권선보다 고온이 정상",
  shaft: "베어링·브레이크의 열이 전도로 유입",
  stator_core: "자속이 바뀌며 생기는 철손",
  endshield_de: "베어링 열이 전도로 유입",
  endshield_nde: "베어링 열이 전도로 유입",
  frame: "내부 열을 바깥으로 내보내는 통로 — 팬이 서면 막힘",
}[key] ?? "");

const faultCards = (d: ModeData): FaultCardText[] => {
  const brg = part(d, "bearing_de"), wdg = part(d, "winding"), shaft = part(d, "shaft"), frame = part(d, "frame");
  const f = (k: string) => fault(d, k);
  return [
    {
      key: "bearing_de_fault", name: "구동측(DE) 베어링 결함", easy: "축을 받치는 구슬 베어링이 닳거나 기름이 마른 상태",
      cause: "윤활 부족, 이물질, 과하중, 장기 사용에 따른 구름면 손상",
      seen: "구동측 베어링 자리만 주황 → 빨강 발광. 엔드실드가 반투명해져 안쪽 베어링이 보임",
      criteria: `베어링 ${brg.normal_max_C} °C 초과 주의, ${brg.caution_max_C} °C 초과 경고, ${brg.warning_max_C} °C 초과 위험 · 진동 ${f("bearing_de_fault")?.vibration_mms} mm/s`,
      ifIgnored: "베어링 고착 → 축 손상, 로터가 고정자에 닿아 모터 전체 교체",
      action: "재윤활 또는 베어링 교체, 진동 추세 관리",
      signals: ["온도 (베어링)", "진동 (BPFO/BPFI)"], stepId: "bearing_fault",
    },
    {
      key: "misalignment", name: "축 정렬 불량 (오정렬)", easy: "모터 축과 감속기 축이 한 줄로 맞지 않은 상태",
      cause: "설치 오차, 기초 침하, 열팽창, 커플링 마모",
      seen: "양쪽 베어링과 축이 함께 따뜻해짐 (베어링 결함보다 넓게 퍼짐)",
      criteria: `베어링 손실 ${f("misalignment")?.loss_multiplier}배 · 진동 ${f("misalignment")?.vibration_mms} mm/s · 축 ${shaft.normal_max_C} °C 초과 주의`,
      ifIgnored: "베어링 조기 파손, 커플링 파손, 축 피로 균열",
      action: "레이저 정렬로 재정렬, 기초 볼트 점검",
      signals: ["진동 (1×·2× 회전 성분)", "온도 (베어링·축)"], stepId: "misalignment",
    },
    {
      key: "fan_failure", name: "냉각팬 고장", easy: "모터 뒤쪽에서 바람을 보내 식히는 팬이 멈춘 상태",
      cause: "팬 날개 파손, 커버 막힘(먼지·이물질), 팬 고정 불량",
      seen: "하우징부터 안쪽까지 전체가 고르게 올라감. 특정 부위가 아니라 전부 주황빛",
      criteria: `외부 방열 저항 ${f("fan_failure")?.r_amb_multiplier}배 · 하우징 ${frame.normal_max_C} °C 초과 주의 · 권선 ${wdg.normal_max_C} °C 초과 주의`,
      ifIgnored: "권선 절연 열화 → 단락으로 이어질 수 있음",
      action: "팬·커버 청소 또는 교체, 그 전까지 부하 저감",
      signals: ["온도 (하우징·권선 동반 상승)"], stepId: "fan_failure",
    },
    {
      key: "brake_drag", name: "브레이크 끌림", easy: "정지용 브레이크가 완전히 풀리지 않고 계속 스치는 상태",
      cause: "에어갭 조정 불량, 라이닝 마모, 코일 전압 부족, 복귀 스프링 이상",
      seen: "축(샤프트)이 먼저 붉어지고 로터로 번짐",
      criteria: `축으로 유입되는 발열 ${f("brake_drag")?.extra_loss_W} W · 축 ${shaft.caution_max_C} °C 초과 경고`,
      ifIgnored: "라이닝 소손, 제동력 상실 — 크레인에서는 낙하 위험",
      action: "에어갭 조정, 라이닝·스프링 점검, 코일 전압 확인",
      signals: ["온도 (축·로터)", "진동"], stepId: "brake_drag",
    },
    {
      key: "overload", name: "과부하 (열 관점)", easy: "정격보다 무거운 짐을 계속 들어 올리는 상태",
      cause: "정격 초과 하중, 잦은 기동·정지, 기계적 저항 증가",
      seen: "고정자 권선이 가장 먼저 주황 → 빨강",
      criteria: `부하율 ${((f("overload")?.load_multiplier ?? 1) * 100).toFixed(0)} % · 권선 ${wdg.normal_max_C} °C 초과 주의, ${wdg.caution_max_C} °C 초과 경고, ${wdg.warning_max_C} °C 초과 위험 (${wdg.note})`,
      ifIgnored: "절연 수명 급감 → 권선 단락, 소손",
      action: "하중 제한, 운전 패턴 조정, 권선 온도 추세 관리",
      signals: ["온도 (권선)", "전류 (세 상 동반 상승)"], stepId: "overload",
    },
  ];
};

const glossary = (d: ModeData): GlossaryEntry[] => {
  const brg = part(d, "bearing_de"), wdg = part(d, "winding"), rot = part(d, "rotor");
  return [
    { term: "발열의 세 가지 원인", body: "동손(권선에 전류가 흐르며 생기는 열, 전류의 제곱에 비례), 철손(코어의 자속이 바뀌며 생기는 열), 마찰열(베어링·브레이크). 결함마다 커지는 열원이 달라서 뜨거워지는 부품도 다릅니다." },
    { term: "열이 번지는 원리", body: "부품끼리 맞닿은 곳으로는 전도(고체 안에서 열이 옮겨감), 표면에서 공기로는 대류(바람이 열을 실어 나름)로 빠져나갑니다. 냉각팬이 서면 대류가 약해져 전체가 뜨거워지고, 베어링이 나빠지면 전도 경로가 막혀 그 자리에만 열이 고입니다." },
    { term: "집중정수 열회로 (9노드)", body: "모터를 권선·코어·로터·축·베어링 2개·엔드실드 2개·하우징 등 9개 덩어리로 나누고, 각 덩어리의 온도를 하나의 숫자로 계산하는 모델입니다. 부품 안의 온도 차이(열점)는 표현하지 못하므로, 이 화면의 색은 '부품 하나에 한 가지'입니다." },
    { term: "부품마다 다른 허용 온도", body: `같은 80 °C 라도 베어링(${brg.normal_max_C} °C 부터 주의, ${brg.note})에게는 위험 신호이고 로터(${rot.normal_max_C} °C 까지 정상, ${rot.note})에게는 평범한 온도입니다. 권선은 ${wdg.note} 으로 ${wdg.warning_max_C} °C 를 넘기면 위험으로 봅니다. 그래서 색은 절대 온도가 아니라 부품별 기준으로 정합니다.` },
    { term: "주의 → 경고 → 위험", body: "정상 상한을 넘으면 주의(주황), 그 위 구간은 경고(붉은 주황), 마지막 상한을 넘으면 위험(빨강 발광·깜빡임)입니다. VIGENT 는 주의 단계에서 경보를 보내므로 위험에 닿기 전에 손쓸 시간이 생깁니다." },
    { term: "리드 타임", body: "경보가 울린 시점부터 실제로 위험에 도달하는 시점까지의 여유 시간입니다. 차트의 주황 점선(조기 경보)과 빨간 선(위험 도달) 사이가 그것이며, 이 값이 사업 가치의 핵심입니다." },
    { term: "ISO 20816-3 진동 등급", body: "회전 기계의 진동 크기를 정상 / 주시 / 계획 / 조치 네 등급으로 나누는 국제 기준입니다. 베어링 결함이나 정렬 불량은 온도보다 진동에서 먼저 드러나는 경우가 많아, VIGENT 는 온도와 진동을 함께 봅니다." },
    { term: "시뮬레이션 배속", body: "화면의 1초는 열 시뮬레이션에서는 수십~수백 초입니다(구간마다 다르며 설명 패널 아래에 표시). 실제 모터는 이렇게 빨리 뜨거워지지 않습니다 — 발표 시간 안에 보여주기 위한 압축입니다." },
  ];
};

export const mechanical: ModeContent = { chapter, faultCards, glossary, partReason };
