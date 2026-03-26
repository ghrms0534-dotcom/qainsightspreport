from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    build_summary,    # JTL DataFrame -> 핵심 성능 요약 dict
    gate_result,      # 성능 기준 통과/실패 판정
    load_config,      # config/base.json + local.json 로드
    safe_read_jtl,    # JTL 파일 안전하게 읽기
    summary_to_text,  # summary/gate를 사람이 읽기 쉬운 텍스트로 변환
)


def main():
    """
    역할:
    raw.jtl 파일을 읽어서 아래 3개 파일을 만든다.

    1) summary.json  : 수치 요약
    2) gate.json     : 기준 통과/실패 판정
    3) summary.txt   : 사람이 읽기 쉬운 텍스트 요약

    이 파일은 보통 run_pipeline.py 에서 호출된다.
    """
    parser = argparse.ArgumentParser(
        description="JMeter JTL 파일을 요약(summary) + 게이트(gate) 결과로 변환"
    )
    parser.add_argument("--jtl", required=True, help="입력 JTL 파일 경로 (예: raw.jtl)")
    parser.add_argument("--plan", required=True, help="현재 실행한 테스트 플랜 이름")
    parser.add_argument("--out-dir", required=True, help="결과를 저장할 폴더")
    args = parser.parse_args()

    # --------------------------------------------------------------------------
    # 1) 설정 로드
    # --------------------------------------------------------------------------
    config = load_config()

    # --------------------------------------------------------------------------
    # 2) 결과 폴더 준비
    # --------------------------------------------------------------------------
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # 3) raw.jtl 읽기
    # safe_read_jtl() 안에서 컬럼 보정, 숫자형 변환, success bool 변환 등을 처리함
    # --------------------------------------------------------------------------
    df = safe_read_jtl(args.jtl)

    # --------------------------------------------------------------------------
    # 4) 핵심 요약 생성
    # 예:
    # - total_requests
    # - success_count
    # - fail_count
    # - error_rate_percent
    # - p95_ms / p99_ms
    # - throughput_rps
    # --------------------------------------------------------------------------
    summary = build_summary(df)

    # --------------------------------------------------------------------------
    # 5) 성능 기준 통과/실패 판정
    # config 안의 gate 기준과 summary 값을 비교해서
    # PASS / FAIL + 사유를 만든다.
    # --------------------------------------------------------------------------
    gate = gate_result(config, args.plan, summary)

    # --------------------------------------------------------------------------
    # 6) 파일 저장
    # summary.json : 다른 스크립트 / 서버가 기계적으로 읽기 좋은 형태
    # gate.json    : 기준 판정 결과
    # summary.txt  : 사람이 직접 보기 좋은 텍스트 형태
    # --------------------------------------------------------------------------
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (out_dir / "gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (out_dir / "summary.txt").write_text(
        summary_to_text(summary, gate=gate),
        encoding="utf-8",
    )

    print(f"[OK] summary.json 생성: {out_dir / 'summary.json'}")
    print(f"[OK] gate.json 생성: {out_dir / 'gate.json'}")
    print(f"[OK] summary.txt 생성: {out_dir / 'summary.txt'}")


if __name__ == "__main__":
    main()