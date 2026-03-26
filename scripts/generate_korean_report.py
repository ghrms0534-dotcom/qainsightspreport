from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, List


# --------------------------------------------------------------------------------------
# JSON 파일 읽기
# 없거나 깨지면 예외가 날 수 있으므로,
# 이 스크립트는 "입력 파일이 정상적으로 생성되었다"는 전제에서 사용한다.
# 보통 run_pipeline.py 에서 호출됨.
# --------------------------------------------------------------------------------------
def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# 밀리초(ms) 표시용 포맷 함수
# 숫자면 "1,234.56 ms" 형태
# 숫자 아니면 "-"
# --------------------------------------------------------------------------------------
def fmt_ms(value: Any) -> str:
    try:
        return f"{float(value):,.2f} ms"
    except Exception:
        return "-"


# --------------------------------------------------------------------------------------
# 일반 숫자 포맷
# 정수면 천단위 콤마
# 실수면 소수점 2자리
# --------------------------------------------------------------------------------------
def fmt_num(value: Any) -> str:
    try:
        if isinstance(value, int):
            return f"{value:,}"
        return f"{float(value):,.2f}"
    except Exception:
        return "-"


# --------------------------------------------------------------------------------------
# 퍼센트 표시용
# --------------------------------------------------------------------------------------
def fmt_percent(value: Any) -> str:
    try:
        return f"{float(value):,.2f}%"
    except Exception:
        return "-"


# --------------------------------------------------------------------------------------
# HTML <ul> 내부용 <li> 리스트 생성
# gate 사유 목록 같은 데 사용
# --------------------------------------------------------------------------------------
def list_items(items: List[str]) -> str:
    if not items:
        return "<li>없음</li>"
    return "".join(f"<li>{html.escape(str(item))}</li>" for item in items)


# --------------------------------------------------------------------------------------
# 느린 요청 상세 테이블 행 생성
# summary["slowest_labels"] 용
# --------------------------------------------------------------------------------------
def table_rows(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return '<tr><td colspan="4">데이터 없음</td></tr>'

    out = []
    for row in rows:
        out.append(
            "<tr>"
            f'<td>{html.escape(str(row.get("label", "-")))}</td>'
            f'<td>{fmt_num(row.get("count", 0))}</td>'
            f'<td>{fmt_ms(row.get("avg_ms", 0))}</td>'
            f'<td>{fmt_ms(row.get("max_ms", 0))}</td>'
            "</tr>"
        )
    return "".join(out)


# --------------------------------------------------------------------------------------
# 실패 샘플 테이블 행 생성
# summary["failed_samples"] 용
# 너무 길면 최대 10개까지만 보여줌
# --------------------------------------------------------------------------------------
def failure_rows(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return '<tr><td colspan="5">실패 샘플 없음</td></tr>'

    out = []
    for row in rows[:10]:
        out.append(
            "<tr>"
            f'<td>{html.escape(str(row.get("label", "-")))}</td>'
            f'<td>{html.escape(str(row.get("responseCode", "-")))}</td>'
            f'<td>{html.escape(str(row.get("responseMessage", "-")))}</td>'
            f'<td>{html.escape(str(row.get("failureMessage", "-")))}</td>'
            f'<td>{fmt_ms(row.get("elapsed", 0))}</td>'
            "</tr>"
        )
    return "".join(out)


# --------------------------------------------------------------------------------------
# baseline 비교 키를 사람이 보기 쉬운 한글 라벨로 바꿔줌
# compare_baseline.py 에서 생성하는 필드명을 기준으로 작성
# --------------------------------------------------------------------------------------
def compare_key_label(key: str) -> str:
    mapping = {
        "baseline_name": "기준선 이름",
        "delta_p95_ms": "p95 응답시간 변화량",
        "delta_p99_ms": "p99 응답시간 변화량",
        "delta_error_rate_percent": "에러율 변화량",
        "delta_throughput_rps": "처리량 변화량",
        "current_p95_ms": "현재 p95 응답시간",
        "baseline_p95_ms": "기준선 p95 응답시간",
        "current_p99_ms": "현재 p99 응답시간",
        "baseline_p99_ms": "기준선 p99 응답시간",
        "current_error_rate_percent": "현재 에러율",
        "baseline_error_rate_percent": "기준선 에러율",
        "current_throughput_rps": "현재 처리량",
        "baseline_throughput_rps": "기준선 처리량",
        # 혹시 예전 형식이 남아 있어도 표시되도록 보정
        "p95_ms_delta": "p95 응답시간 변화량",
        "p99_ms_delta": "p99 응답시간 변화량",
        "avg_ms_delta": "평균 응답시간 변화량",
        "error_rate_percent_delta": "에러율 변화량",
        "throughput_rps_delta": "처리량 변화량",
        "summary": "요약",
    }
    return mapping.get(key, key)


# --------------------------------------------------------------------------------------
# baseline 비교 값 표시 방식
# ms / percent / rps 구분해서 출력
# --------------------------------------------------------------------------------------
def compare_value_label(key: str, value: Any) -> str:
    if value is None:
        return "-"

    if key == "baseline_name":
        return html.escape(str(value))

    if isinstance(value, (int, float)):
        if "ms" in key:
            return f"{value:+,.2f} ms" if "delta" in key else f"{value:,.2f} ms"
        if "percent" in key or "error_rate" in key:
            return f"{value:+,.2f}%" if "delta" in key else f"{value:,.2f}%"
        if "throughput" in key or "rps" in key:
            return f"{value:+,.2f} rps" if "delta" in key else f"{value:,.2f} rps"
        return f"{value:+,.2f}"

    return html.escape(str(value))


# --------------------------------------------------------------------------------------
# baseline 비교 항목에 대한 참고 설명
# --------------------------------------------------------------------------------------
def compare_note(key: str) -> str:
    if key == "baseline_name":
        return "비교 기준으로 사용한 기준선 이름"
    if key in ("delta_p95_ms", "p95_ms_delta"):
        return "음수면 개선, 양수면 악화"
    if key in ("delta_p99_ms", "p99_ms_delta"):
        return "극단 지연 구간 변화"
    if key in ("delta_error_rate_percent", "error_rate_percent_delta"):
        return "음수면 에러율 감소, 양수면 증가"
    if key in ("delta_throughput_rps", "throughput_rps_delta"):
        return "양수면 처리량 증가, 음수면 감소"
    if key in ("avg_ms_delta",):
        return "음수면 평균 응답시간 개선"
    return ""


# --------------------------------------------------------------------------------------
# baseline 비교 테이블 전체 행 생성
# compare_baseline.py 결과가 없으면 '기준선 비교 없음' 표시
# --------------------------------------------------------------------------------------
def compare_rows(compare: Dict[str, Any]) -> str:
    if not compare:
        return '<tr><td colspan="3">기준선 비교 없음</td></tr>'

    preferred_order = [
        "baseline_name",
        "delta_p95_ms",
        "delta_p99_ms",
        "delta_error_rate_percent",
        "delta_throughput_rps",
        "current_p95_ms",
        "baseline_p95_ms",
        "current_p99_ms",
        "baseline_p99_ms",
        "current_error_rate_percent",
        "baseline_error_rate_percent",
        "current_throughput_rps",
        "baseline_throughput_rps",
        # 구버전 대비 호환용
        "p95_ms_delta",
        "p99_ms_delta",
        "avg_ms_delta",
        "error_rate_percent_delta",
        "throughput_rps_delta",
    ]

    keys = [k for k in preferred_order if k in compare]
    extra_keys = [k for k in compare.keys() if k not in keys and k != "summary"]
    keys.extend(extra_keys)

    summary_note = str(compare.get("summary", "")).strip()

    out = []
    for key in keys:
        value = compare.get(key)
        note = compare_note(key)
        if summary_note:
            note = f"{note} / {summary_note}" if note else summary_note

        out.append(
            "<tr>"
            f"<td>{html.escape(compare_key_label(key))}</td>"
            f"<td>{compare_value_label(key, value)}</td>"
            f"<td>{html.escape(note)}</td>"
            "</tr>"
        )

    return "".join(out)


# --------------------------------------------------------------------------------------
# 응답시간 막대 그래프 HTML 생성
# summary.json 의 avg/p90/p95/p99/max 값을 시각화
# --------------------------------------------------------------------------------------
def build_metric_bars(summary: Dict[str, Any]) -> str:
    metrics = [
        ("평균", float(summary.get("avg_ms", 0) or 0)),
        ("P90", float(summary.get("p90_ms", 0) or 0)),
        ("P95", float(summary.get("p95_ms", 0) or 0)),
        ("P99", float(summary.get("p99_ms", 0) or 0)),
        ("최대", float(summary.get("max_ms", 0) or 0)),
    ]
    max_val = max([v for _, v in metrics] + [1.0])

    rows = []
    for label, value in metrics:
        width = max(2, int((value / max_val) * 100))
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{html.escape(label)}</div>
              <div class="bar-track">
                <div class="bar-fill" style="width: {width}%;"></div>
              </div>
              <div class="bar-value">{fmt_ms(value)}</div>
            </div>
            """
        )
    return "".join(rows)


# --------------------------------------------------------------------------------------
# 응답코드 분포 막대 그래프 HTML 생성
# --------------------------------------------------------------------------------------
def build_code_bars(summary: Dict[str, Any]) -> str:
    code_map = summary.get("response_code_distribution", {}) or {}
    if not code_map:
        return '<div class="empty-chart">응답코드 데이터 없음</div>'

    max_val = max([int(v) for v in code_map.values()] + [1])
    rows = []
    for code, count in code_map.items():
        count_int = int(count or 0)
        width = max(2, int((count_int / max_val) * 100))
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">HTTP {html.escape(str(code))}</div>
              <div class="bar-track code-track">
                <div class="bar-fill code-fill" style="width: {width}%;"></div>
              </div>
              <div class="bar-value">{fmt_num(count_int)}건</div>
            </div>
            """
        )
    return "".join(rows)


# --------------------------------------------------------------------------------------
# 느린 요청 상위 목록 막대 그래프 HTML 생성
# --------------------------------------------------------------------------------------
def build_slow_bars(summary: Dict[str, Any]) -> str:
    slow_rows = summary.get("slowest_labels", []) or []
    if not slow_rows:
        return '<div class="empty-chart">느린 요청 데이터 없음</div>'

    max_val = max([float(x.get("avg_ms", 0) or 0) for x in slow_rows] + [1.0])
    rows = []
    for row in slow_rows[:10]:
        label = str(row.get("label", "-"))
        avg_ms = float(row.get("avg_ms", 0) or 0)
        width = max(2, int((avg_ms / max_val) * 100))
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label long">{html.escape(label)}</div>
              <div class="bar-track slow-track">
                <div class="bar-fill slow-fill" style="width: {width}%;"></div>
              </div>
              <div class="bar-value">{fmt_ms(avg_ms)}</div>
            </div>
            """
        )
    return "".join(rows)


# --------------------------------------------------------------------------------------
# 메타데이터 테이블 행 생성
# run_metadata.json 기준
# --------------------------------------------------------------------------------------
def metadata_rows(metadata: Dict[str, Any]) -> str:
    if not metadata:
        return '<tr><td colspan="2">메타데이터 없음</td></tr>'

    rows = []
    preferred_order = [
        "플랜명",
        "결과폴더",
        "원본결과파일",
        "HTML리포트폴더",
        "사용자수",
        "램프업",
        "반복수",
        "지속시간초",
    ]

    used = set()
    for key in preferred_order:
        if key in metadata:
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(key))}</td>"
                f"<td>{html.escape(str(metadata.get(key, '-')))}</td>"
                "</tr>"
            )
            used.add(key)

    for key, value in metadata.items():
        if key in used:
            continue
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(key))}</td>"
            f"<td>{html.escape(str(value))}</td>"
            "</tr>"
        )

    return "".join(rows)


def main():
    # ----------------------------------------------------------------------------------
    # 입력 인자:
    # --summary   : summarize_jtl.py 가 만든 summary.json
    # --gate      : summarize_jtl.py 가 만든 gate.json
    # --out-dir   : 결과 폴더
    # --compare   : compare_baseline.py 결과(json), 없으면 생략 가능
    # --metadata  : run_pipeline.py 가 만든 run_metadata.json, 없으면 생략 가능
    # ----------------------------------------------------------------------------------
    parser = argparse.ArgumentParser(description="QA Insights 한글 HTML 보고서 생성")
    parser.add_argument("--summary", required=True, help="summary.json 경로")
    parser.add_argument("--gate", required=True, help="gate.json 경로")
    parser.add_argument("--out-dir", required=True, help="결과 폴더")
    parser.add_argument("--compare", required=False, help="baseline_compare.json 경로")
    parser.add_argument("--metadata", required=False, help="run_metadata.json 경로")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)

    # ----------------------------------------------------------------------------------
    # 필수 입력 파일 로드
    # ----------------------------------------------------------------------------------
    summary = load_json(Path(args.summary))
    gate = load_json(Path(args.gate))

    # 선택 입력 파일 로드
    compare = load_json(Path(args.compare)) if args.compare and Path(args.compare).exists() else {}
    metadata = load_json(Path(args.metadata)) if args.metadata and Path(args.metadata).exists() else {}

    # ----------------------------------------------------------------------------------
    # 추가 텍스트 파일 로드
    # 이 파일들은 없어도 보고서 생성은 가능
    # ----------------------------------------------------------------------------------
    qwen_text = (
        (out_dir / "qwen_summary.txt").read_text(encoding="utf-8")
        if (out_dir / "qwen_summary.txt").exists()
        else ""
    )
    gpt_text = (
        (out_dir / "gptoss_analysis.txt").read_text(encoding="utf-8")
        if (out_dir / "gptoss_analysis.txt").exists()
        else ""
    )
    llm_report = (
        (out_dir / "llm_report.md").read_text(encoding="utf-8")
        if (out_dir / "llm_report.md").exists()
        else ""
    )
    summary_text = (
        (out_dir / "summary.txt").read_text(encoding="utf-8")
        if (out_dir / "summary.txt").exists()
        else ""
    )

    # ----------------------------------------------------------------------------------
    # 화면 상단에 보여줄 주요 값 계산
    # ----------------------------------------------------------------------------------
    plan_name = str(gate.get("plan_name", metadata.get("플랜명", "-")))
    run_dir_text = str(out_dir)

    total_requests = int(summary.get("total_requests", 0) or 0)
    success_count = int(summary.get("success_count", 0) or 0)
    fail_count = int(summary.get("fail_count", 0) or 0)

    success_rate = (success_count / total_requests * 100) if total_requests else 0.0
    error_rate = float(summary.get("error_rate_percent", 0) or 0)

    # 막대 그래프 HTML 조각
    metric_bars_html = build_metric_bars(summary)
    code_bars_html = build_code_bars(summary)
    slow_bars_html = build_slow_bars(summary)

    # 상태 표시
    gate_passed = bool(gate.get("passed", False))
    status_text = "통과 PASS" if gate_passed else "실패 FAIL"
    status_bg = "var(--success-soft)" if gate_passed else "var(--danger-soft)"
    status_fg = "var(--success)" if gate_passed else "var(--danger)"

    # ----------------------------------------------------------------------------------
    # 최종 HTML 생성
    # report.html 하나만 만든다.
    # ----------------------------------------------------------------------------------
    html_text = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>QA Insights 성능 보고서</title>
  <style>
    :root {{
      --bg: #f6f8fc;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --line: #e5e7eb;
      --primary: #4f46e5;
      --primary-soft: #eef2ff;
      --success: #16a34a;
      --success-soft: #dcfce7;
      --danger: #dc2626;
      --danger-soft: #fee2e2;
      --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
      --radius: 18px;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}

    .wrap {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 20px 40px;
    }}

    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 20px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }}

    .title {{
      font-size: 42px;
      font-weight: 800;
      margin: 0 0 8px;
      letter-spacing: -0.5px;
    }}

    .subtitle {{
      color: var(--muted);
      font-size: 14px;
      line-height: 1.7;
    }}

    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 12px 18px;
      border-radius: 999px;
      font-size: 15px;
      font-weight: 800;
      background: {status_bg};
      color: {status_fg};
      box-shadow: var(--shadow);
    }}

    .section-card {{
      background: var(--card);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 22px;
      margin-top: 18px;
    }}

    .section-title {{
      margin: 0 0 14px;
      font-size: 24px;
      font-weight: 800;
    }}

    .links a {{
      color: var(--primary);
      text-decoration: none;
      margin-right: 16px;
      font-weight: 700;
    }}

    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}

    .kpi {{
      background: var(--card);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 22px;
      min-height: 132px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}

    .kpi-label {{
      color: var(--muted);
      font-size: 14px;
      font-weight: 700;
    }}

    .kpi-value {{
      font-size: 42px;
      font-weight: 800;
      line-height: 1.1;
      letter-spacing: -0.5px;
    }}

    .kpi-sub {{
      color: var(--muted);
      font-size: 13px;
    }}

    .chart-grid {{
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 18px;
      margin-top: 18px;
    }}

    .chart-card {{
      background: var(--card);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 22px;
      min-height: 320px;
    }}

    .chart-title {{
      margin: 0 0 16px;
      font-size: 20px;
      font-weight: 800;
    }}

    .bars {{
      display: flex;
      flex-direction: column;
      gap: 14px;
      margin-top: 6px;
    }}

    .bar-row {{
      display: grid;
      grid-template-columns: 120px minmax(0, 1fr) 110px;
      gap: 12px;
      align-items: center;
    }}

    .bar-label {{
      font-size: 14px;
      font-weight: 700;
      color: #334155;
    }}

    .bar-label.long {{
      font-size: 13px;
      line-height: 1.4;
      word-break: break-word;
    }}

    .bar-track {{
      width: 100%;
      height: 18px;
      background: #e5e7eb;
      border-radius: 999px;
      overflow: hidden;
      position: relative;
    }}

    .bar-fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, #818cf8, #4f46e5);
      min-width: 10px;
    }}

    .code-fill {{
      background: linear-gradient(90deg, #60a5fa, #2563eb);
    }}

    .slow-fill {{
      background: linear-gradient(90deg, #a78bfa, #7c3aed);
    }}

    .bar-value {{
      text-align: right;
      font-size: 13px;
      font-weight: 700;
      color: #0f172a;
      white-space: nowrap;
    }}

    .empty-chart {{
      color: var(--muted);
      font-size: 14px;
      padding: 20px 4px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 14px;
    }}

    th, td {{
      padding: 13px 14px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}

    th {{
      background: var(--primary-soft);
      color: #334155;
      font-weight: 800;
    }}

    tr:last-child td {{
      border-bottom: none;
    }}

    ul {{
      margin: 0;
      padding-left: 20px;
      line-height: 1.8;
    }}

    pre {{
      margin: 0;
      background: #0f172a;
      color: #f8fafc;
      border-radius: 14px;
      padding: 16px;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 13px;
      line-height: 1.7;
    }}

    .meta-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
      margin-top: 18px;
    }}

    @media (max-width: 1100px) {{
      .kpi-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .chart-grid {{ grid-template-columns: 1fr; }}
      .meta-grid {{ grid-template-columns: 1fr; }}
    }}

    @media (max-width: 740px) {{
      .bar-row {{
        grid-template-columns: 1fr;
        gap: 6px;
      }}
      .bar-value {{
        text-align: left;
      }}
    }}

    @media (max-width: 640px) {{
      .wrap {{ padding: 18px 12px 28px; }}
      .title {{ font-size: 30px; }}
      .kpi-grid {{ grid-template-columns: 1fr; }}
      .kpi-value {{ font-size: 34px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1 class="title">QA Insights 성능 보고서</h1>
        <div class="subtitle">
          플랜: {html.escape(plan_name)}<br/>
          결과 폴더: {html.escape(run_dir_text)}
        </div>
      </div>
      <div class="status-badge">
        {status_text}
      </div>
    </div>

    <div class="section-card">
      <h2 class="section-title">종합 요약</h2>
      <ul>{list_items(gate.get('reasons', []))}</ul>
      <div class="links" style="margin-top: 14px;">
        <a href="html/index.html" target="_blank">JMeter 원본 리포트</a>
        <a href="llm_report.md" target="_blank">한글 Markdown 보고서</a>
        <a href="summary.txt" target="_blank">텍스트 요약</a>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi">
        <div class="kpi-label">총 요청 수</div>
        <div class="kpi-value">{fmt_num(total_requests)}</div>
        <div class="kpi-sub">전체 실행된 요청 수</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">성공률</div>
        <div class="kpi-value">{fmt_percent(success_rate)}</div>
        <div class="kpi-sub">성공 요청 비율</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">에러율</div>
        <div class="kpi-value">{fmt_percent(error_rate)}</div>
        <div class="kpi-sub">실패 요청 비율</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">p95 응답시간</div>
        <div class="kpi-value">{fmt_ms(summary.get('p95_ms', 0)).replace(' ms', '')}</div>
        <div class="kpi-sub">95% 요청이 이 시간 이내 완료</div>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="kpi">
        <div class="kpi-label">성공 요청 수</div>
        <div class="kpi-value">{fmt_num(success_count)}</div>
        <div class="kpi-sub">정상 처리 건수</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">실패 요청 수</div>
        <div class="kpi-value">{fmt_num(fail_count)}</div>
        <div class="kpi-sub">오류 발생 건수</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">처리량</div>
        <div class="kpi-value">{fmt_num(summary.get('throughput_rps', 0))}</div>
        <div class="kpi-sub">requests/sec</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">최대 응답시간</div>
        <div class="kpi-value">{fmt_ms(summary.get('max_ms', 0)).replace(' ms', '')}</div>
        <div class="kpi-sub">가장 느린 단건</div>
      </div>
    </div>

    <div class="chart-grid">
      <div class="chart-card">
        <h3 class="chart-title">응답시간 지표 비교</h3>
        <div class="bars">
          {metric_bars_html}
        </div>
      </div>
      <div class="chart-card">
        <h3 class="chart-title">응답코드 분포</h3>
        <div class="bars">
          {code_bars_html}
        </div>
      </div>
    </div>

    <div class="chart-grid">
      <div class="chart-card">
        <h3 class="chart-title">느린 요청 상위 목록</h3>
        <div class="bars">
          {slow_bars_html}
        </div>
      </div>
      <div class="chart-card">
        <h3 class="chart-title">핵심 지표</h3>
        <table>
          <thead>
            <tr><th>항목</th><th>값</th><th>설명</th></tr>
          </thead>
          <tbody>
            <tr><td>평균 응답시간</td><td>{fmt_ms(summary.get('avg_ms', 0))}</td><td>전체 평균</td></tr>
            <tr><td>p90 응답시간</td><td>{fmt_ms(summary.get('p90_ms', 0))}</td><td>상위 10% 느린 요청 직전 지점</td></tr>
            <tr><td>p95 응답시간</td><td>{fmt_ms(summary.get('p95_ms', 0))}</td><td>대표 SLA 비교용</td></tr>
            <tr><td>p99 응답시간</td><td>{fmt_ms(summary.get('p99_ms', 0))}</td><td>극단적 지연 확인용</td></tr>
            <tr><td>최대 응답시간</td><td>{fmt_ms(summary.get('max_ms', 0))}</td><td>가장 느린 단건</td></tr>
            <tr><td>평균 Latency</td><td>{fmt_ms(summary.get('avg_latency_ms', 0))}</td><td>서버 처리 지연 중심</td></tr>
            <tr><td>평균 Connect</td><td>{fmt_ms(summary.get('avg_connect_ms', 0))}</td><td>연결 시간 평균</td></tr>
            <tr><td>처리량</td><td>{fmt_num(summary.get('throughput_rps', 0))} rps</td><td>초당 처리 요청 수</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="meta-grid">
      <div class="section-card">
        <h2 class="section-title">실행 메타데이터</h2>
        <table>
          <thead><tr><th>항목</th><th>값</th></tr></thead>
          <tbody>{metadata_rows(metadata)}</tbody>
        </table>
      </div>

      <div class="section-card">
        <h2 class="section-title">기준선 비교</h2>
        <table>
          <thead><tr><th>항목</th><th>값</th><th>참고</th></tr></thead>
          <tbody>{compare_rows(compare)}</tbody>
        </table>
      </div>
    </div>

    <div class="section-card">
      <h2 class="section-title">느린 요청 상세</h2>
      <table>
        <thead><tr><th>라벨</th><th>요청 수</th><th>평균</th><th>최대</th></tr></thead>
        <tbody>{table_rows(summary.get('slowest_labels', []))}</tbody>
      </table>
    </div>

    <div class="section-card">
      <h2 class="section-title">실패 샘플</h2>
      <table>
        <thead><tr><th>라벨</th><th>응답코드</th><th>응답메시지</th><th>실패메시지</th><th>응답시간</th></tr></thead>
        <tbody>{failure_rows(summary.get('failed_samples', []))}</tbody>
      </table>
    </div>

    {f'<div class="section-card"><h2 class="section-title">요약 텍스트</h2><pre>{html.escape(summary_text)}</pre></div>' if summary_text else ''}
    {f'<div class="section-card"><h2 class="section-title">GPT-OSS 심층 분석</h2><pre>{html.escape(gpt_text)}</pre></div>' if gpt_text else ''}
    {f'<div class="section-card"><h2 class="section-title">Qwen 요약</h2><pre>{html.escape(qwen_text)}</pre></div>' if qwen_text else ''}
    {f'<div class="section-card"><h2 class="section-title">전체 Markdown 보고서</h2><pre>{html.escape(llm_report)}</pre></div>' if llm_report else ''}
  </div>
</body>
</html>
"""

    # ----------------------------------------------------------------------------------
    # 최종 보고서는 report.html 하나만 생성
    # run_pipeline.py 에서 이 파일을 최종 결과물로 사용
    # ----------------------------------------------------------------------------------
    (out_dir / "report.html").write_text(html_text, encoding="utf-8")

    print(f"[OK] HTML 보고서 생성: {out_dir / 'report.html'}")


if __name__ == "__main__":
    main()