# QA Insights 성능검증 자동화 플랫폼

AI 기반 QA 서비스의 안정성과 성능을 검증하기 위해 구축한 **통합 성능 테스트 자동화 플랫폼**입니다.

기존 단순 부하 테스트(JMeter 실행 후 결과 확인) 방식에서 벗어나, **성능 테스트 실행 → 결과 수집 → 기준선 비교 → AI 기반 성능 분석 → 최종 리포트 자동 생성**까지 전체 파이프라인을 자동화하는 것을 목표로 개발하였습니다.

---

## 프로젝트 목표

기존 성능 테스트 과정에는 아래와 같은 문제가 존재했습니다.

* 단순 JMeter 부하 테스트 결과만 확인 가능
* 테스트 결과 분석 과정이 수동으로 진행됨
* 병목 원인 분석에 많은 시간이 소요됨
* 배포 이후 성능 저하 여부를 즉시 판단하기 어려움

위 문제를 해결하기 위해 AI 기반 자동 분석 기능을 포함한 성능검증 자동화 플랫폼을 설계하였습니다.

---

## 핵심 기능

### 1. 자동 부하 테스트 실행

* Apache JMeter 기반 API 부하 테스트 자동 실행
* Smoke Test, Login API, RAG Query, E2E 시나리오 지원
* 동시 접속자 기반 과부하 테스트 지원

---

### 2. 성능 데이터 자동 분석

* JMeter 결과(raw.jtl) 자동 수집
* summary.json 생성
* gate.json 기반 SLA 통과 여부 자동 판정
* baseline 비교를 통한 성능 저하 자동 탐지

---

### 3. AI 기반 성능 분석 파이프라인

* Qwen CLI 기반 1차 성능 요약 생성
* GPT-OSS 120B 기반 병목 원인 심층 분석
* 성능 이슈 우선순위 자동 분류
* 개선 포인트 자동 도출

---

### 4. 자동 리포트 생성

* Markdown 보고서 자동 생성
* HTML 기반 성능 리포트 자동 생성
* 배포 후 성능 회귀(Regression) 자동 검증

---

### 5. MCP 기반 AI Tool Integration

* MCP Server 구축
* Agent가 직접 성능 테스트 실행 가능
* Tool Calling 기반 자동 테스트 파이프라인 제공

지원 Tool

* run_jmeter_test
* analyze_jtl
* compare_with_baseline
* run_full_qa_pipeline

---

## 시스템 아키텍처

```text
JMeter Load Test
      ↓
raw.jtl 생성
      ↓
summary.json / gate.json 생성
      ↓
baseline compare 수행
      ↓
Qwen CLI 1차 분석
      ↓
GPT-OSS 심층 분석
      ↓
Markdown / HTML Report 자동 생성
```

---

## 기술 스택

* Python
* Apache JMeter
* Qwen CLI
* GPT-OSS 120B
* MCP Architecture
* JSON Report Pipeline
* HTML Report Generation
* Performance Regression Detection

---

## 개발하면서 집중한 부분

* 테스트부터 분석까지 완전 자동화된 Pipeline 구조 설계
* AI 기반 성능 분석 자동화 구조 설계
* Baseline 비교 기반 Regression Detection 구현
* MCP Tool Calling 기반 Agent 연동 구조 설계
* 운영 환경에서 반복 가능한 QA 자동화 구조 구현

---

## 기대 효과

* 성능 테스트 반복 작업 자동화
* 테스트 결과 분석 시간 단축
* 배포 후 성능 저하 자동 탐지
* QA 엔지니어 개입 최소화
* AI 기반 운영 자동화 구조 검증
