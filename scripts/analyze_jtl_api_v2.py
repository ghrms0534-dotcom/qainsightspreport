#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""JTL 파일을 분석하여 API 별 성능 통계를 산출 - 개선 버전"""

import csv
from collections import defaultdict

def analyze_jtl_api_performance(jtl_path):
    """JTL 파일을 분석하여 API 별 통계를 계산"""
    
    api_stats = defaultdict(lambda: {
        'count': 0,
        'elapsed_times': [],
        'latency_times': []
    })
    
    with open(jtl_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            label = row.get('label', 'Unknown')
            
            if not label or label == 'Unknown':
                continue
                
            try:
                elapsed = float(row.get('elapsed', 0))
                latency = float(row.get('Latency', 0))
                success = row.get('success', 'true').lower() == 'true'
                
                api_stats[label]['count'] += 1
                api_stats[label]['elapsed_times'].append(elapsed)
                api_stats[label]['latency_times'].append(latency)
            except (ValueError, TypeError):
                continue
    
    # 통계 계산
    results = []
    for label, stats in api_stats.items():
        elapsed_times = stats['elapsed_times']
        latency_times = stats['latency_times']
        
        if not elapsed_times:
            continue
            
        elapsed_times.sort()
        latency_times.sort()
        
        n = len(elapsed_times)
        avg_elapsed = sum(elapsed_times) / n
        avg_latency = sum(latency_times) / n
        max_elapsed = max(elapsed_times)
        min_elapsed = min(elapsed_times)
        
        # 백분위수 계산
        p50_idx = int(n * 0.50)
        p90_idx = int(n * 0.90)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)
        
        p50_elapsed = elapsed_times[min(p50_idx, n-1)]
        p90_elapsed = elapsed_times[min(p90_idx, n-1)]
        p95_elapsed = elapsed_times[min(p95_idx, n-1)]
        p99_elapsed = elapsed_times[min(p99_idx, n-1)]
        
        success_count = n  # JTL의 success 컬럼이 있으면 확인 가능
        
        results.append({
            'label': label,
            'count': n,
            'avg_ms': round(avg_elapsed, 2),
            'min_ms': round(min_elapsed, 2),
            'max_ms': round(max_elapsed, 2),
            'p50_ms': round(p50_elapsed, 2),
            'p90_ms': round(p90_elapsed, 2),
            'p95_ms': round(p95_elapsed, 2),
            'p99_ms': round(p99_elapsed, 2),
            'avg_latency_ms': round(avg_latency, 2),
            'success_count': success_count
        })
    
    # 평균 응답시간 내림차순으로 정렬
    results.sort(key=lambda x: x['avg_ms'], reverse=True)
    
    return results

def print_report(results, output_path):
    """분석 결과를 보고서로 출력"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 110 + "\n")
        f.write("QA Insights API 성능 분석 보고서 (100명 동시 접속 기준)\n")
        f.write("=" * 110 + "\n")
        f.write(f"총 API 수: {len(results)}개\n")
        f.write("=" * 110 + "\n\n")
        
        f.write("# 1. API 별 응답시간 통계 ( 평균 응답시간 기준 내림차순 )\n")
        f.write("-" * 110 + "\n")
        f.write(f"{'순위':<6} {'API 명':<45} {'평균':<10} {' 최대 ':<10} {' p95 ':<10} {' p99 ':<10} {'요청수':<10}\n")
        f.write("-" * 110 + "\n")
        
        for i, result in enumerate(results, 1):
            f.write(f"{i:<6} {result['label']:<45} {result['avg_ms']:<10.2f} {result['max_ms']:<10.2f} {result['p95_ms']:<10.2f} {result['p99_ms']:<10.2f} {result['count']:<10}\n")
        
        f.write("-" * 110 + "\n\n")
        
        # 병목 구간 분석
        f.write("# 2. 병목 구간 분석\n")
        f.write("-" * 110 + "\n\n")
        
        # 평균 50ms 이상인 API를 병목 후보로 간주
        bottlenecks = [r for r in results if r['avg_ms'] >= 50]
        
        if bottlenecks:
            f.write("## 2.1 병목 후보 API ( 평균 응답시간 ≥ 50ms )\n\n")
            for i, result in enumerate(bottlenecks, 1):
                f.write(f"### {i}. {result['label']}\n")
                f.write(f"- **평균 응답시간**: {result['avg_ms']} ms\n")
                f.write(f"- **최대 응답시간**: {result['max_ms']} ms\n")
                f.write(f"- **p95 응답시간**: {result['p95_ms']} ms\n")
                f.write(f"- **p99 응답시간**: {result['p99_ms']} ms\n")
                f.write(f"- **요청 횟수**: {result['count']}회\n\n")
        
        # 최대 응답시간이 100ms 이상인 API
        f.write("## 2.2 최대 응답시간이 높은 API (max ≥ 100ms)\n\n")
        high_max = [r for r in results if r['max_ms'] >= 100]
        for result in high_max:
            f.write(f"- **{result['label']}**: max {result['max_ms']} ms, avg {result['avg_ms']} ms\n")
        
        f.write("\n## 2.3 분석 및 추천 개선사항\n\n")
        f.write("### 가장 느린 API (우선 개선 대상)\n")
        if results:
            slowest = results[0]
            f.write(f"1. **{slowest['label']}**\n")
            f.write(f"   - 평균: {slowest['avg_ms']} ms, 최대: {slowest['max_ms']} ms\n")
            f.write(f"   - 개선 우선순위: ** Highest **\n")
            f.write(f"   - 가능한 개선 방안:\n")
            f.write(f"     - 데이터베이스 쿼리 최적화 (index 생성, 불필요한 join 제거)\n")
            f.write(f"     - 서버 측 캐싱 적용 (Redis 등)\n")
            f.write(f"     - 응답 데이터 크기 감소 (필요한 필드만 선택)\n\n")
        
        f.write("### 병목 구간 요약\n")
        f.write("-" * 50 + "\n")
        
        if len(results) >= 1:
            f.write(f"1. 가장 느린 API: {results[0]['label']}\n")
            f.write(f"   - 평균: {results[0]['avg_ms']} ms, 최대: {results[0]['max_ms']} ms\n\n")
        if len(results) >= 2:
            f.write(f"2. 두 번째로 느린 API: {results[1]['label']}\n")
            f.write(f"   - 평균: {results[1]['avg_ms']} ms, 최대: {results[1]['max_ms']} ms\n\n")
        if len(results) >= 3:
            f.write(f"3. 세 번째로 느린 API: {results[2]['label']}\n")
            f.write(f"   - 평균: {results[2]['avg_ms']} ms, 최대: {results[2]['max_ms']} ms\n\n")
        
        # 전체 집계
        f.write("-" * 110 + "\n")
        f.write("# 3. 전체 집계\n")
        f.write("-" * 110 + "\n\n")
        
        total_requests = sum(r['count'] for r in results)
        
        all_elapsed = []
        for r in results:
            all_elapsed.extend(r['elapsed_times'] if hasattr(r, 'elapsed_times') else [r['avg_ms']] * r['count'])
        
        if all_elapsed and hasattr(results[0], 'count'):  #	results에 raw data가 있다면
            pass
        else:
            # avg만 있는 경우 추정
            all_raw = []
            for r in results:
                all_raw.extend([r['avg_ms']] * r['count'])
            all_raw.sort()
            
            overall_avg = sum(all_raw) / len(all_raw)
            n = len(all_raw)
            overall_p50 = all_raw[int(n * 0.50)]
            overall_p90 = all_raw[int(n * 0.90)]
            overall_p95 = all_raw[int(n * 0.95)]
            overall_p99 = all_raw[min(int(n * 0.99), n-1)]
            
            f.write(f"- **총 요청 수**: {total_requests}\n")
            f.write(f"- **전체 평균 응답시간**: {overall_avg:.2f} ms\n")
            f.write(f"- **전체 p50**: {overall_p50:.2f} ms\n")
            f.write(f"- **전체 p90**: {overall_p90:.2f} ms\n")
            f.write(f"- **전체 p95**: {overall_p95:.2f} ms\n")
            f.write(f"- **전체 p99**: {overall_p99:.2f} ms\n")
    
    print(f"보고서가 {output_path}에 작성되었습니다.")
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("사용법: python analyze_jtl_api.py <jtl_file_path> [output_path]")
        sys.exit(1)
    
    jtl_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "api_performance_report.txt"
    
    print(f"분석 중: {jtl_path}")
    results = analyze_jtl_api_performance(jtl_path)
    print_report(results, output_path)
    
    print("\n API 별 상위 15개:")
    print("-" * 110)
    for i, r in enumerate(results[:15], 1):
        print(f"{i:2d}. {r['label']:<45} avg: {r['avg_ms']:>7.2f}ms, max: {r['max_ms']:>7.2f}ms, p95: {r['p95_ms']:>7.2f}ms")
