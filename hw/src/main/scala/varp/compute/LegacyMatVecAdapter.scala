package varp.compute

import qk.{DecodeMatVecInt8, DecodeMatVecInt8Config}
import spinal.core._
import spinal.lib._

/** Ready/valid wrapper around the imported qk.DecodeMatVecInt8 primitive.
  *
  * A complete command is retained for the primitive's 65-cycle execution.
  * The result and its TileJob identity remain stable under output
  * backpressure.
  */
class LegacyMatVecAdapter(config: TileJobConfig = TileJobConfig())
    extends Component {
  val io = new Bundle {
    val command = slave Stream (MatVecTileCommand(config))
    val result = master Stream (MatVecTileResult(config))
    val active = out Bool ()
    val computeCycles = out UInt (16 bits)
  }

  val primitive = new DecodeMatVecInt8(
    DecodeMatVecInt8Config(
      inputDim = config.inputDim,
      outputDim = config.outputDim,
      tileDim = 1,
      dataWidth = config.dataWidth,
      accWidth = config.accWidth
    )
  )

  val commandReg =
    Reg(MatVecTileCommand(config)) init (MatVecTileCommand(config).getZero)
  val resultReg =
    Reg(MatVecTileResult(config)) init (MatVecTileResult(config).getZero)
  val launching = Reg(Bool()) init (False)
  val running = Reg(Bool()) init (False)
  val resultValid = Reg(Bool()) init (False)
  val cycles = Reg(UInt(16 bits)) init (0)

  io.command.ready := !launching && !running && !resultValid
  when(io.command.fire) {
    commandReg := io.command.payload
    launching := True
    cycles := 0
  }

  primitive.io.start := launching
  primitive.io.activation := commandReg.activation
  primitive.io.weights := commandReg.weights

  when(launching) {
    launching := False
    running := True
  }
  when(running) {
    cycles := cycles + 1
    when(primitive.io.done) {
      resultReg.job := commandReg.job
      resultReg.outputs := primitive.io.outputs
      running := False
      resultValid := True
    }
  }

  io.result.valid := resultValid
  io.result.payload := resultReg
  when(io.result.fire) {
    resultValid := False
  }

  io.active := launching || running || resultValid
  io.computeCycles := cycles

  when(!ClockDomain.current.isResetActive) {
    assert(!(io.command.fire && (launching || running || resultValid)))
    when(io.result.valid) {
      assert(io.result.payload.job.kStart === 0)
      assert(io.result.payload.job.kLength === config.inputDim)
      assert(io.result.payload.job.nLength > 0)
      assert(io.result.payload.job.nLength <= config.outputDim)
    }
  }
}
