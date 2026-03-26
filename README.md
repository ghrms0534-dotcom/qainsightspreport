# QA Insights 성능검증 스택

QA Insights 서비스에 맞춰 만든 **JMeter + Qwen CLI + GPT-OSS:120B + MCP** 기반 성능 테스트 자동화 프로젝트입니다.

이 프로젝트의 목적은 단순한 부하 테스트 1회 실행이 아니라, 아래 흐름을 한 번에 만드는 것입니다.

1. JMeter로 API 시나리오 실행
2. `raw.jtl` 저장
3. `summary.json` / `gate.json` 생성
4. 기준선(baseline) 비교
5. Qwen CLI 1차 요약
6. GPT-OSS:120B 심층 분석
7. `llm_report.md`와 `report.html` 생성

---

## 1. 포함된 테스트 시나리오

### 1) `smoke_health`
- 목적: 서버 생존 확인
- 대상: `/health`
- 권장 시점: 서버 띄운 직후, 배포 직후

### 2) `auth_login`
- 목적: 로그인 응답속도와 인증 성공률 확인
- 대상: `/api/auth/login`
- 권장 시점: 인증 변경 후, 세션 이슈 점검 시

### 3) `rag_query`
- 목적: QA Insights 질의응답 API 성능 측정
- 대상: `/api/chat/query`
- 권장 시점: 모델/프롬프트/검색 로직 변경 후

### 4) `e2e_user_journey`
- 목적: 로그인 후 질의까지 이어지는 사용자 흐름 검증
- 대상: 로그인 + 질의응답 연계
- 권장 시점: 릴리즈 전 종합 점검

### 5) `concurrent_overload`
- 목적: 과부하 테스트 및 동시 접속자 대응력 확인
- 대상: 로그인 + 질의응답 동시 부하
- 권장 시점: 대량 접속 예상 전, 용량 산정 전, 병목 지점 확인 시

---

## 2. 권장 실행 순서

### 1단계. 최소 생존 확인
```bash
python run_performance_test.py --plan smoke_health --users 1 --ramp-up 1 --loops 1
```

### 2단계. 로그인 확인
```bash
python run_performance_test.py --plan auth_login --users 5 --ramp-up 5 --loops 1
```

### 3단계. 질의응답 확인
```bash
python run_performance_test.py --plan rag_query --users 5 --ramp-up 5 --loops 1
```

### 4단계. 사용자 흐름 확인
```bash
python run_performance_test.py --plan e2e_user_journey --users 5 --ramp-up 5 --loops 1
```

### 5단계. 과부하/동시 접속자 테스트
```bash
python run_performance_test.py --plan concurrent_overload --users 50 --ramp-up 10 --loops 3
```

### 6단계. 단계적 과부하 테스트 세트
```bash
python run_performance_test.py --plan concurrent_overload --users 20 --ramp-up 10 --loops 2
python run_performance_test.py --plan concurrent_overload --users 50 --ramp-up 10 --loops 3
python run_performance_test.py --plan concurrent_overload --users 100 --ramp-up 20 --loops 3
```

---

## 3. 결과물 위치

실행 결과는 아래 폴더에 생성됩니다.

```text
output/runs/<실행시각>_<플랜명>/
```

주요 파일:
- `raw.jtl` : JMeter 원본 결과
- `html/index.html` : JMeter 시각화 리포트
- `summary.json` : 성능 수치 요약
- `gate.json` : 기준 통과/실패 판정
- `baseline_compare.json` : 기준선 대비 변화량
- `qwen_summary.txt` : Qwen CLI 요약
- `gptoss_analysis.txt` : GPT-OSS 120B 분석
- `llm_report.md` : Markdown 보고서
- `report.html` : 한글 HTML 보고서

---

## 4. 꼭 먼저 수정할 파일

### `config/local.json`
실제 서비스에 맞는 주소와 도구 경로를 여기서 맞춥니다.

예시:
```json
{
  "service": {
    "base_url": "http://127.0.0.1:8000",
    "health_path": "/health",
    "login_path": "/api/auth/login",
    "chat_path": "/api/chat/query"
  },
  "jmeter": {
    "bin": "C:\apache-jmeter-5.6.3\bin\jmeter.bat"
  },
  "qwen": {
    "enabled": true,
    "command": "C:\Users\admin\AppData\Roaming\npm\qwen.cmd"
  },
  "gpt_oss": {
    "enabled": true,
    "base_url": "http://localhost:11434",
    "model": "gpt-oss:120b"
  }
}
```

---

## 5. Qwen CLI 중심 분석 포인트

Qwen CLI는 아래 역할로 쓰는 것을 권장합니다.
- 테스트 결과 핵심 이슈 5개 요약
- 병목 후보 우선순위 정리
- 실패 응답 패턴 분류
- 바로 공유 가능한 한 줄 결론 작성

GPT-OSS:120B는 아래 역할로 쓰는 것을 권장합니다.
- 심층 원인 분석
- 다음 실험 설계
- 병목 원인 가설 정리
- 개발/운영 액션아이템 분리

---

## 6. 추천 테스트 세트

### A. 기본 확인
- `smoke_health`
- `auth_login`
- `rag_query`

### B. 릴리즈 전 점검
- `smoke_health`
- `auth_login`
- `rag_query`
- `e2e_user_journey`
- 기준선 비교 포함

### C. 과부하 점검
```bash
python run_performance_test.py --plan concurrent_overload --users 20 --ramp-up 10 --loops 2
python run_performance_test.py --plan concurrent_overload --users 50 --ramp-up 10 --loops 3
python run_performance_test.py --plan concurrent_overload --users 100 --ramp-up 20 --loops 3
```

해석 기준 예시:
- 20명: 정상 동작 구간 확인
- 50명: 병목 시작 지점 확인
- 100명: 에러율 상승과 p95/p99 악화 여부 확인

---

## 7. MCP 서버

MCP 서버 실행:
```bash
python server.py
```

제공 툴:
- `run_jmeter_test`
- `analyze_jtl`
- `compare_with_baseline`
- `review_with_qwen`
- `review_with_gpt_oss`
- `run_full_qa_pipeline`

한국어 별칭:
- `헬스체크` → `smoke_health`
- `로그인성능` → `auth_login`
- `질의응답성능` → `rag_query`
- `종합흐름` → `e2e_user_journey`
- `과부하테스트` / `동시접속자테스트` → `concurrent_overload`

---

## 8. 빠른 시작

```bash
python run_performance_test.py --plan smoke_health --users 1 --ramp-up 1 --loops 1
```

성공하면 그다음:
```bash
python run_performance_test.py --plan auth_login --users 5 --ramp-up 5 --loops 1
python run_performance_test.py --plan rag_query --users 5 --ramp-up 5 --loops 1
python run_performance_test.py --plan e2e_user_journey --users 5 --ramp-up 5 --loops 1
python run_performance_test.py --plan concurrent_overload --users 20 --ramp-up 10 --loops 2
```

## 한글 보고서
테스트가 끝나면 각 실행 폴더에 `report.html`이 자동 생성됩니다.
이 파일은 한글 요약 화면이며, `html/index.html`은 JMeter 원본 영어 리포트입니다.
