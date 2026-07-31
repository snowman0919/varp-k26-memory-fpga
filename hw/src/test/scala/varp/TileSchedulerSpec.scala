package varp

import org.scalatest.funsuite.AnyFunSuite
import spinal.core.sim._
import varp.compute.{TileJobConfig, TileOperation}
import varp.scheduler._

import scala.collection.mutable.ArrayBuffer
import scala.util.Random

class TileSchedulerSpec extends AnyFunSuite {
  private val config = TileJobConfig()

  private def initialize(dut: TileScheduler): Unit = {
    dut.io.now #= 100
    dut.io.input.valid #= false
    for (cluster <- 0 until dut.clusterCount) {
      dut.io.dispatch(cluster).ready #= false
      dut.io.clusterChannel(cluster) #= cluster
      dut.io.clusterLinkBundle(cluster) #= cluster
      dut.io.activationResident(cluster) #= false
      dut.io.residentActivationId(cluster) #= 0
    }
  }

  private def driveJob(
      dut: TileScheduler,
      jobId: Int,
      arrival: Long,
      stealable: Boolean = true,
      preferredChannel: Int = 0,
      preferredBundle: Int = 0,
      activationId: Int = 0,
      reductionOwner: Int = 0
  ): Unit = {
    val job = dut.io.input.payload
    job.jobId #= jobId
    job.arrivalTimestamp #= arrival
    job.layerId #= jobId & 0xffff
    job.operationType #= TileOperation.MatVec
    job.activationId #= activationId
    job.weightBase #= jobId * 0x1000L
    job.outputBase #= jobId * 0x100L
    job.kStart #= 0
    job.kLength #= config.inputDim
    job.nStart #= jobId * config.outputDim
    job.nLength #= config.outputDim
    job.preferredChannel #= preferredChannel
    job.preferredLinkBundle #= preferredBundle
    job.reductionOwner #= reductionOwner
    job.priority #= jobId & 0xff
    job.stealable #= stealable
  }

  private def offer(dut: TileScheduler): Unit = {
    dut.io.input.valid #= true
    while (!dut.io.input.ready.toBoolean) {
      dut.clockDomain.waitSampling()
    }
    dut.clockDomain.waitSampling()
    dut.io.input.valid #= false
  }

  private def awaitOne(dut: TileScheduler): (Int, Int, Int, Boolean) = {
    var guard = 0
    while (
      !(0 until dut.clusterCount)
        .exists(index => dut.io.dispatch(index).valid.toBoolean) &&
      guard < 100
    ) {
      dut.clockDomain.waitSampling()
      guard += 1
    }
    assert(guard < 100)
    val target = (0 until dut.clusterCount)
      .find(index => dut.io.dispatch(index).valid.toBoolean)
      .get
    val payload = dut.io.dispatch(target).payload
    val result = (
      payload.job.jobId.toBigInt.toInt,
      payload.sourceCluster.toInt,
      payload.targetCluster.toInt,
      payload.stolen.toBoolean
    )
    dut.clockDomain.waitSampling()
    result
  }

  test("S0 global FIFO dispatches in order to the first available cluster") {
    SimConfig.withVerilator
      .workspacePath("build/tile-scheduler-s0")
      .compile(
        new TileScheduler(4, SchedulerPolicy.S0GlobalFifo, config)
      )
      .doSim(seed = 0x2700) { dut =>
        dut.clockDomain.forkStimulus(period = 10)
        initialize(dut)
        dut.clockDomain.waitSampling()
        driveJob(dut, 10, 10, reductionOwner = 2)
        offer(dut)

        dut.io.dispatch(2).ready #= true
        dut.io.dispatch(3).ready #= true
        assert(awaitOne(dut) == ((10, 2, 2, false)))
        dut.io.dispatch(2).ready #= false
        dut.io.dispatch(3).ready #= false
        driveJob(dut, 11, 11, reductionOwner = 3)
        offer(dut)
        dut.io.dispatch(0).ready #= true
        sleep(1)
        assert(awaitOne(dut) == ((11, 0, 0, false)))
      }
  }

  test("S1 local queues preserve static FCFS and never steal") {
    SimConfig.withVerilator
      .workspacePath("build/tile-scheduler-s1")
      .compile(
        new TileScheduler(4, SchedulerPolicy.S1LocalFcfs, config)
      )
      .doSim(seed = 0x2701) { dut =>
        dut.clockDomain.forkStimulus(period = 10)
        initialize(dut)
        dut.clockDomain.waitSampling()
        driveJob(dut, 1, 20, reductionOwner = 1)
        offer(dut)
        driveJob(dut, 5, 10, reductionOwner = 1)
        offer(dut)
        dut.io.dispatch(1).ready #= true
        assert(awaitOne(dut) == ((1, 1, 1, false)))
        assert(awaitOne(dut) == ((5, 1, 1, false)))
        assert(dut.io.successfulSteals.toBigInt == 0)
      }
  }

  test("S2 steals the oldest eligible victim head") {
    SimConfig.withVerilator
      .workspacePath("build/tile-scheduler-s2")
      .compile(
        new TileScheduler(4, SchedulerPolicy.S2OldestSteal, config)
      )
      .doSim(seed = 0x2702) { dut =>
        dut.clockDomain.forkStimulus(period = 10)
        initialize(dut)
        dut.clockDomain.waitSampling()
        driveJob(dut, 1, 20, reductionOwner = 1)
        offer(dut)
        driveJob(dut, 2, 10, reductionOwner = 2)
        offer(dut)
        driveJob(dut, 3, 0, stealable = false, reductionOwner = 3)
        offer(dut)
        dut.io.dispatch(0).ready #= true
        assert(awaitOne(dut) == ((2, 2, 0, true)))
        assert(dut.io.successfulSteals.toBigInt == 1)
      }
  }

  test("S3 age-locality score avoids a costlier remote victim") {
    SimConfig.withVerilator
      .workspacePath("build/tile-scheduler-s3")
      .compile(
        new TileScheduler(
          4,
          SchedulerPolicy.S3LocalityAware,
          config,
          weights = LocalityWeights(
            age = 1,
            weightChannel = 100,
            activation = 100,
            reduction = 100,
            linkBundle = 100
          )
        )
      )
      .doSim(seed = 0x2703) { dut =>
        dut.clockDomain.forkStimulus(period = 10)
        initialize(dut)
        dut.io.now #= 20
        dut.io.clusterChannel(0) #= 0
        dut.io.clusterLinkBundle(0) #= 0
        dut.io.activationResident(0) #= true
        dut.io.residentActivationId(0) #= 7
        dut.clockDomain.waitSampling()

        driveJob(
          dut,
          jobId = 1,
          arrival = 0,
          preferredChannel = 1,
          preferredBundle = 1,
          activationId = 8,
          reductionOwner = 1
        )
        offer(dut)
        driveJob(
          dut,
          jobId = 2,
          arrival = 5,
          preferredChannel = 0,
          preferredBundle = 0,
          activationId = 7,
          reductionOwner = 0
        )
        offer(dut)
        dut.io.dispatch(0).ready #= true
        assert(awaitOne(dut) == ((2, 2, 0, true)))
      }
  }

  test("fixed-seed 1000-job random campaign is exact once and lossless") {
    SimConfig.withVerilator
      .workspacePath("build/tile-scheduler-random")
      .compile(
        new TileScheduler(
          4,
          SchedulerPolicy.S2OldestSteal,
          config,
          queueDepth = 16
        )
      )
      .doSim(seed = 0x2704) { dut =>
        dut.clockDomain.forkStimulus(period = 10)
        initialize(dut)
        dut.clockDomain.waitSampling()
        val random = new Random(0x2704L)
        val ids = random.shuffle((0 until 1000).toVector)
        val received = ArrayBuffer.empty[Int]
        var offered = 0
        var guard = 0

        while (received.size < ids.size && guard < 20000) {
          for (cluster <- 0 until dut.clusterCount) {
            dut.io.dispatch(cluster).ready #=
              random.nextInt(5) != 0
          }
          if (offered < ids.size) {
            val id = ids(offered)
            driveJob(
              dut,
              jobId = id,
              arrival = guard,
              stealable = random.nextInt(7) != 0,
              preferredChannel = random.nextInt(4),
              preferredBundle = random.nextInt(4),
              activationId = random.nextInt(32),
              reductionOwner = id & 3
            )
            dut.io.input.valid #= true
          } else {
            dut.io.input.valid #= false
          }
          sleep(1)
          val inputFire =
            dut.io.input.valid.toBoolean &&
              dut.io.input.ready.toBoolean
          val fired = (0 until dut.clusterCount).filter(index =>
            dut.io.dispatch(index).valid.toBoolean &&
              dut.io.dispatch(index).ready.toBoolean
          )
          assert(fired.size <= 1)
          fired.foreach(index =>
            received +=
              dut.io.dispatch(index).payload.job.jobId.toBigInt.toInt
          )
          dut.clockDomain.waitSampling()
          if (inputFire) {
            offered += 1
          }
          guard += 1
        }

        assert(offered == 1000)
        assert(received.size == 1000)
        assert(received.distinct.size == 1000)
        assert(received.sorted == (0 until 1000))
        dut.clockDomain.waitSampling()
        assert(dut.io.acceptedJobs.toBigInt == 1000)
        assert(dut.io.dispatchedJobs.toBigInt == 1000)
        assert(dut.io.liveJobs.toBigInt == 0)
      }
  }
}
