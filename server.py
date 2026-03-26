from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# scripts/common.py import 가능하게 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from common import (  # noqa: E402
    BASE_DIR,
    build_summary,
    create_run_dir,
    gate_result,
    load_config,
    run_gpt_oss,
    safe_read_jtl,
    summary_to_text,
)

# ------------------------------------------------------------------------------
# MCP 서버 초기화
# ------------------------------------------------------------------------------
mcp = FastMCP("qa-insights-jmeter-gptoss")
CONFIG = load_config()

# ------------------------------------------------------------------------------
# 실행 상태 저장용 메모리
# - RUNS: 현재 세션에서 시작한 실행 상태 저장
# - RECENT_RESULTS: 같은 조건 재호출 시 최근 결과 재사용해서 체감 속도 개선
# ------------------------------------------------------------------------------
RUNS: dict[str, dict] = {}
RECENT_RESULTS: dict[str, dict] = {}
RECENT_RESULT_TTL_SEC = 900  # 15분

# ------------------------------------------------------------------------------
# 플랜 별칭
# - 사용자가 한국어/영어/붙여쓰기/띄어쓰기로 입력해도 최대한 자동 매핑
# ------------------------------------------------------------------------------
PLAN_ALIASES = {
    "projecteyes": "projecteyes",
    "project eyes": "projecteyes",
    "프로젝트아이즈": "projecteyes",
    "프로젝트 아이즈": "projecteyes",
    "프로젝트아이즈50명": "projecteyes",
    "프로젝트아이즈 50명": "projecteyes",
    "projecteyes50": "projecteyes",
    "projecteyes 50명": "projecteyes",
    "project eyes 50명": "projecteyes",
    "헬스체크": "smoke_health",
    "스모크": "smoke_health",
    "health": "smoke_health",
    "smoke": "smoke_health",
    "로그인": "auth_login",
    "로그인성능": "auth_login",
    "login": "auth_login",
    "auth": "auth_login",
    "질의응답": "rag_query",
    "질의응답성능": "rag_query",
    "채팅": "rag_query",
    "채팅성능": "rag_query",
    "rag": "rag_query",
    "query": "rag_query",
    "chat": "rag_query",
    "종합흐름": "e2e_user_journey",
    "사용자흐름": "e2e_user_journey",
    "journey": "e2e_user_journey",
    "e2e": "e2e_user_journey",
    "과부하": "concurrent_overload",
    "과부하테스트": "concurrent_overload",
    "동시접속": "concurrent_overload",
    "동시접속자테스트": "concurrent_overload",
    "overload": "concurrent_overload",
    "concurrent": "concurrent_overload",
}


# ------------------------------------------------------------------------------
# 문자열 정규화 유틸
# ------------------------------------------------------------------------------
def normalize_text(value: str) -> str:
    if not value:
        return ""
    return str(value).strip().lower().replace(" ", "")


# ------------------------------------------------------------------------------
# JMX 테스트 플랜 폴더 경로
# ------------------------------------------------------------------------------
def get_jmeter_plan_dir() -> Path:
    return (BASE_DIR / CONFIG["jmeter"]["testplan_dir"]).resolve()


# ------------------------------------------------------------------------------
# 사용 가능한 JMX 목록 조회
# ------------------------------------------------------------------------------
def list_available_jmx_plans() -> list[str]:
    plan_dir = get_jmeter_plan_dir()
    if not plan_dir.exists():
        return []
    return sorted([p.stem for p in plan_dir.glob("*.jmx")])


# ------------------------------------------------------------------------------
# 파일명 기반 자동 키워드 맵 생성
# ------------------------------------------------------------------------------
def build_auto_keyword_map() -> dict[str, list[str]]:
    auto_map: dict[str, list[str]] = {}
    for plan_name in list_available_jmx_plans():
        keywords = set()
        lower_name = plan_name.lower()
        keywords.add(lower_name)
        keywords.add(lower_name.replace("_", "").replace("-", "").replace(" ", ""))
        for token in lower_name.replace("-", "_").replace(" ", "_").split("_"):
            token = token.strip()
            if token:
                keywords.add(token)
        auto_map[plan_name] = sorted(keywords)
    return auto_map


# ------------------------------------------------------------------------------
# 사용자 입력 plan 을 실제 JMX 파일명으로 보정
# ------------------------------------------------------------------------------
def resolve_plan(plan: str) -> str:
    if not plan:
        return "smoke_health"

    raw = str(plan).strip()
    normalized = normalize_text(raw)

    for alias, resolved in PLAN_ALIASES.items():
        if normalize_text(alias) == normalized:
            return resolved

    for alias, resolved in PLAN_ALIASES.items():
        n_alias = normalize_text(alias)
        if n_alias and n_alias in normalized:
            return resolved

    auto_map = build_auto_keyword_map()
    for plan_name, keywords in auto_map.items():
        for keyword in keywords:
            if keyword and keyword in normalized:
                return plan_name

    for name in list_available_jmx_plans():
        if normalize_text(name) == normalized:
            return name

    return raw.lower().strip()


# ------------------------------------------------------------------------------
# 사용 가능한 플랜 요약
# ------------------------------------------------------------------------------
def get_available_plan_summary() -> dict:
    return {
        "plan_dir": str(get_jmeter_plan_dir()),
        "available_jmx_plans": list_available_jmx_plans(),
        "auto_keyword_map": build_auto_keyword_map(),
        "alias_map": PLAN_ALIASES,
    }


# ------------------------------------------------------------------------------
# 최근 실행 결과 재사용용 키
# ------------------------------------------------------------------------------
def build_run_key(plan: str, users: int, ramp_up: int, loops: int, duration_sec: int, pipeline_mode: str) -> str:
    return f"{plan}|u={users}|r={ramp_up}|l={loops}|d={duration_sec}|mode={pipeline_mode}"


# ------------------------------------------------------------------------------
# 최근 결과 TTL 지난 항목 정리
# ------------------------------------------------------------------------------
def cleanup_recent_results():
    now = time.time()
    expired_keys = []
    for key, value in RECENT_RESULTS.items():
        if now - value.get("ts", 0) > RECENT_RESULT_TTL_SEC:
            expired_keys.append(key)
    for key in expired_keys:
        RECENT_RESULTS.pop(key, None)


# ------------------------------------------------------------------------------
# 로그 파일 tail 조회
# ------------------------------------------------------------------------------
def tail_text_file(path: Optional[str], limit: int = 4000) -> str:
    if not path:
        return ""
    file_path = Path(path)
    if not file_path.exists():
        return ""
    try:
        return file_path.read_text(encoding="utf-8", errors="ignore")[-limit:]
    except Exception:
        return ""


# ------------------------------------------------------------------------------
# stdout/stderr 에서 run_dir 추출
# ------------------------------------------------------------------------------
def extract_run_dir_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("[RUN_DIR]"):
            return line.replace("[RUN_DIR]", "", 1).strip()
        if line.startswith("[SUCCESS] 완료:"):
            return line.replace("[SUCCESS] 완료:", "", 1).strip()
        if line.startswith("결과 폴더:"):
            return line.replace("결과 폴더:", "", 1).strip()
        if line.startswith("✅ 완료:"):
            return line.replace("✅ 완료:", "", 1).strip()
    return None


# ------------------------------------------------------------------------------
# 결과 폴더 내부 생성 파일 탐지
# ------------------------------------------------------------------------------
def try_find_output_files(run_dir: Optional[str]) -> dict:
    result = {
        "run_dir": run_dir,
        "raw_jtl_path": None,
        "summary_json_path": None,
        "gate_json_path": None,
        "report_md_path": None,
        "report_html_path": None,
        "llm_report_md_path": None,
        "baseline_compare_path": None,
        "metadata_path": None,
        "html_dir": None,
        "stdout_log_path": None,
        "stderr_log_path": None,
    }
    if not run_dir:
        return result

    base = Path(run_dir)
    if not base.exists():
        return result

    candidates = {
        "raw_jtl_path": ["raw.jtl", "results.jtl"],
        "summary_json_path": ["summary.json"],
        "gate_json_path": ["gate.json"],
        "report_md_path": ["report.md", "report_ko.md", "korean_report.md", "summary.txt"],
        "report_html_path": ["report.html"],
        "llm_report_md_path": ["llm_report.md"],
        "baseline_compare_path": ["baseline_compare.json"],
        "metadata_path": ["run_metadata.json"],
        "stdout_log_path": ["pipeline_stdout.log", "jmeter_stdout.log"],
        "stderr_log_path": ["pipeline_stderr.log", "jmeter_stderr.log"],
    }

    for key, names in candidates.items():
        for name in names:
            p = base / name
            if p.exists():
                result[key] = str(p)
                break

    html_dir = base / "html"
    if html_dir.exists():
        result["html_dir"] = str(html_dir)

    return result


# ------------------------------------------------------------------------------
# 오래 걸리는 테스트는 강제로 비동기 전환
# 이유:
# - CLI 에서 100명/300초/full/wait=true 같이 호출되면 체감이 너무 느림
# - Playwright 느낌처럼 "일단 실행 → 나중에 상태 확인" 흐름으로 바꾸기 위함
# ------------------------------------------------------------------------------
def should_force_async(users: int, duration_sec: int, pipeline_mode: str) -> bool:
    mode = (pipeline_mode or "quick").strip().lower()
    if mode == "full" and duration_sec >= 60:
        return True
    if users >= 100:
        return True
    if duration_sec >= 180:
        return True
    return False


# ------------------------------------------------------------------------------
# 대기 타임아웃 자동 계산
# - quick 는 비교적 짧게
# - full 은 후처리 시간 버퍼를 더 줌
# ------------------------------------------------------------------------------
def build_wait_timeout(duration_sec: int, pipeline_mode: str) -> int:
    mode = (pipeline_mode or "quick").strip().lower()
    if mode == "full":
        return max(duration_sec + 120, 180)
    return max(duration_sec + 45, 90)


# ------------------------------------------------------------------------------
# 실행 완료 대기
# ------------------------------------------------------------------------------
def wait_for_run_completion(run_id: str, poll_interval_sec: float = 0.5, timeout_sec: int = 180) -> dict:
    started = time.time()
    while True:
        status = get_test_status(run_id)
        if not status.get("ok"):
            return status
        if status.get("status") == "finished":
            return status
        if time.time() - started > timeout_sec:
            return {
                "ok": False,
                "status": "timeout",
                "run_id": run_id,
                "message": f"{timeout_sec}초 내에 테스트가 끝나지 않았습니다.",
            }
        time.sleep(poll_interval_sec)


# ------------------------------------------------------------------------------
# GPT-OSS 분석용 짧은 프롬프트
# ------------------------------------------------------------------------------
def build_korean_analysis_prompt(result: dict, analysis_basis: Optional[dict] = None) -> str:
    summary = (analysis_basis or {}).get("summary", {}) or {}
    gate = (analysis_basis or {}).get("gate", {}) or {}

    lines = [
        "다음 성능 테스트 결과를 한국어로 짧고 명확하게 분석해줘.",
        "반드시 아래 4개 항목만 답해.",
        "각 항목은 1~2문장만 써.",
        "",
        "[실행 정보]",
        f"- plan: {result.get('plan')}",
        f"- users: {result.get('users')}",
        f"- ramp_up: {result.get('ramp_up')}",
        f"- loops: {result.get('loops')}",
        f"- duration_sec: {result.get('duration_sec')}",
        "",
        "[핵심 지표]",
        f"- total_requests: {summary.get('total_requests')}",
        f"- error_rate_percent: {summary.get('error_rate_percent')}",
        f"- avg_ms: {summary.get('avg_ms')}",
        f"- p95_ms: {summary.get('p95_ms')}",
        f"- p99_ms: {summary.get('p99_ms')}",
        f"- max_ms: {summary.get('max_ms')}",
        f"- throughput_rps: {summary.get('throughput_rps')}",
        "",
        "[게이트]",
        f"- passed: {gate.get('passed')}",
        f"- reasons: {', '.join(gate.get('reasons', [])) if gate.get('reasons') else '-'}",
        "",
        "형식:",
        "1. 전체 상태 요약",
        "2. 병목 3개",
        "3. 개선 3개",
        "4. 최종 결론",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------------------
# 빠른 결과 요약 묶음
# ------------------------------------------------------------------------------
def build_fast_result(result: dict, analysis_basis: Optional[dict]) -> dict:
    return {
        "ok": result.get("ok", False),
        "status": "finished",
        "requested_plan": result.get("requested_plan"),
        "plan": result.get("plan"),
        "pipeline_mode": result.get("pipeline_mode"),
        "users": result.get("users"),
        "ramp_up": result.get("ramp_up"),
        "loops": result.get("loops"),
        "duration_sec": result.get("duration_sec"),
        "run_dir": result.get("run_dir"),
        "returncode": result.get("returncode"),
        "summary": (analysis_basis or {}).get("summary"),
        "gate": (analysis_basis or {}).get("gate"),
        "summary_text": (analysis_basis or {}).get("summary_text"),
    }


# ------------------------------------------------------------------------------
# raw.jtl 이 있으면 즉시 분석 가능
# ------------------------------------------------------------------------------
def _analyze_output_files(result: dict, plan: str) -> dict:
    output_files = result.get("output_files") or try_find_output_files(result.get("run_dir"))
    raw_jtl_path = output_files.get("raw_jtl_path") if output_files else None
    if not raw_jtl_path:
        return {"ok": False, "message": "raw.jtl 파일을 찾지 못해 JTL 분석을 생략했습니다."}
    return analyze_jtl(raw_jtl_path, plan=plan)


@mcp.tool(description="사용 가능한 JMeter 테스트 플랜 목록 조회")
def get_available_plans() -> dict:
    return {"ok": True, **get_available_plan_summary()}


@mcp.tool(description="JMeter 기반 성능 테스트를 비동기로 시작")
def start_performance_test(
    plan: str = "smoke_health",
    users: int = 20,
    ramp_up: int = 10,
    loops: int = 1,
    duration_sec: int = 30,
    pipeline_mode: str = "quick",
) -> dict:
    resolved_plan = resolve_plan(plan)
    mode = (pipeline_mode or "quick").strip().lower()
    if mode not in {"quick", "full"}:
        mode = "quick"

    cleanup_recent_results()
    run_key = build_run_key(resolved_plan, users, ramp_up, loops, duration_sec, mode)

    # 같은 조건의 실행이 이미 돌고 있으면 새로 안 띄우고 기존 run_id 반환
    for existing_run_id, info in RUNS.items():
        if info.get("run_key") == run_key and info.get("status") == "running":
            return {
                "ok": True,
                "reused": True,
                "status": "running",
                "run_id": existing_run_id,
                "requested_plan": plan,
                "plan": resolved_plan,
                "pipeline_mode": mode,
                "message": "같은 조건의 테스트가 이미 실행 중입니다.",
            }

    # 최근 15분 이내 동일 조건 결과가 있으면 재사용
    if run_key in RECENT_RESULTS:
        return {
            "ok": True,
            "reused": True,
            "status": "finished",
            "requested_plan": plan,
            "plan": resolved_plan,
            "pipeline_mode": mode,
            "message": "같은 조건의 최근 실행 결과를 재사용했습니다.",
            "recent_result": RECENT_RESULTS[run_key]["result"],
        }

    run_dir = create_run_dir(CONFIG, resolved_plan)
    stdout_log_path = run_dir / "pipeline_stdout.log"
    stderr_log_path = run_dir / "pipeline_stderr.log"

    cmd = [
        sys.executable,
        str(BASE_DIR / "scripts" / "run_pipeline.py"),
        "--plan", resolved_plan,
        "--users", str(users),
        "--ramp-up", str(ramp_up),
        "--loops", str(loops),
        "--duration-sec", str(duration_sec),
        "--pipeline-mode", mode,
        "--run-dir", str(run_dir),
    ]

    stdout_fp = open(stdout_log_path, "w", encoding="utf-8")
    stderr_fp = open(stderr_log_path, "w", encoding="utf-8")

    proc = subprocess.Popen(cmd, stdout=stdout_fp, stderr=stderr_fp, text=True, shell=False)
    run_id = str(uuid.uuid4())[:8]

    RUNS[run_id] = {
        "run_id": run_id,
        "run_key": run_key,
        "requested_plan": plan,
        "plan": resolved_plan,
        "pipeline_mode": mode,
        "users": users,
        "ramp_up": ramp_up,
        "loops": loops,
        "duration_sec": duration_sec,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "started_ts": time.time(),
        "command": cmd,
        "proc": proc,
        "stdout_fp": stdout_fp,
        "stderr_fp": stderr_fp,
        "stdout_log_path": str(stdout_log_path),
        "stderr_log_path": str(stderr_log_path),
        "status": "running",
        "stdout": "",
        "stderr": "",
        "run_dir": str(run_dir),
        "returncode": None,
    }

    return {
        "ok": True,
        "status": "started",
        "run_id": run_id,
        "requested_plan": plan,
        "plan": resolved_plan,
        "pipeline_mode": mode,
        "users": users,
        "ramp_up": ramp_up,
        "loops": loops,
        "duration_sec": duration_sec,
        "run_dir": str(run_dir),
        "message": f"테스트를 시작했습니다. run_id={run_id}",
    }


@mcp.tool(description="실행 중인 테스트 상태 조회")
def get_test_status(run_id: str) -> dict:
    run = RUNS.get(run_id)
    if not run:
        return {"ok": False, "error": "run_id not found"}

    proc = run["proc"]
    returncode = proc.poll()

    if returncode is None:
        elapsed_sec = int(time.time() - run["started_ts"])
        return {
            "ok": True,
            "status": "running",
            "run_id": run_id,
            "requested_plan": run.get("requested_plan"),
            "plan": run["plan"],
            "pipeline_mode": run.get("pipeline_mode"),
            "elapsed_sec": elapsed_sec,
            "run_dir": run.get("run_dir"),
            "stdout_log_path": run.get("stdout_log_path"),
            "stderr_log_path": run.get("stderr_log_path"),
            "message": f"테스트 실행 중입니다. {elapsed_sec}초 경과",
        }

    if run["status"] != "finished":
        try:
            if run.get("stdout_fp"):
                run["stdout_fp"].close()
            if run.get("stderr_fp"):
                run["stderr_fp"].close()
        except Exception:
            pass

        run["stdout"] = tail_text_file(run.get("stdout_log_path"), limit=8000)
        run["stderr"] = tail_text_file(run.get("stderr_log_path"), limit=8000)
        run["returncode"] = returncode
        run["status"] = "finished"

        if not run.get("run_dir"):
            run["run_dir"] = extract_run_dir_from_text(run["stdout"]) or extract_run_dir_from_text(run["stderr"])

        result = {
            "ok": returncode == 0,
            "status": "finished",
            "run_id": run_id,
            "requested_plan": run.get("requested_plan"),
            "plan": run["plan"],
            "pipeline_mode": run.get("pipeline_mode"),
            "users": run["users"],
            "ramp_up": run["ramp_up"],
            "loops": run["loops"],
            "duration_sec": run["duration_sec"],
            "returncode": returncode,
            "stdout": run["stdout"][-4000:],
            "stderr": run["stderr"][-4000:],
            "stdout_log_path": run.get("stdout_log_path"),
            "stderr_log_path": run.get("stderr_log_path"),
            "run_dir": run["run_dir"],
            "command": run["command"],
            "run_key": run["run_key"],
            "output_files": try_find_output_files(run.get("run_dir")),
        }

        RECENT_RESULTS[run["run_key"]] = {"ts": time.time(), "result": result}

    return {
        "ok": True,
        "status": "finished",
        "run_id": run_id,
        "requested_plan": run.get("requested_plan"),
        "plan": run["plan"],
        "pipeline_mode": run.get("pipeline_mode"),
        "returncode": run["returncode"],
        "run_dir": run["run_dir"],
        "stdout_log_path": run.get("stdout_log_path"),
        "stderr_log_path": run.get("stderr_log_path"),
        "message": "테스트가 완료되었습니다.",
    }


@mcp.tool(description="완료된 테스트 결과 상세 조회")
def get_test_result(run_id: str) -> dict:
    run = RUNS.get(run_id)
    if not run:
        return {"ok": False, "error": "run_id not found"}

    status = get_test_status(run_id)
    if not status.get("ok"):
        return status

    if status.get("status") != "finished":
        return {
            "ok": False,
            "status": status.get("status"),
            "run_id": run_id,
            "message": "아직 테스트가 끝나지 않았습니다.",
        }

    file_info = try_find_output_files(run.get("run_dir"))
    file_info["stdout_log_path"] = run.get("stdout_log_path")
    file_info["stderr_log_path"] = run.get("stderr_log_path")

    return {
        "ok": run["returncode"] == 0,
        "status": "finished",
        "run_id": run_id,
        "requested_plan": run.get("requested_plan"),
        "plan": run["plan"],
        "pipeline_mode": run.get("pipeline_mode"),
        "users": run["users"],
        "ramp_up": run["ramp_up"],
        "loops": run["loops"],
        "duration_sec": run["duration_sec"],
        "returncode": run["returncode"],
        "run_dir": run["run_dir"],
        "stdout": tail_text_file(run.get("stdout_log_path"), 4000),
        "stderr": tail_text_file(run.get("stderr_log_path"), 4000),
        "output_files": file_info,
        "message": "테스트 결과를 반환합니다.",
    }


@mcp.tool(description="JMeter 기반 성능 테스트를 실행하고 결과를 분석")
def run_and_analyze_performance_test(
    plan: str = "smoke_health",
    users: int = 20,
    ramp_up: int = 10,
    loops: int = 1,
    duration_sec: int = 30,
    analysis_model: str = "none",
    pipeline_mode: str = "quick",
    wait_timeout_sec: int = 0,
    async_only: bool = False,
) -> dict:
    mode = (pipeline_mode or "quick").strip().lower()

    # 긴 테스트 / 큰 부하는 강제로 비동기 전환
    # - 사용자가 wait 를 원해도 너무 긴 조건이면 바로 반환 후 상태 조회 방식 사용
    force_async = should_force_async(users=users, duration_sec=duration_sec, pipeline_mode=mode)
    actual_async = async_only or force_async

    started = start_performance_test(
        plan=plan,
        users=users,
        ramp_up=ramp_up,
        loops=loops,
        duration_sec=duration_sec,
        pipeline_mode=mode,
    )

    # 재사용 결과가 있으면 즉시 반환
    if started.get("reused") and started.get("status") == "finished":
        result = started.get("recent_result", {})
        result["output_files"] = result.get("output_files") or try_find_output_files(result.get("run_dir"))
        analysis_basis = _analyze_output_files(result, plan=result.get("plan", plan))
        response = {
            "ok": result.get("ok", False),
            "status": "finished",
            "reused": True,
            "result": result,
            "analysis_basis": analysis_basis,
            "fast_summary": build_fast_result(result, analysis_basis),
        }
        if analysis_model.lower() == "gpt-oss":
            prompt = build_korean_analysis_prompt(result, analysis_basis)
            response["ai_review"] = review_with_gpt_oss(prompt)
        return response

    if not started.get("ok"):
        return started

    # 비동기 전용이면 바로 반환
    if actual_async and started.get("status") in {"started", "running"}:
        message = "테스트를 백그라운드에서 시작했습니다. get_test_status(run_id) 또는 analyze_last_run(run_id) 로 조회하세요."
        if force_async and not async_only:
            message = (
                "긴 테스트 조건이라 자동으로 백그라운드 실행으로 전환했습니다. "
                "get_test_status(run_id) 또는 analyze_last_run(run_id) 로 조회하세요."
            )
        return {
            "ok": True,
            "status": started.get("status"),
            "run_id": started.get("run_id"),
            "requested_plan": started.get("requested_plan"),
            "plan": started.get("plan"),
            "pipeline_mode": started.get("pipeline_mode"),
            "run_dir": started.get("run_dir"),
            "forced_async": force_async,
            "message": message,
        }

    timeout_sec = wait_timeout_sec or build_wait_timeout(duration_sec, mode)
    run_id = started["run_id"]
    waited = wait_for_run_completion(run_id=run_id, poll_interval_sec=0.5, timeout_sec=timeout_sec)
    if not waited.get("ok"):
        return waited

    result = get_test_result(run_id)
    analysis_basis = _analyze_output_files(result, plan=result.get("plan", plan))
    response = {
        "ok": result.get("ok", False),
        "status": "finished",
        "run_id": run_id,
        "result": result,
        "analysis_basis": analysis_basis,
        "fast_summary": build_fast_result(result, analysis_basis),
    }
    if analysis_model.lower() == "gpt-oss":
        prompt = build_korean_analysis_prompt(result, analysis_basis)
        response["ai_review"] = review_with_gpt_oss(prompt)
    return response


@mcp.tool(description="ProjectEyes 빠른 성능 테스트 (실행/확인 위주)")
def quick_projecteyes_test(
    users: int = 10,
    ramp_up: int = 5,
    loops: int = 1,
    duration_sec: int = 15,
    analysis_model: str = "none",
) -> dict:
    return run_and_analyze_performance_test(
        plan="projecteyes",
        users=users,
        ramp_up=ramp_up,
        loops=loops,
        duration_sec=duration_sec,
        analysis_model=analysis_model,
        pipeline_mode="quick",
        wait_timeout_sec=build_wait_timeout(duration_sec, "quick"),
        async_only=False,
    )


@mcp.tool(description="ProjectEyes 전체 성능 테스트 (기본은 백그라운드 실행)")
def full_projecteyes_test(
    users: int = 50,
    ramp_up: int = 10,
    loops: int = 1,
    duration_sec: int = 30,
    analysis_model: str = "none",
    wait_for_finish: bool = False,
) -> dict:
    return run_and_analyze_performance_test(
        plan="projecteyes",
        users=users,
        ramp_up=ramp_up,
        loops=loops,
        duration_sec=duration_sec,
        analysis_model=analysis_model,
        pipeline_mode="full",
        wait_timeout_sec=build_wait_timeout(duration_sec, "full"),
        async_only=(not wait_for_finish),
    )


@mcp.tool(description="서버 상태 확인용 헬스체크 테스트")
def quick_smoke_test(analysis_model: str = "none") -> dict:
    return run_and_analyze_performance_test(
        plan="smoke_health",
        users=1,
        ramp_up=1,
        loops=1,
        duration_sec=5,
        analysis_model=analysis_model,
        pipeline_mode="quick",
        wait_timeout_sec=60,
        async_only=False,
    )


@mcp.tool(description="JTL 결과 파일을 분석하여 summary 및 gate 결과 반환")
def analyze_jtl(jtl_path: str, plan: str = "smoke_health") -> dict:
    resolved_plan = resolve_plan(plan)
    df = safe_read_jtl(jtl_path)
    summary = build_summary(df)
    gate = gate_result(CONFIG, resolved_plan, summary)
    return {
        "ok": True,
        "plan": resolved_plan,
        "summary": summary,
        "gate": gate,
        "summary_text": summary_to_text(summary, gate=gate),
    }


@mcp.tool(description="baseline과 비교하여 성능 변화 분석")
def compare_with_baseline(summary_json_path: str, baseline_json_path: str) -> dict:
    summary = json.loads(Path(summary_json_path).read_text(encoding="utf-8"))
    baseline = json.loads(Path(baseline_json_path).read_text(encoding="utf-8"))
    base = baseline.get("baseline_summary", baseline)
    return {
        "baseline_name": baseline.get("baseline_name", Path(baseline_json_path).stem),
        "delta_p95_ms": round(summary.get("p95_ms", 0) - base.get("p95_ms", 0), 2),
        "delta_p99_ms": round(summary.get("p99_ms", 0) - base.get("p99_ms", 0), 2),
        "delta_error_rate_percent": round(summary.get("error_rate_percent", 0) - base.get("error_rate_percent", 0), 2),
        "delta_throughput_rps": round(summary.get("throughput_rps", 0) - base.get("throughput_rps", 0), 2),
    }


@mcp.tool(description="마지막 실행된 테스트 결과를 분석")
def analyze_last_run(run_id: str, analysis_model: str = "none") -> dict:
    result = get_test_result(run_id)
    if not result.get("ok") and result.get("status") != "finished":
        return result

    analysis_basis = _analyze_output_files(result, plan=result.get("plan", "smoke_health"))
    response = {
        "ok": True,
        "run_id": run_id,
        "result": result,
        "analysis_basis": analysis_basis,
        "fast_summary": build_fast_result(result, analysis_basis),
    }

    if analysis_model.lower() == "gpt-oss":
        prompt = build_korean_analysis_prompt(result, analysis_basis)
        response["ai_review"] = review_with_gpt_oss(prompt)

    return response


@mcp.tool(description="GPT-OSS 모델을 사용해 성능 테스트 결과를 분석")
def review_with_gpt_oss(prompt: str) -> dict:
    return run_gpt_oss(CONFIG, prompt)


@mcp.tool(description="최근 실행된 테스트 목록 조회")
def get_recent_runs() -> dict:
    items = []
    for run_id, run in RUNS.items():
        status = get_test_status(run_id)
        items.append(
            {
                "run_id": run_id,
                "requested_plan": run.get("requested_plan"),
                "plan": run.get("plan"),
                "pipeline_mode": run.get("pipeline_mode"),
                "users": run.get("users"),
                "ramp_up": run.get("ramp_up"),
                "loops": run.get("loops"),
                "duration_sec": run.get("duration_sec"),
                "status": status.get("status"),
                "started_at": run.get("started_at"),
                "run_dir": run.get("run_dir"),
            }
        )
    items.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return {"ok": True, "runs": items}


if __name__ == "__main__":
    mcp.run()
