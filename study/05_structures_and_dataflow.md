# 구조와 데이터 흐름

## 닫힌 compute path

`MatVecTileCommand → TileScheduler → associative payload store → ComputeClusterArray → MatVecTileResult`

이 경로는 runnable RTL이며 synthetic steal identity와 actual MatVec result를 연결한다.

## 독립 memory/link planes

`memoryRequest → channel mapping → bank-aware queue → memoryCommands`

`linkInput → bundle select → linkBundles`

둘 다 외부 입력에서 시작한다. response interface, DMA sequencing, GT wrapper, receive path, returned weight insertion은 없다.

## FIFO를 구분하는 이유

TileJob queue는 ‘누가 실행하는가’를 정한다. Transport FIFO는 ‘byte가 언제 이동하는가’를 정한다. 합치면 queue imbalance와 link backpressure를 구분할 수 없다.
