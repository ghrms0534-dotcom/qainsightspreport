from __future__ import annotations

"""
공통 유틸 모듈 (GPT-OSS 전용)

핵심 변경점
- JTL 읽기 시 필요한 컬럼만 우선 사용해서 불필요한 파싱 부담 감소
- summary 에 상세 정보(느린 요청, 실패 샘플, duration) 추가
- summary_to_text 가 compare 까지 받을 수 있게 확장
- GPT-OSS 호출 옵션을 config 로 제어 가능하게 정리
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import requests

# ------------------------------------------------------------------------------
# 프로젝트 루트 경로
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------------
# 시간 문자열 생성 (run_dir 이름용)
# ------------------------------------------------------------------------------
def now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ------------------------------------------------------------------------------
# dict 깊은 병합 (config base + local)
# ------------------------------------------------------------------------------
def deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# ------------------------------------------------------------------------------
# config 로딩
# ------------------------------------------------------------------------------
def load_config() -> Dict[str, Any]:
    base_path = BASE_DIR / "config" / "base.json"
    local_path = BASE_DIR / "config" / "local.json"

    base = json.loads(base_path.read_text(encoding="utf-8"))

    if local_path.exists():
        local = json.loads(local_path.read_text(encoding="utf-8"))
        return deep_merge(base, local)

    return base


# ------------------------------------------------------------------------------
# 디렉토리 생성
# ------------------------------------------------------------------------------
def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ------------------------------------------------------------------------------
# 실행 결과 폴더 생성
# ------------------------------------------------------------------------------
def create_run_dir(config: Dict[str, Any], plan_name: str) -> Path:
    runs_dir = ensure_dir(BASE_DIR / config["paths"]["output_runs_dir"])
    run_dir = runs_dir / f"{now_ts()}_{plan_name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# ------------------------------------------------------------------------------
# JTL 파일 읽기
# - JMeter 결과 컬럼이 매번 조금씩 달라도 안전하게 읽도록 처리
# - 성능 때문에 기본적으로 필요한 컬럼 위주로 읽음
# ------------------------------------------------------------------------------
def safe_read_jtl(result_file: str | Path) -> pd.DataFrame:
    wanted_cols = [
        "timeStamp",
        "elapsed",
        "label",
        "responseCode",
        "responseMessage",
        "threadName",
        "success",
        "failureMessage",
        "bytes",
        "Latency",
        "Connect",
    ]

    # 엔진별/파일별 차이를 고려해서 우선 전체 헤더를 읽고,
    # 실제 존재하는 컬럼만 다시 읽는다.
    head_df = pd.read_csv(result_file, nrows=0)
    available_cols = [col for col in wanted_cols if col in head_df.columns]

    if available_cols:
        df = pd.read_csv(result_file, usecols=available_cols)
    else:
        df = pd.read_csv(result_file)

    # 기본 컬럼 보정
    for col in wanted_cols:
        if col not in df.columns:
            df[col] = None

    # 타입 변환
    df["elapsed"] = pd.to_numeric(df["elapsed"], errors="coerce")
    df["Latency"] = pd.to_numeric(df["Latency"], errors="coerce")
    df["Connect"] = pd.to_numeric(df["Connect"], errors="coerce")
    df["timeStamp"] = pd.to_numeric(df["timeStamp"], errors="coerce")

    # success 컬럼이 true/false 문자열인 경우 보정
    df["success"] = (
        df["success"]
        .astype(str)
        .str.lower()
        .map({"true": True, "false": False})
        .fillna(False)
    )

    # 문자열 컬럼 NaN 보정
    for col in ["label", "responseCode", "responseMessage", "failureMessage", "threadName"]:
        df[col] = df[col].fillna("")

    return df


# ------------------------------------------------------------------------------
# 성능 요약 생성
# - 기존 요약 + 느린 요청 상위 목록 + 실패 샘플 목록 추가
# ------------------------------------------------------------------------------
def build_summary(df: pd.DataFrame) -> Dict[str, Any]:
    total = len(df)
    success_count = int(df["success"].sum()) if total else 0
    fail_count = total - success_count
    error_rate = round((fail_count / total) * 100, 2) if total else 0.0

    elapsed = df["elapsed"].dropna()

    throughput_rps = 0.0
    duration_sec = 0.0
    ts = df["timeStamp"].dropna()
    if len(ts) >= 2:
        duration_sec = round(max((float(ts.max()) - float(ts.min())) / 1000.0, 1.0), 2)
        throughput_rps = round(total / duration_sec, 2)

    slowest_labels = []
    if total and df["label"].astype(str).str.len().gt(0).any():
        group_df = (
            df.groupby("label", dropna=False)["elapsed"]
            .agg(["count", "mean", "max"])
            .reset_index()
            .sort_values(["mean", "max"], ascending=False)
        )
        for _, row in group_df.head(5).iterrows():
            slowest_labels.append(
                {
                    "label": str(row.get("label", "") or "-"),
                    "count": int(row.get("count", 0) or 0),
                    "avg_ms": round(float(row.get("mean", 0) or 0), 2),
                    "max_ms": round(float(row.get("max", 0) or 0), 2),
                }
            )

    failed_samples = []
    fail_df = df[df["success"] == False]  # noqa: E712
    if not fail_df.empty:
        for _, row in fail_df.head(10).iterrows():
            failed_samples.append(
                {
                    "label": str(row.get("label", "") or "-"),
                    "responseCode": str(row.get("responseCode", "") or "-"),
                    "responseMessage": str(row.get("responseMessage", "") or "-"),
                    "failureMessage": str(row.get("failureMessage", "") or "-"),
                    "elapsed": round(float(row.get("elapsed", 0) or 0), 2),
                }
            )

    return {
        "total_requests": total,
        "success_count": success_count,
        "fail_count": fail_count,
        "error_rate_percent": error_rate,
        "avg_ms": round(float(elapsed.mean()), 2) if not elapsed.empty else 0.0,
        "p90_ms": round(float(elapsed.quantile(0.90)), 2) if not elapsed.empty else 0.0,
        "p95_ms": round(float(elapsed.quantile(0.95)), 2) if not elapsed.empty else 0.0,
        "p99_ms": round(float(elapsed.quantile(0.99)), 2) if not elapsed.empty else 0.0,
        "max_ms": round(float(elapsed.max()), 2) if not elapsed.empty else 0.0,
        "throughput_rps": throughput_rps,
        "duration_sec": duration_sec,
        "slowest_labels": slowest_labels,
        "failed_samples": failed_samples,
    }


# ------------------------------------------------------------------------------
# Gate 판정
# ------------------------------------------------------------------------------
def gate_result(config: Dict[str, Any], plan_name: str, summary: Dict[str, Any]) -> Dict[str, Any]:
    global_gate = config["gate"]["global"]
    plan_gate = config["gate"]["plans"].get(plan_name, {})
    merged = {**global_gate, **plan_gate}

    passed = True
    reasons = []

    if summary["error_rate_percent"] > merged["error_rate_percent_max"]:
        passed = False
        reasons.append("에러율 초과")

    if summary["p95_ms"] > merged["p95_ms_max"]:
        passed = False
        reasons.append("p95 초과")

    if summary["p99_ms"] > merged.get("p99_ms_max", 999999):
        passed = False
        reasons.append("p99 초과")

    if passed:
        reasons.append("PASS")

    return {
        "passed": passed,
        "reasons": reasons,
        "thresholds": merged,
    }


# ------------------------------------------------------------------------------
# 텍스트 리포트 생성
# - GPT 호출 없이 바로 생성되는 빠른 Markdown 본문용
# ------------------------------------------------------------------------------
def summary_to_text(
    summary: Dict[str, Any],
    gate: Optional[Dict[str, Any]] = None,
    compare: Optional[Dict[str, Any]] = None,
) -> str:
    lines = [
        "# QA Insights 성능 테스트 요약",
        "",
        "## 1) 핵심 지표",
        f"- 총 요청: {summary.get('total_requests', 0)}",
        f"- 성공: {summary.get('success_count', 0)}",
        f"- 실패: {summary.get('fail_count', 0)}",
        f"- 에러율: {summary.get('error_rate_percent', 0)}%",
        f"- 평균 응답시간: {summary.get('avg_ms', 0)} ms",
        f"- p90: {summary.get('p90_ms', 0)} ms",
        f"- p95: {summary.get('p95_ms', 0)} ms",
        f"- p99: {summary.get('p99_ms', 0)} ms",
        f"- 최대 응답시간: {summary.get('max_ms', 0)} ms",
        f"- 처리량: {summary.get('throughput_rps', 0)} rps",
        f"- 측정 구간: {summary.get('duration_sec', 0)} 초",
    ]

    if gate:
        lines.extend(
            [
                "",
                "## 2) 게이트 판정",
                f"- 결과: {'PASS' if gate.get('passed') else 'FAIL'}",
                f"- 사유: {', '.join(gate.get('reasons', [])) or '-'}",
            ]
        )

    slowest_labels = summary.get("slowest_labels") or []
    if slowest_labels:
        lines.extend(["", "## 3) 느린 요청 상위"])
        for item in slowest_labels:
            lines.append(
                f"- {item.get('label')}: avg {item.get('avg_ms')} ms / max {item.get('max_ms')} ms / count {item.get('count')}"
            )

    failed_samples = summary.get("failed_samples") or []
    if failed_samples:
        lines.extend(["", "## 4) 실패 샘플"])
        for item in failed_samples[:5]:
            lines.append(
                f"- {item.get('label')} | code={item.get('responseCode')} | msg={item.get('responseMessage')} | fail={item.get('failureMessage')} | elapsed={item.get('elapsed')} ms"
            )

    if compare:
        lines.extend(
            [
                "",
                "## 5) 기준선 비교",
                f"- baseline: {compare.get('baseline_name', '-')}",
                f"- Δ p95: {compare.get('delta_p95_ms', 0)} ms",
                f"- Δ p99: {compare.get('delta_p99_ms', 0)} ms",
                f"- Δ 에러율: {compare.get('delta_error_rate_percent', 0)}%",
                f"- Δ 처리량: {compare.get('delta_throughput_rps', 0)} rps",
            ]
        )

    return "\n".join(lines).strip() + "\n"


# ------------------------------------------------------------------------------
# GPT-OSS 호출
# - 기본적으로는 안 쓰더라도 유지
# - config 에 generation 옵션이 있으면 같이 반영
# ------------------------------------------------------------------------------
def run_gpt_oss(config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
    g = config["gpt_oss"]
    base_url = g["base_url"].rstrip("/")
    url = f"{base_url}/api/chat"

    generation = g.get("generation", {})

    # 프롬프트 너무 길면 잘라서 timeout 방지
    max_prompt_chars = g.get("max_prompt_chars", 6000)
    safe_prompt = prompt[:max_prompt_chars]

    payload = {
        "model": g["model"],
        "messages": [
            {
                "role": "system",
                "content": (
                    "너는 성능 테스트 분석 전문가다. "
                    "반드시 짧고 명확하게만 답해라. "
                    "불필요한 설명 금지. "
                    "최대 10줄 이내로 답변해라."
                ),
            },
            {"role": "user", "content": safe_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": generation.get("temperature", 0.1),
            "num_predict": generation.get("num_predict", 220),
        },
    }

    resp = requests.post(url, json=payload, timeout=g.get("timeout_sec", 900))
    resp.raise_for_status()
    data = resp.json()

    return {
        "ok": True,
        "response": data.get("message", {}).get("content", ""),
    }
