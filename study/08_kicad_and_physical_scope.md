# KiCad와 물리 범위

현재 KiCad 자료는 K26 모듈과 Memory FPGA가 실장된 전체 보드가 아니다. J1/J2
일반 경계 커넥터, MLCC, 단일 DDR3L slice와 일부 GTH·기준 클록 배선을 둔 참조
라우팅 쿠폰이다.

footprint 29개, 라우팅된 GTH/refclk 관련 net 20개, 선언한 제한 범위 ERC/DRC 0을
확인했다. 이 값은 쿠폰 subset에만 적용된다.

정확한 MPN, K26 connector pinout, FPGA package·transceiver quad, 네 MIG bank,
전원 트리, 전체 배선, SI/PI/PDN/thermal/EMC와 제조 검사가 남아 있다. 항상
**NOT FOR FABRICATION**으로 표시한다.
