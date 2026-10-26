// 첫 화면: 두 대시보드 중 하나를 고른다. 여기서는 어떤 결함 정보도 섞지 않는다.
export function Landing() {
  return (
    <div className="landing">
      <div style={{ textAlign: "center" }}>
        <div className="dim" style={{ letterSpacing: ".1em" }}>VIGENT · 크레인 권상 모터 디지털 트윈</div>
        <h1>모터 결함 시각화 대시보드</h1>
        <p className="muted">한 화면에는 한 가지 결함 유형만 보여줍니다. 보실 항목을 고르세요.</p>
      </div>
      <div className="pick">
        <a href="#/mechanical">
          <h2>1. 기계적 결함</h2>
          <div className="muted">부품이 뜨거워지는 과정을 색으로 봅니다</div>
          <div className="sample">
            <span style={{ background: "#8c9ea6" }} title="정상(원래 재질)" />
            <span style={{ background: "#e69e38" }} title="주의" />
            <span style={{ background: "#f27a1f" }} title="경고" />
            <span style={{ background: "#ff2e0a", boxShadow: "0 0 10px #ff2e0a" }} title="위험(발광)" />
          </div>
          <div className="dim">베어링 열화 · 축 정렬 불량 · 냉각팬 고장 · 브레이크 끌림 · 과부하</div>
        </a>
        <a href="#/electrical">
          <h2>2. 전기적 결함</h2>
          <div className="muted">세 줄의 전류가 어떻게 흐르는지 색으로 봅니다</div>
          <div className="sample">
            <span style={{ background: "#ff140d" }} title="과전류" />
            <span style={{ background: "#26f259" }} title="정상" />
            <span style={{ background: "#1a59ff" }} title="저전류" />
          </div>
          <div className="dim">턴간 단락(ITSC) · 과부하 · 전압 불평형 · 결상 · 무부하</div>
        </a>
        <a href="#/status">
          <h2>3. 모터 상태 보드</h2>
          <div className="muted">현대 HLP-2.2/4(M1) 한 대의 안전·경고·위험을 한눈에 봅니다</div>
          <div className="sample">
            <span style={{ background: "#26f259" }} title="안전" />
            <span style={{ background: "#ff731a" }} title="경고" />
            <span style={{ background: "#ff2e0a", boxShadow: "0 0 10px #ff2e0a" }} title="위험" />
          </div>
          <div className="dim">현대 HLP-2.2/4 · 2.2 kW 4극 (카탈로그 사양, 해석 기준 모터) · 판정 엔진 · 상태·원인·조치 한눈에</div>
        </a>
      </div>
      <div className="dim">시뮬레이션 기반 추정값 · 오프라인 동작 · F 키: 발표 모드</div>
    </div>
  );
}
