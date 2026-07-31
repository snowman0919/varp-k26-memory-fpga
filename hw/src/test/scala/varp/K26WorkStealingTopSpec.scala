package varp

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import varp.k26.K26WorkStealingTop
import varp.scheduler.SchedulerPolicy

final class K26WorkStealingTopSpec extends AnyFunSuite {
  test("the paper top elaborates for all controlled scaling points") {
    for {
      clusters <- Seq(1, 2, 4)
      channels <- Seq(1, 2, 4)
      bundles <- Seq(1, 2, 4)
    } {
      SpinalConfig(
        mode = Verilog,
        targetDirectory =
          s"build/k26-top-elaboration-c${clusters}-ch${channels}-b${bundles}"
      )
        .generate(
          new K26WorkStealingTop(
            clusterCount = clusters,
            channelCount = channels,
            bundleCount = bundles,
            policy = SchedulerPolicy.S3LocalityAware
          )
        )
    }
  }

  test("the paper top runs the real MatVec and preserves job identity") {
    SimConfig.withVerilator
      .compile(
        new K26WorkStealingTop(
          clusterCount = 1,
          channelCount = 1,
          bundleCount = 1,
          policy = SchedulerPolicy.S0GlobalFifo,
          commandStoreDepth = 8
        )
      )
      .doSim { dut =>
        dut.clockDomain.forkStimulus(2)
        dut.io.command.valid #= false
        dut.io.memoryRequest.valid #= false
        dut.io.linkInput.valid #= false
        dut.io.results(0).ready #= true
        dut.io.memoryCommands(0).ready #= true
        dut.io.linkBundles(0).ready #= true
        dut.io.clusterChannel(0) #= 0
        dut.io.clusterLinkBundle(0) #= 0
        dut.io.activationResident(0) #= false
        dut.io.residentActivationId(0) #= 0
        dut.io.now #= 0
        dut.clockDomain.waitSampling(5)

        val activation =
          Seq(3, -2, 1, 4, -1, 2, 0, 5, 2, -3, 1, 1, 4, 0, -2, 3)
        val weights = Seq(
          Seq(1, 0, -1, 2, 1, 1, 0, -2, 2, 1, 1, 0, -1, 2, 0, 1),
          Seq(-1, 2, 0, 1, 3, -2, 1, 0, 1, 1, -1, 2, 0, -1, 2, 1),
          Seq(2, 1, 1, 0, -1, 2, 3, 1, 0, -2, 1, 1, 2, 0, -1, 1),
          Seq(0, -1, 2, 3, 1, 0, -2, 1, 2, 1, 0, -1, 1, 2, 3, 0)
        )
        val expected = weights.map(row =>
          row.zip(activation).map { case (w, a) => w * a }.sum
        )

        val job = dut.io.command.payload.job
        job.jobId #= 77
        job.arrivalTimestamp #= 0
        job.layerId #= 2
        job.operationType #= 0
        job.activationId #= 3
        job.weightBase #= 0x1000
        job.outputBase #= 0x2000
        job.kStart #= 0
        job.kLength #= 16
        job.nStart #= 0
        job.nLength #= 4
        job.preferredChannel #= 0
        job.preferredLinkBundle #= 0
        job.reductionOwner #= 0
        job.priority #= 0
        job.stealable #= true
        activation.indices.foreach(index =>
          dut.io.command.payload.activation(index) #= activation(index)
        )
        for {
          output <- weights.indices
          input <- weights(output).indices
        } dut.io.command.payload.weights(output)(input) #= weights(output)(input)

        dut.io.command.valid #= true
        while (!dut.io.command.ready.toBoolean) {
          dut.clockDomain.waitSampling()
        }
        dut.clockDomain.waitSampling()
        dut.io.command.valid #= false

        var cycles = 0
        while (!dut.io.results(0).valid.toBoolean && cycles < 200) {
          dut.io.now #= cycles
          dut.clockDomain.waitSampling()
          cycles += 1
        }
        assert(cycles < 200)
        assert(dut.io.results(0).payload.job.jobId.toBigInt == 77)
        for (index <- expected.indices) {
          assert(
            dut.io.results(0).payload.outputs(index).toBigInt == expected(index)
          )
        }
        dut.clockDomain.waitSampling()
        assert(dut.io.completedJobs(0).toBigInt == 1)
      }
  }
}
