# 실험과 지표

Synthetic workload는 balanced, skew, hotspot, bursty, mixed 각각 1,000 job이고 seed는 19/23/29/31/43이다. 동일 seed의 3회 반복은 결정성 검사이며 표본 수를 늘리지 않는다.

Full-overlap은 `data-ready=max(link-end,memory-end)`, sequential은 두 서비스를 더한다. 두 모델 모두 DMA/PHY cycle timing이 아니다.

지표는 p50/p95/p99, completion time, successful steals, remote weight bytes, compute duty, reservation occupancy, unreserved idle을 함께 본다. occupancy가 99%여도 MAC이 99% 계산했다는 뜻은 아니다.

정상성 조건은 input/dispatched/completed ID set 동일, duplicate 0, timeout false다.
