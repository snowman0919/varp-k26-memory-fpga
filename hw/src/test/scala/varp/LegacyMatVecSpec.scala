package varp

import org.scalatest.funsuite.AnyFunSuite
import qk.{DecodeMatVecInt8, DecodeMatVecInt8Config, DecodeMatVecInt8Stimulus}
import spinal.core.sim._

class LegacyMatVecSpec extends AnyFunSuite {
  private def simulate(cfg: DecodeMatVecInt8Config): (Seq[Int], Int) = {
    val activation = DecodeMatVecInt8Stimulus.deterministicActivation(cfg.inputDim)
    val weights = DecodeMatVecInt8Stimulus.deterministicWeights(cfg)
    var observed = Seq.empty[Int]
    var cycles = 0

    SimConfig
      .withWave
      .workspacePath("build/k26-matvec-sim")
      .compile(new DecodeMatVecInt8(cfg))
      .doSim(seed = 1) { dut =>
        dut.clockDomain.forkStimulus(period = 10)
        dut.io.start #= false
        for (index <- 0 until cfg.inputDim) {
          dut.io.activation(index) #= activation(index)
        }
        for (row <- 0 until cfg.outputDim; column <- 0 until cfg.inputDim) {
          dut.io.weights(row)(column) #= weights(row)(column)
        }

        dut.clockDomain.waitSampling()
        dut.io.start #= true
        dut.clockDomain.waitSampling()
        dut.io.start #= false

        val timeout = (cfg.inputDim / cfg.tileDim) * cfg.outputDim + 12
        while (!dut.io.done.toBoolean && cycles < timeout) {
          dut.clockDomain.waitSampling()
          cycles += 1
        }
        assert(dut.io.done.toBoolean)
        observed = (0 until cfg.outputDim).map(dut.io.outputs(_).toInt)
      }
    (observed, cycles)
  }

  test("exact imported 16x4 primitive preserves CPU result and 65-cycle boundary") {
    val cfg = DecodeMatVecInt8.DemoConfig
    val expected = DecodeMatVecInt8Stimulus.expectedOutputs(cfg)
    val (observed, cycles) = simulate(cfg)
    assert(observed == expected)
    assert(observed == Seq(-271, 239, 287, 797))
    assert(cycles == 65)
  }

  test("tileDim four variant remains bit exact") {
    val cfg = DecodeMatVecInt8Config(inputDim = 64, outputDim = 16, tileDim = 4)
    val (observed, cycles) = simulate(cfg)
    assert(observed == DecodeMatVecInt8Stimulus.expectedOutputs(cfg))
    assert(cycles <= 260)
  }
}
