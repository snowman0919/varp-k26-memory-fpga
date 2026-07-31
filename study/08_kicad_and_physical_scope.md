# KiCad와 물리 범위

Native KiCad source와 validation coupon은 실제 산출물이다. ERC/제한 DRC는 선언된 규칙과 현재 범위 안에서의 검사다.

그러나 55 unrouted nets, DDR topology/length matching 미완료, SI/PI/PDN/thermal/EMC 미검증, FPGA pin planning·MIG·GT·clock closure 부재 때문에 **NOT FOR FABRICATION**이다.

다음 물리 검증 순서는 schematic/net class 확정 → routing/length match → ERC/DRC 0 → SI/PI/PDN → FPGA constraints/timing → 제작 → bring-up → calibrated power/bandwidth다.
