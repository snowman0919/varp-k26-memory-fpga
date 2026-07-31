package varp

import org.scalatest.funsuite.AnyFunSuite
import qk.DecodeMatVecInt8Stimulus
import spinal.core.SpinalConfig
import spinal.core.sim._
import varp.compute._

import scala.collection.mutable.ArrayBuffer
import scala.util.Random

class ComputeClusterSpec extends AnyFunSuite {
  private val config = TileJobConfig()

  private def driveJob(
      dut: ComputeCluster,
      jobId: Int,
      activation: Seq[Int],
      weights: Seq[Seq[Int]]
  ): Unit = {
    dut.io.command.payload.job.jobId #= jobId
    dut.io.command.payload.job.arrivalTimestamp #= jobId
    dut.io.command.payload.job.layerId #= 1
    dut.io.command.payload.job.operationType #= TileOperation.MatVec
    dut.io.command.payload.job.activationId #= jobId / 2
    dut.io.command.payload.job.weightBase #= jobId * 0x1000L
    dut.io.command.payload.job.outputBase #= jobId * 0x100L
    dut.io.command.payload.job.kStart #= 0
    dut.io.command.payload.job.kLength #= config.inputDim
    dut.io.command.payload.job.nStart #= jobId * config.outputDim
    dut.io.command.payload.job.nLength #= config.outputDim
    dut.io.command.payload.job.preferredChannel #= jobId & 3
    dut.io.command.payload.job.preferredLinkBundle #= jobId & 3
    dut.io.command.payload.job.reductionOwner #= jobId % dut.clusterCount
    dut.io.command.payload.job.priority #= jobId & 0xff
    dut.io.command.payload.job.stealable #= true
    for (index <- activation.indices) {
      dut.io.command.payload.activation(index) #= activation(index)
    }
    for (
      row <- weights.indices;
      column <- weights(row).indices
    ) {
      dut.io.command.payload.weights(row)(column) #=
        weights(row)(column)
    }
  }

  private def offer(dut: ComputeCluster): Unit = {
    dut.io.command.valid #= true
    while (!dut.io.command.ready.toBoolean) {
      dut.clockDomain.waitSampling()
    }
    dut.clockDomain.waitSampling()
    dut.io.command.valid #= false
  }

  test("actual legacy MatVec executes an exact full-K N-axis tile") {
    val activation =
      DecodeMatVecInt8Stimulus.deterministicActivation(config.inputDim)
    val weights =
      DecodeMatVecInt8Stimulus.deterministicWeights(
        qk.DecodeMatVecInt8.DemoConfig
      )
    val expected =
      weights.map(row => activation.zip(row).map {
        case (a, w) => a * w
      }.sum)

    SimConfig.withVerilator
      .workspacePath("build/compute-cluster-exact")
      .compile(new ComputeCluster(0, 1, config))
      .doSim(seed = 0x2601) { dut =>
        dut.clockDomain.forkStimulus(period = 10)
        dut.io.command.valid #= false
        dut.io.result.ready #= true
        driveJob(dut, 0, activation, weights)
        dut.clockDomain.waitSampling()
        offer(dut)

        var guard = 0
        while (!dut.io.result.valid.toBoolean && guard < 100) {
          dut.clockDomain.waitSampling()
          guard += 1
        }
        assert(guard < 100)
        assert(dut.io.result.payload.job.jobId.toBigInt == 0)
        assert(
          (0 until config.outputDim)
            .map(dut.io.result.payload.outputs(_).toInt) == expected
        )
        assert(dut.io.acceptedJobs.toBigInt == 1)
      }
  }

  test("cluster command and output buffers preserve local FCFS order") {
    val random = new Random(0x2602L)
    val activation =
      Seq.fill(config.inputDim)(random.nextInt(31) - 15)
    val commands = (0 until 4).map { jobId =>
      val weights = Seq.fill(config.outputDim, config.inputDim)(
        random.nextInt(31) - 15
      )
      val expected =
        weights.map(row => activation.zip(row).map {
          case (a, w) => a * w
        }.sum)
      (jobId, weights, expected)
    }

    SimConfig.withVerilator
      .workspacePath("build/compute-cluster-fcfs")
      .compile(
        new ComputeCluster(
          clusterId = 0,
          clusterCount = 1,
          config = config,
          queueDepth = 4,
          outputDepth = 2
        )
      )
      .doSim(seed = 0x2602) { dut =>
        dut.clockDomain.forkStimulus(period = 10)
        dut.io.command.valid #= false
        dut.io.result.ready #= false
        dut.clockDomain.waitSampling()

        commands.foreach {
          case (jobId, weights, _) =>
            driveJob(dut, jobId, activation, weights)
            offer(dut)
        }

        val observed = ArrayBuffer.empty[(Int, Seq[Int])]
        var guard = 0
        while (observed.size < commands.size && guard < 500) {
          dut.io.result.ready #= (guard % 5 != 0)
          sleep(1)
          if (
            dut.io.result.valid.toBoolean &&
            dut.io.result.ready.toBoolean
          ) {
            observed += (
              dut.io.result.payload.job.jobId.toBigInt.toInt ->
                (0 until config.outputDim)
                  .map(dut.io.result.payload.outputs(_).toInt)
            )
          }
          dut.clockDomain.waitSampling()
          guard += 1
        }
        assert(observed.map(_._1) == commands.map(_._1))
        assert(observed.map(_._2) == commands.map(_._3))
        dut.clockDomain.waitSampling()
        assert(dut.io.completedJobs.toBigInt == commands.size)
      }
  }

  test("one two and four concrete cluster arrays elaborate") {
    for (count <- Seq(1, 2, 4)) {
      val report = SpinalConfig(
        targetDirectory = s"build/compute-cluster-array-$count"
      ).generateVerilog(new ComputeClusterArray(count, config))
      assert(report.toplevel.clusterCount == count)
    }
  }
}
