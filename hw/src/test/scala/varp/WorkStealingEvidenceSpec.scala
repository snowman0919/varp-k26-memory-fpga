package varp

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Paths}

import org.scalatest.funsuite.AnyFunSuite
import spinal.core.sim._
import varp.compute.{TileJobConfig, TileOperation}
import varp.evidence.WorkStealingEvidenceTop

import scala.collection.mutable.ArrayBuffer

final class WorkStealingEvidenceSpec extends AnyFunSuite {
  private val config = TileJobConfig()

  private val activation =
    Seq(3, -2, 1, 4, -1, 2, 0, 5, 2, -3, 1, 1, 4, 0, -2, 3)
  private val weights = Seq(
    Seq(1, 0, -1, 2, 1, 1, 0, -2, 2, 1, 1, 0, -1, 2, 0, 1),
    Seq(-1, 2, 0, 1, 3, -2, 1, 0, 1, 1, -1, 2, 0, -1, 2, 1),
    Seq(2, 1, 1, 0, -1, 2, 3, 1, 0, -2, 1, 1, 2, 0, -1, 1),
    Seq(0, -1, 2, 3, 1, 0, -2, 1, 2, 1, 0, -1, 1, 2, 3, 0)
  )
  private val expected =
    weights.map(row => row.zip(activation).map { case (w, a) => w * a }.sum)

  private def driveCommand(
      dut: WorkStealingEvidenceTop,
      jobId: Int,
      arrival: Long
  ): Unit = {
    val command = dut.io.command.payload
    command.job.jobId #= jobId
    command.job.arrivalTimestamp #= arrival
    command.job.layerId #= 1
    command.job.operationType #= TileOperation.MatVec
    command.job.activationId #= 0
    command.job.weightBase #= jobId * 0x1000L
    command.job.outputBase #= jobId * 0x100L
    command.job.kStart #= 0
    command.job.kLength #= config.inputDim
    command.job.nStart #= 0
    command.job.nLength #= config.outputDim
    command.job.preferredChannel #= 0
    command.job.preferredLinkBundle #= 0
    command.job.reductionOwner #= 0
    command.job.priority #= 0
    command.job.stealable #= true
    activation.indices.foreach(index =>
      command.activation(index) #= activation(index)
    )
    for {
      output <- weights.indices
      input <- weights(output).indices
    } command.weights(output)(input) #= weights(output)(input)
  }

  test("capture one exact stealing-to-real-MatVec temporal trace") {
    SimConfig.withVcdWave
      .waveFilePrefix("work_stealing_case")
      .withVerilator
      .workspacePath("build/work-stealing-evidence")
      .compile(new WorkStealingEvidenceTop())
      .doSim(seed = 0x100001) { dut =>
        dut.clockDomain.forkStimulus(period = 10)
        dut.io.command.valid #= false
        for (cluster <- 0 until dut.clusterCount) {
          dut.io.clusterEnable(cluster) #= false
          dut.io.results(cluster).ready #= true
        }
        dut.io.now #= 0
        dut.clockDomain.waitSampling(5)

        val lines = ArrayBuffer(
          "cycle,input_valid,input_ready,job_id,q0,q1,q2,q3,victim,target," +
            "eligible,age,locality_score,steal_event,dispatch_job_id," +
            "matvec_start_0,matvec_active_0,matvec_result_0," +
            "accepted,dispatched,successful_steals"
        )
        val completed = ArrayBuffer.empty[Int]
        var cycle = 0

        def sample(): Unit = {
          sleep(1)
          lines += Seq(
            cycle,
            dut.io.command.valid.toBoolean,
            dut.io.command.ready.toBoolean,
            dut.io.command.payload.job.jobId.toBigInt,
            dut.io.queueOccupancy(0).toBigInt,
            dut.io.queueOccupancy(1).toBigInt,
            dut.io.queueOccupancy(2).toBigInt,
            dut.io.queueOccupancy(3).toBigInt,
            dut.io.victimQueue.toBigInt,
            dut.io.dispatchTarget.toBigInt,
            dut.io.eligible.toBoolean,
            dut.io.age.toBigInt,
            dut.io.localityScore.toBigInt,
            dut.io.stealEvent.toBoolean,
            dut.io.dispatchJobId.toBigInt,
            dut.io.matVecStart(0).toBoolean,
            dut.io.matVecActive(0).toBoolean,
            dut.io.matVecResult(0).toBoolean,
            dut.io.acceptedJobs.toBigInt,
            dut.io.dispatchedJobs.toBigInt,
            dut.io.successfulSteals.toBigInt
          ).mkString(",")
          for (cluster <- 0 until dut.clusterCount) {
            if (dut.io.results(cluster).valid.toBoolean) {
              val result = dut.io.results(cluster).payload
              for (index <- expected.indices) {
                assert(result.outputs(index).toBigInt == expected(index))
              }
              completed += result.job.jobId.toBigInt.toInt
            }
          }
        }

        for ((jobId, index) <- Seq(1, 5, 9).zipWithIndex) {
          driveCommand(dut, jobId, cycle)
          dut.io.command.valid #= true
          while (!dut.io.command.ready.toBoolean) {
            dut.io.now #= cycle
            sample()
            dut.clockDomain.waitSampling()
            cycle += 1
          }
          dut.io.now #= cycle
          sample()
          dut.clockDomain.waitSampling()
          cycle += 1
          dut.io.command.valid #= false
        }

        while (cycle < 16) {
          dut.io.now #= cycle
          sample()
          dut.clockDomain.waitSampling()
          cycle += 1
        }
        dut.io.clusterEnable(0) #= true

        while (completed.size < 3 && cycle < 280) {
          dut.io.now #= cycle
          sample()
          dut.clockDomain.waitSampling()
          cycle += 1
        }
        assert(completed.sorted == Seq(1, 5, 9))
        assert(dut.io.successfulSteals.toBigInt == 3)
        assert(dut.io.acceptedJobs.toBigInt == 3)
        assert(dut.io.dispatchedJobs.toBigInt == 3)

        val output = Paths.get("evidence/waveforms/work_stealing_events.csv")
        Files.createDirectories(output.getParent)
        Files.write(
          output,
          (lines.mkString("\n") + "\n").getBytes(StandardCharsets.UTF_8)
        )
      }
  }
}
