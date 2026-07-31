# 전력·비용·에너지

에너지는 측정값이 아니다. INT8 MAC 1/5/15 pJ와 link 24/51.2/120 pJ/bit 민감도를 사용하고, DRAM command dynamic 항을 더한다. Refresh, idle, controller, PHY, regulator와 보드 전체 전력은 제외한다.

비용은 DRAM package와 package 내부 physical die만 정규화한다. K26, Memory FPGA, PCB, 조립, 전원과 커넥터는 제외된다. 따라서 ‘전체 시스템 가격’이라고 부르면 안 된다.

외부 8 GiB는 Gemma 1B capacity 때문에 필수라는 결과가 아니다. context-32K INT8 모델 2.4301 GiB가 명목 4 GB에 들어가므로, 채택은 대역폭·경합·전력 측정 뒤에 결정한다.
