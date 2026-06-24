# BenchFlow

BenchFlow는 AI 기반 서비스의 안정성과 성능을 검증하기 위해 설계한 **AI Performance Testing Automation Platform** 입니다.

기존 성능 테스트는 단순히 부하 테스트를 실행하고 결과를 확인하는 수준에 머무르는 경우가 많습니다.
BenchFlow는 이러한 방식에서 벗어나 **성능 테스트 실행 → 결과 수집 → 기준선 비교 → AI 기반 병목 분석 → 자동 리포트 생성** 까지 전체 과정을 자동화하는 것을 목표로 개발하였습니다.

---

## 프로젝트 목표

기존 성능 테스트 환경에는 다음과 같은 한계가 존재합니다.

* JMeter 실행 후 결과를 직접 분석해야 함
* 병목 원인 분석 과정이 수동으로 이루어짐
* 배포 이후 성능 저하 여부를 즉시 확인하기 어려움
* 반복적인 테스트 수행 과정이 비효율적임

BenchFlow는 이러한 문제를 해결하기 위해 **AI 기반 성능 테스트 자동화 파이프라인**을 설계하였습니다.

---

## 핵심 기능

### 1. Automated Load Testing

Apache JMeter 기반 API 부하 테스트 자동 실행

지원 시나리오

* Health Check Test
* Authentication API Test
* RAG Query Performance Test
* End-to-End User Journey Test
* Concurrent User Load Test

---

### 2. Performance Data Processing

테스트 결과 자동 수집 및 분석

지원 기능

* raw.jtl 자동 생성
* summary.json 생성
* gate.json 기반 SLA 판정
* Baseline 기반 성능 비교 분석
* Regression Detection

---

### 3. AI Performance Analysis Pipeline

LLM 기반 성능 분석 자동화

분석 흐름

* Qwen CLI 기반 1차 성능 요약
* GPT-OSS 120B 기반 병목 원인 분석
* 성능 이슈 우선순위 분류
* 개선 포인트 자동 도출

---

### 4. Automated Report Generation

테스트 결과 기반 자동 리포트 생성

지원 결과물

* Markdown Report
* HTML Dashboard Report
* JSON Performance Summary
* Baseline Comparison Report

---

### 5. MCP Tool Integration

MCP 기반 Tool Calling 구조 설계

지원 기능

* Performance Test Trigger
* Result Analysis Pipeline
* Baseline Comparison
* Full QA Pipeline Execution

지원 Tool

* run_jmeter_test
* analyze_jtl
* compare_with_baseline
* run_full_qa_pipeline

---

## 시스템 아키텍처

```text
JMeter Load Testing
        ↓
raw.jtl Collection
        ↓
summary.json Generation
        ↓
gate.json SLA Validation
        ↓
Baseline Comparison
        ↓
Qwen CLI Analysis
        ↓
GPT-OSS Deep Analysis
        ↓
Markdown / HTML Report Generation
```

---

## 기술 스택

Backend

* Python
* Apache JMeter
* JSON Processing Pipeline

AI Integration

* Qwen CLI
* GPT-OSS 120B
* MCP Architecture
* Tool Calling Pipeline

Reporting

* Markdown Report Generation
* HTML Report Generation
* Performance Regression Detection

---

## 개발하면서 집중한 부분

* End-to-End 성능 테스트 자동화 Pipeline 설계
* AI 기반 병목 분석 자동화 구조 구현
* Baseline 기반 Regression Detection 구현
* MCP Tool Calling 기반 Agent 연동 구조 설계
* 반복 가능한 QA Automation Architecture 구현

---

## 기대 효과

* 성능 테스트 반복 작업 자동화
* 병목 원인 분석 시간 단축
* 배포 후 성능 저하 자동 탐지
* QA 엔지니어 수동 분석 최소화
* AI 기반 QA Automation 구조 검증
