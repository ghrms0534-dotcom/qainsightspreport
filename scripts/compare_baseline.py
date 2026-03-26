from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    """
    역할:
    현재 실행 결과(summary.json)와 baseline.json 을 비교해서
    얼마나 빨라졌는지 / 느려졌는지 / 에러율이 늘었는지를 계산한다.

    출력:
    - baseline_compare.json

    주로 run_pipeline.py 에서 baseline 파일이 있을 때 호출된다.
    """
    parser = argparse.ArgumentParser(
        description="현재 summary 와 baseline 을 비교해서 차이(delta) 계산"
    )
    parser.add_argument("--summary", required=True, help="현재 실행 결과 summary.json 경로")
    parser.add_argument("--baseline", required=True, help="비교할 baseline json 경로")
    parser.add_argument("--out", required=True, help="비교 결과 저장 파일 경로")
    args = parser.parse_args()

    # --------------------------------------------------------------------------
    # 1) 파일 읽기
    # --------------------------------------------------------------------------
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))

    # baseline 파일 형식이 2가지일 수 있음
    # 1) 그냥 summary 형태 그대로
    # 2) {"baseline_name": "...", "baseline_summary": {...}} 형태
    current = summary
    base = baseline.get("baseline_summary", baseline)

    # --------------------------------------------------------------------------
    # 2) 차이 계산
    # delta 값 의미:
    # - delta_p95_ms > 0 이면 현재가 baseline보다 느려진 것
    # - delta_p95_ms < 0 이면 현재가 baseline보다 빨라진 것
    #
    # - delta_error_rate_percent > 0 이면 에러율 나빠짐
    # - delta_throughput_rps > 0 이면 처리량 좋아짐
    # --------------------------------------------------------------------------
    compare = {
        "baseline_name": baseline.get("baseline_name", Path(args.baseline).stem),

        # 응답시간 차이
        "delta_p95_ms": round(current.get("p95_ms", 0) - base.get("p95_ms", 0), 2),
        "delta_p99_ms": round(current.get("p99_ms", 0) - base.get("p99_ms", 0), 2),

        # 에러율 차이
        "delta_error_rate_percent": round(
            current.get("error_rate_percent", 0) - base.get("error_rate_percent", 0),
            2,
        ),

        # 처리량 차이
        "delta_throughput_rps": round(
            current.get("throughput_rps", 0) - base.get("throughput_rps", 0),
            2,
        ),

        # 참고용 원본 값도 같이 넣어두면 나중에 보고서 만들 때 편함
        "current_p95_ms": current.get("p95_ms", 0),
        "baseline_p95_ms": base.get("p95_ms", 0),

        "current_p99_ms": current.get("p99_ms", 0),
        "baseline_p99_ms": base.get("p99_ms", 0),

        "current_error_rate_percent": current.get("error_rate_percent", 0),
        "baseline_error_rate_percent": base.get("error_rate_percent", 0),

        "current_throughput_rps": current.get("throughput_rps", 0),
        "baseline_throughput_rps": base.get("throughput_rps", 0),
    }

    # --------------------------------------------------------------------------
    # 3) 결과 저장
    # --------------------------------------------------------------------------
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(compare, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[OK] baseline 비교 결과 생성: {out_path}")


if __name__ == "__main__":
    main()