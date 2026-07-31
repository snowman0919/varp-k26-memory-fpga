# Current architecture and integration boundary

`K26WorkStealingTop` contains three independent functional planes.

1. The compute plane accepts a `MatVecTileCommand`, sends its `TileJob` to
   `TileScheduler`, keeps activation/weight payload in an associative store,
   dispatches the selected payload to `ComputeClusterArray`, and returns a
   `MatVecTileResult`.
2. The memory-command plane accepts an unrelated external `memoryRequest`,
   maps it to a channel, applies a bank-aware queue, and emits
   `memoryCommands`. There is no response interface.
3. The link plane accepts an unrelated external `linkInput`, selects a bundle,
   and emits `linkBundles`. It has no GT wrapper or receive path.

There is therefore no implemented path of the form:

`TileJob → DMA request → DDR command/response → link transfer → payload store → MatVec`.

The scheduler-to-payload-store-to-MatVec path is runnable RTL. DDR PHY, memory
responses, DMA sequencing, GT wrappers, CDC implementation, and returned weight
insertion are future integration gates. The KiCad design is a conditional
physical proposal and does not close those gates.
