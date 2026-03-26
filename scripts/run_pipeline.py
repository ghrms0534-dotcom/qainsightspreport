from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from common import BASE_DIR, create_run_dir, load_config, summary_to_text


def resolve_service_connection(service: dict) -> tuple[str, str, int]:
    """
    base_url 에서 protocol / domain / port 를 분리한다.
    JMeter 에 -J 변수로 넘길 때 사용한다.
    """
    parsed = urlparse(service["base_url"])
    protocol = parsed.scheme or "http"
    domain = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if protocol == "https" else 80)
    return protocol, domain, port



def build_jmeter_command(
    config: dict,
    plan_file: Path,
    result_file: Path,
    html_dir: Path,
    users: int,
    ramp_up: int,
    loops: int,
    duration_sec: int,
    generate_html_dashboard: bool,
) -> list[str]:
    """
    JMeter 실행 명령 조립

    속도 관련 핵심
    - HTML dashboard(-e -o)는 꽤 느릴 수 있어서 선택형으로 둔다.
    - quick 모드에서는 기본 OFF.
    """
    service = config["service"]
    protocol, domain, port = resolve_service_connection(service)

    cmd = [
        config["jmeter"]["bin"],
        "-n",
        "-t", str(plan_file),
        "-l", str(result_file),
        f"-Jprotocol={protocol}",
        f"-Jdomain={domain}",
        f"-Jport={port}",
        f"-Jbase_url={service['base_url']}",
        f"-Jhealth_path={service['health_path']}",
        f"-Jlogin_path={service['login_path']}",
        f"-Jchat_path={service['chat_path']}",
        f"-Jusername_field={service.get('username_field', 'username')}",
        f"-Jpassword_field={service.get('password_field', 'password')}",
        f"-Jchat_question_field={service.get('chat_question_field', 'question')}",
        f"-Jauth_token_json_path={service.get('auth_token_json_path', '$.auth_token')}",
        f"-Jchat_answer_json_path={service.get('chat_answer_json_path', '$.answer')}",
        f"-Jusers={users}",
        f"-Jramp_up={ramp_up}",
        f"-Jloops={loops}",
        f"-Jduration_sec={duration_sec}",
        f"-Jdata_dir={str((BASE_DIR / config['jmeter']['data_dir']).resolve())}",
    ]

    if generate_html_dashboard:
        cmd.extend(["-e", "-o", str(html_dir)])

    return cmd



def write_text(path: Path, text: str) -> None:
    path.write_text(text or "", encoding="utf-8")



def run_subprocess_checked(
    cmd: list[str],
    stdout_path: Path,
    stderr_path: Path,
    step_name: str,
) -> tuple[float, str, str]:
    """
    서브프로세스 공통 실행기
    - stdout/stderr 를 파일로 저장
    - returncode != 0 이면 즉시 종료
    """
    started = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    elapsed = round(time.perf_counter() - started, 2)

    write_text(stdout_path, proc.stdout or "")
    write_text(stderr_path, proc.stderr or "")

    print(f"[STEP] {step_name} 완료 ({elapsed}초)")

    if proc.returncode != 0:
        print(f"[ERROR] {step_name} 실패")
        print((proc.stderr or "")[-2000:])
        sys.exit(proc.returncode)

    return elapsed, proc.stdout or "", proc.stderr or ""



def build_generated_files(
    run_dir: Path,
    result_file: Path,
    html_dir: Path,
    llm_report_md: Path,
    compare_file: Path,
) -> dict:
    """
    실제 생성된 파일만 metadata 에 반영
    """
    return {
        "raw_jtl": str(result_file) if result_file.exists() else None,
        "summary_json": str(run_dir / "summary.json") if (run_dir / "summary.json").exists() else None,
        "gate_json": str(run_dir / "gate.json") if (run_dir / "gate.json").exists() else None,
        "llm_report_md": str(llm_report_md) if llm_report_md.exists() else None,
        "baseline_compare_json": str(compare_file) if compare_file.exists() else None,
        "report_html": str(run_dir / "report.html") if (run_dir / "report.html").exists() else None,
        "html_dashboard_dir": str(html_dir) if html_dir.exists() else None,
    }



def write_run_metadata(
    run_dir: Path,
    plan_name: str,
    pipeline_mode: str,
    result_file: Path,
    html_dir: Path,
    users: int,
    ramp_up: int,
    loops: int,
    duration_sec: int,
    generated_files: dict,
    elapsed_info: dict | None = None,
) -> Path:
    metadata = {
        "플랜명": plan_name,
        "파이프라인모드": pipeline_mode,
        "결과폴더": str(run_dir),
        "원본결과파일": str(result_file),
        "HTML리포트폴더": str(html_dir) if html_dir.exists() else None,
        "사용자수": users,
        "램프업": ramp_up,
        "반복수": loops,
        "지속시간초": duration_sec,
        "생성파일": generated_files,
        "단계별소요초": elapsed_info or {},
    }
    path = run_dir / "run_metadata.json"
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path



def main():
    parser = argparse.ArgumentParser(description="QA Insights JMeter 파이프라인")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--users", type=int)
    parser.add_argument("--ramp-up", type=int)
    parser.add_argument("--loops", type=int)
    parser.add_argument("--duration-sec", type=int)
    parser.add_argument("--pipeline-mode", default="quick", choices=["quick", "full"])
    parser.add_argument("--run-dir")

    # 개별 스킵 옵션
    parser.add_argument("--skip-html-dashboard", action="store_true")
    parser.add_argument("--skip-baseline-compare", action="store_true")
    parser.add_argument("--skip-korean-report", action="store_true")
    args = parser.parse_args()

    config = load_config()
    plan_name = args.plan.strip().lower()
    pipeline_mode = args.pipeline_mode.strip().lower()

    run_dir = Path(args.run_dir).resolve() if args.run_dir else create_run_dir(config, plan_name)
    run_dir.mkdir(parents=True, exist_ok=True)

    testplan_dir = (BASE_DIR / config["jmeter"]["testplan_dir"]).resolve()
    plan_file = testplan_dir / f"{plan_name}.jmx"

    print("=" * 80)
    print("QA Insights JMeter 성능 테스트 파이프라인")
    print("=" * 80)
    print(f"[RUN_DIR] {run_dir}")
    print("플랜:", plan_name)
    print("모드:", pipeline_mode)
    print("testplan_dir:", testplan_dir)
    print("plan_file:", plan_file)

    if not plan_file.exists():
        print(f"[ERROR] 테스트 플랜을 찾을 수 없음: {plan_file}")
        sys.exit(1)

    result_file = run_dir / "raw.jtl"
    html_dir = run_dir / "html"

    users = args.users or config["jmeter"]["default_users"]
    ramp_up = args.ramp_up or config["jmeter"]["default_ramp_up"]
    loops = args.loops or config["jmeter"]["default_loops"]
    duration_sec = args.duration_sec or config["jmeter"]["default_duration_sec"]

    # --------------------------------------------------------------------------
    # 모드별 속도 정책
    # quick:
    # - 가장 빠른 모드
    # - JMeter 결과 + summary/gate + Markdown 요약만 생성
    # - HTML dashboard / baseline / report.html 생성 안 함
    #
    # full:
    # - 한국어 report.html 까지 생성
    # - 하지만 JMeter HTML dashboard 는 기본 OFF 로 바꿔서 체감 속도 개선
    # --------------------------------------------------------------------------
    if pipeline_mode == "quick":
        generate_html_dashboard = False
        generate_baseline_compare = False
        generate_korean_report = False
    else:
        generate_html_dashboard = not args.skip_html_dashboard and bool(config.get("report", {}).get("enable_jmeter_dashboard_in_full", False))
        generate_baseline_compare = not args.skip_baseline_compare
        generate_korean_report = not args.skip_korean_report

    cmd = build_jmeter_command(
        config=config,
        plan_file=plan_file,
        result_file=result_file,
        html_dir=html_dir,
        users=users,
        ramp_up=ramp_up,
        loops=loops,
        duration_sec=duration_sec,
        generate_html_dashboard=generate_html_dashboard,
    )

    print("결과 폴더:", run_dir)
    print("사용자 수:", users)
    print("램프업:", ramp_up)
    print("반복 수:", loops)
    print("지속 시간(초):", duration_sec)
    print("HTML Dashboard 생성:", generate_html_dashboard)
    print("Baseline 비교:", generate_baseline_compare)
    print("한글 HTML 보고서 생성:", generate_korean_report)
    print("실행 명령:", " ".join(cmd))

    timings: dict[str, float] = {}

    # 1) JMeter 실행
    jmeter_stdout_log = run_dir / "jmeter_stdout.log"
    jmeter_stderr_log = run_dir / "jmeter_stderr.log"
    started = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    timings["jmeter_sec"] = round(time.perf_counter() - started, 2)

    write_text(jmeter_stdout_log, proc.stdout or "")
    write_text(jmeter_stderr_log, proc.stderr or "")

    print(f"[STEP] jmeter 완료 ({timings['jmeter_sec']}초)")

    if proc.returncode != 0:
        print("[ERROR] JMeter 실행 실패")
        print((proc.stderr or "")[-2000:])
        sys.exit(proc.returncode)

    # 2) summary/gate 생성
    timings["summarize_sec"], _, _ = run_subprocess_checked(
        [
            sys.executable,
            str(BASE_DIR / "scripts" / "summarize_jtl.py"),
            "--jtl", str(result_file),
            "--plan", plan_name,
            "--out-dir", str(run_dir),
        ],
        stdout_path=run_dir / "summarize_stdout.log",
        stderr_path=run_dir / "summarize_stderr.log",
        step_name="summarize_jtl",
    )

    # 3) baseline 비교 (선택)
    baseline_file = BASE_DIR / config["paths"]["baselines_dir"] / f"{plan_name}.json"
    compare_file = run_dir / "baseline_compare.json"

    if generate_baseline_compare and baseline_file.exists():
        timings["baseline_compare_sec"], _, _ = run_subprocess_checked(
            [
                sys.executable,
                str(BASE_DIR / "scripts" / "compare_baseline.py"),
                "--summary", str(run_dir / "summary.json"),
                "--baseline", str(baseline_file),
                "--out", str(compare_file),
            ],
            stdout_path=run_dir / "compare_stdout.log",
            stderr_path=run_dir / "compare_stderr.log",
            step_name="compare_baseline",
        )
    else:
        timings["baseline_compare_sec"] = 0.0

    # 4) Markdown 요약 생성
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    gate = json.loads((run_dir / "gate.json").read_text(encoding="utf-8"))
    compare = json.loads(compare_file.read_text(encoding="utf-8")) if compare_file.exists() else None

    llm_report_md = run_dir / "llm_report.md"
    llm_report_md.write_text(summary_to_text(summary, gate=gate, compare=compare), encoding="utf-8")
    timings["llm_report_write_sec"] = 0.01

    # 5) report.html 생성 (선택)
    if generate_korean_report:
        tmp_metadata_path = run_dir / "run_metadata.json.tmp"
        tmp_generated_files = {
            "raw_jtl": str(result_file) if result_file.exists() else None,
            "summary_json": str(run_dir / "summary.json") if (run_dir / "summary.json").exists() else None,
            "gate_json": str(run_dir / "gate.json") if (run_dir / "gate.json").exists() else None,
            "llm_report_md": str(llm_report_md) if llm_report_md.exists() else None,
            "baseline_compare_json": str(compare_file) if compare_file.exists() else None,
            "report_html": str(run_dir / "report.html"),
            "html_dashboard_dir": str(html_dir) if html_dir.exists() else None,
        }

        tmp_metadata_path.write_text(
            json.dumps(
                {
                    "플랜명": plan_name,
                    "파이프라인모드": pipeline_mode,
                    "결과폴더": str(run_dir),
                    "원본결과파일": str(result_file),
                    "HTML리포트폴더": str(html_dir) if html_dir.exists() else None,
                    "사용자수": users,
                    "램프업": ramp_up,
                    "반복수": loops,
                    "지속시간초": duration_sec,
                    "생성파일": tmp_generated_files,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        korean_cmd = [
            sys.executable,
            str(BASE_DIR / "scripts" / "generate_korean_report.py"),
            "--summary", str(run_dir / "summary.json"),
            "--gate", str(run_dir / "gate.json"),
            "--out-dir", str(run_dir),
            "--metadata", str(tmp_metadata_path),
        ]
        if compare_file.exists():
            korean_cmd.extend(["--compare", str(compare_file)])

        timings["korean_report_sec"], _, _ = run_subprocess_checked(
            korean_cmd,
            stdout_path=run_dir / "korean_report_stdout.log",
            stderr_path=run_dir / "korean_report_stderr.log",
            step_name="generate_korean_report",
        )

        try:
            tmp_metadata_path.unlink(missing_ok=True)
        except Exception:
            pass
    else:
        timings["korean_report_sec"] = 0.0

    # 6) metadata 저장
    generated_files = build_generated_files(
        run_dir=run_dir,
        result_file=result_file,
        html_dir=html_dir,
        llm_report_md=llm_report_md,
        compare_file=compare_file,
    )
    metadata_path = write_run_metadata(
        run_dir=run_dir,
        plan_name=plan_name,
        pipeline_mode=pipeline_mode,
        result_file=result_file,
        html_dir=html_dir,
        users=users,
        ramp_up=ramp_up,
        loops=loops,
        duration_sec=duration_sec,
        generated_files=generated_files,
        elapsed_info=timings,
    )

    total_elapsed_sec = round(sum(timings.values()), 2)
    print("[SUCCESS] 완료:", run_dir)
    print("[META] 메타데이터:", metadata_path)
    print("[TIME] 단계별 소요:", json.dumps(timings, ensure_ascii=False))
    print("[TIME] 총 소요(대략):", total_elapsed_sec, "초")

    if pipeline_mode == "full":
        if generate_korean_report and (run_dir / "report.html").exists():
            print("[REPORT] 보고서:", run_dir / "report.html")
        elif generate_korean_report:
            print("[REPORT] report.html 생성 시도했지만 파일이 없음")
        else:
            print("[REPORT] full 모드지만 report.html 생성은 생략됨")
    else:
        print("[REPORT] quick 모드라 report.html 생성은 생략됨")
        print("[REPORT] summary.json / gate.json / llm_report.md 생성 완료")


if __name__ == "__main__":
    main()
