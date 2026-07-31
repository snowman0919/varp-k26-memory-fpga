package varp.scheduler

import spinal.core._
import spinal.lib._
import varp.compute.{TileJob, TileJobConfig}

object SchedulerPolicy {
  val S0GlobalFifo = 0
  val S1LocalFcfs = 1
  val S2OldestSteal = 2
  val S3LocalityAware = 3
  val All: Set[Int] =
    Set(S0GlobalFifo, S1LocalFcfs, S2OldestSteal, S3LocalityAware)
}

final case class LocalityWeights(
    age: Int = 8,
    weightChannel: Int = 8,
    activation: Int = 12,
    reduction: Int = 16,
    linkBundle: Int = 8
) {
  require(
    Seq(age, weightChannel, activation, reduction, linkBundle)
      .forall(value => value >= 0 && value <= 65535)
  )
  require(age > 0)
}

case class ScheduledTile(
    config: TileJobConfig,
    clusterCount: Int
) extends Bundle {
  private val clusterWidth = scala.math.max(1, log2Up(clusterCount))
  val job = TileJob(config)
  val sourceCluster = UInt(clusterWidth bits)
  val targetCluster = UInt(clusterWidth bits)
  val stolen = Bool()
  val localityScore = UInt(64 bits)
}

/** Synthesizable S0-S3 tile scheduler.
  *
  * S0 owns one global FIFO. S1-S3 route ingress to deterministic local FCFS
  * queues using job_id modulo cluster_count. S2 and S3 inspect only victim
  * queue heads, preserving FCFS within every local queue. At most one job is
  * dispatched per edge, which makes exact-once ownership explicit.
  */
class TileScheduler(
    val clusterCount: Int,
    val policy: Int,
    config: TileJobConfig = TileJobConfig(),
    queueDepth: Int = 8,
    weights: LocalityWeights = LocalityWeights()
) extends Component {
  require(Set(1, 2, 4).contains(clusterCount))
  require(SchedulerPolicy.All.contains(policy))
  require(queueDepth >= 2)

  private val clusterWidth = scala.math.max(1, log2Up(clusterCount))
  private val liveDepth =
    if (policy == SchedulerPolicy.S0GlobalFifo) queueDepth
    else queueDepth * clusterCount
  private val liveCountWidth = log2Up(liveDepth + 1)

  val io = new Bundle {
    val now = in UInt (config.timestampWidth bits)
    val input = slave Stream (TileJob(config))
    val dispatch =
      Vec(master(Stream(ScheduledTile(config, clusterCount))), clusterCount)
    val clusterChannel =
      in Vec (UInt(config.channelWidth bits), clusterCount)
    val clusterLinkBundle =
      in Vec (UInt(config.bundleWidth bits), clusterCount)
    val activationResident = in Vec (Bool(), clusterCount)
    val residentActivationId =
      in Vec (UInt(config.activationIdWidth bits), clusterCount)
    val acceptedJobs = out UInt (64 bits)
    val dispatchedJobs = out UInt (64 bits)
    val stealAttempts = out UInt (64 bits)
    val successfulSteals = out UInt (64 bits)
    val liveJobs = out UInt (liveCountWidth bits)
    val localQueueOccupancy =
      out Vec (UInt(log2Up(queueDepth + 1) bits), clusterCount)
  }

  val globalQueue = StreamFifo(TileJob(config), queueDepth)
  val localQueues =
    Array.fill(clusterCount)(StreamFifo(TileJob(config), queueDepth))

  globalQueue.io.push.payload := io.input.payload
  for (queue <- localQueues) {
    queue.io.push.payload := io.input.payload
  }

  val liveValid = Vec(Reg(Bool()) init (False), liveDepth)
  val liveIds =
    Vec(Reg(UInt(config.jobIdWidth bits)) init (0), liveDepth)
  val liveFree = Bits(liveDepth bits)
  val duplicate = Bits(liveDepth bits)
  for (entry <- 0 until liveDepth) {
    liveFree(entry) := !liveValid(entry)
    duplicate(entry) :=
      liveValid(entry) && liveIds(entry) === io.input.payload.jobId
  }
  val freeAvailable = liveFree.orR
  val freeIndex =
    OHToUInt(OHMasking.first(liveFree))
      .resize(scala.math.max(1, log2Up(liveDepth)))

  if (policy == SchedulerPolicy.S0GlobalFifo) {
    globalQueue.io.push.valid := io.input.valid && freeAvailable
    io.input.ready := globalQueue.io.push.ready && freeAvailable
    for (queue <- localQueues) {
      queue.io.push.valid := False
    }
  } else {
    globalQueue.io.push.valid := False
    val owner =
      (io.input.payload.jobId % clusterCount).resize(clusterWidth)
    val ownerReady = Bits(clusterCount bits)
    for (index <- 0 until clusterCount) {
      val selected = owner === index
      localQueues(index).io.push.valid :=
        io.input.valid && freeAvailable && selected
      ownerReady(index) := selected && localQueues(index).io.push.ready
    }
    io.input.ready := ownerReady.orR && freeAvailable
  }

  when(io.input.fire) {
    assert(!duplicate.orR)
    assert(io.input.payload.kStart === 0)
    assert(io.input.payload.kLength === config.inputDim)
    assert(io.input.payload.nLength > 0)
    assert(io.input.payload.nLength <= config.outputDim)
    if (clusterCount < (1 << config.ownerWidth)) {
      assert(io.input.payload.reductionOwner < clusterCount)
    }
    liveValid(freeIndex) := True
    liveIds(freeIndex) := io.input.payload.jobId
  }

  val accepted = Reg(UInt(64 bits)) init (0)
  val dispatched = Reg(UInt(64 bits)) init (0)
  val attempts = Reg(UInt(64 bits)) init (0)
  val steals = Reg(UInt(64 bits)) init (0)
  attempts := attempts
  when(io.input.fire) {
    accepted := accepted + 1
  }

  val dispatchFire = Bool()
  val dispatchedJobId = UInt(config.jobIdWidth bits)
  val dispatchedWasSteal = Bool()

  if (policy == SchedulerPolicy.S0GlobalFifo) {
    for (queue <- localQueues) {
      queue.io.pop.ready := False
    }
    val readyTargets = Bits(clusterCount bits)
    for (target <- 0 until clusterCount) {
      readyTargets(target) := io.dispatch(target).ready
    }
    val targetOH = OHMasking.first(readyTargets)
    for (target <- 0 until clusterCount) {
      io.dispatch(target).valid :=
        globalQueue.io.pop.valid && targetOH(target)
      io.dispatch(target).payload.job := globalQueue.io.pop.payload
      io.dispatch(target).payload.sourceCluster := target
      io.dispatch(target).payload.targetCluster := target
      io.dispatch(target).payload.stolen := False
      io.dispatch(target).payload.localityScore :=
        (io.now - globalQueue.io.pop.payload.arrivalTimestamp).resize(64)
    }
    val anyFire =
      io.dispatch.map(_.fire).reduce(_ || _)
    globalQueue.io.pop.ready := anyFire
    dispatchFire := anyFire
    dispatchedJobId := globalQueue.io.pop.payload.jobId
    dispatchedWasSteal := False
  } else {
    globalQueue.io.pop.ready := False
    for (queue <- localQueues) {
      queue.io.pop.ready := False
    }
    dispatchFire := False
    dispatchedJobId := 0
    dispatchedWasSteal := False
    val candidateValid = Vec(Bool(), clusterCount)
    val candidateSourceOH = Vec(Bits(clusterCount bits), clusterCount)
    val candidateScore = Vec(UInt(64 bits), clusterCount)

    for (target <- 0 until clusterCount) {
      val localValid = localQueues(target).io.pop.valid
      val localAge =
        (io.now -
          localQueues(target).io.pop.payload.arrivalTimestamp).resize(64)
      val sourceOH = Bits(clusterCount bits)
      for (source <- 0 until clusterCount) {
        sourceOH(source) := (if (source == target) localValid else False)
      }
      var stealValid: Bool = False
      var stealSource: UInt = U(0, clusterWidth bits)
      var stealScore: UInt = U(0, 64 bits)
      var stealArrival: UInt =
        U((BigInt(1) << config.timestampWidth) - 1,
          config.timestampWidth bits)
      var stealJobId: UInt =
        U((BigInt(1) << config.jobIdWidth) - 1,
          config.jobIdWidth bits)

      if (
        policy == SchedulerPolicy.S2OldestSteal ||
        policy == SchedulerPolicy.S3LocalityAware
      ) {
        for (source <- 0 until clusterCount if source != target) {
          val job = localQueues(source).io.pop.payload
          val fullK =
            job.kStart === 0 && job.kLength === config.inputDim
          val eligible =
            localQueues(source).io.pop.valid && job.stealable && fullK
          val age = (io.now - job.arrivalTimestamp).resize(64)
          val channelCost =
            Mux(
              job.preferredChannel =/= io.clusterChannel(target),
              U(weights.weightChannel, 64 bits),
              U(0, 64 bits)
            )
          val bundleCost =
            Mux(
              job.preferredLinkBundle =/=
                io.clusterLinkBundle(target),
              U(weights.linkBundle, 64 bits),
              U(0, 64 bits)
            )
          val activationCost =
            Mux(
              !io.activationResident(target) ||
                io.residentActivationId(target) =/= job.activationId,
              U(weights.activation, 64 bits),
              U(0, 64 bits)
            )
          val reductionCost =
            Mux(
              job.reductionOwner =/= target,
              U(weights.reduction, 64 bits),
              U(0, 64 bits)
            )
          val benefit = (age * weights.age).resize(64)
          val totalCost =
            (channelCost + bundleCost + activationCost + reductionCost)
              .resize(64)
          val positive =
            if (policy == SchedulerPolicy.S3LocalityAware)
              benefit > totalCost
            else True
          val score =
            if (policy == SchedulerPolicy.S3LocalityAware)
              (benefit - totalCost).resize(64)
            else age
          val betterScore = score > stealScore
          val sameScoreOlder =
            score === stealScore &&
              job.arrivalTimestamp < stealArrival
          val sameAgeLowerId =
            score === stealScore &&
              job.arrivalTimestamp === stealArrival &&
              job.jobId < stealJobId
          val better =
            !stealValid || betterScore || sameScoreOlder || sameAgeLowerId
          val choose = eligible && positive && better
          stealSource = Mux(choose, U(source, clusterWidth bits), stealSource)
          stealScore = Mux(choose, score, stealScore)
          stealArrival =
            Mux(choose, job.arrivalTimestamp, stealArrival)
          stealJobId = Mux(choose, job.jobId, stealJobId)
          stealValid = stealValid || (eligible && positive)
        }
      }

      when(!localValid && stealValid) {
        for (source <- 0 until clusterCount) {
          sourceOH(source) := stealSource === source
        }
      }
      candidateValid(target) := localValid || (!localValid && stealValid)
      candidateSourceOH(target) := sourceOH
      candidateScore(target) := Mux(localValid, localAge, stealScore)
    }

    val runnableTargets = Bits(clusterCount bits)
    for (target <- 0 until clusterCount) {
      runnableTargets(target) :=
        candidateValid(target) && io.dispatch(target).ready
    }
    val targetOH = OHMasking.first(runnableTargets)

    for (target <- 0 until clusterCount) {
      val sourceOH = candidateSourceOH(target)
      val selectedJob =
        MuxOH(
          sourceOH,
          localQueues.map(_.io.pop.payload).toSeq
        )
      val isSteal = !sourceOH(target)
      io.dispatch(target).valid :=
        candidateValid(target) && targetOH(target)
      io.dispatch(target).payload.job := selectedJob
      io.dispatch(target).payload.sourceCluster :=
        OHToUInt(sourceOH).resize(clusterWidth)
      io.dispatch(target).payload.targetCluster := target
      io.dispatch(target).payload.stolen := isSteal
      io.dispatch(target).payload.localityScore :=
        candidateScore(target)

      when(io.dispatch(target).fire) {
        for (source <- 0 until clusterCount) {
          when(sourceOH(source)) {
            localQueues(source).io.pop.ready := True
          }
        }
        dispatchFire := True
        dispatchedJobId := selectedJob.jobId
        dispatchedWasSteal := isSteal
        when(isSteal) {
          assert(selectedJob.stealable)
          assert(selectedJob.kStart === 0)
          assert(selectedJob.kLength === config.inputDim)
        } otherwise {
          assert(
            OHToUInt(sourceOH).resize(clusterWidth) === target
          )
        }
      }
    }

    var idleWithVictim: Bool = False
    if (
      policy == SchedulerPolicy.S2OldestSteal ||
      policy == SchedulerPolicy.S3LocalityAware
    ) {
      for (target <- 0 until clusterCount) {
        val victimExists =
          (0 until clusterCount)
            .filter(_ != target)
            .map(source =>
              localQueues(source).io.pop.valid &&
                localQueues(source).io.pop.payload.stealable
            )
            .foldLeft(False)(_ || _)
        idleWithVictim =
          idleWithVictim ||
            (!localQueues(target).io.pop.valid && victimExists)
      }
    }
    when(idleWithVictim) {
      attempts := attempts + 1
    }
  }

  val retireHits = Bits(liveDepth bits)
  for (entry <- 0 until liveDepth) {
    retireHits(entry) :=
      liveValid(entry) && liveIds(entry) === dispatchedJobId
  }
  when(dispatchFire) {
    assert(CountOne(retireHits) === 1)
    for (entry <- 0 until liveDepth) {
      when(retireHits(entry)) {
        liveValid(entry) := False
      }
    }
    dispatched := dispatched + 1
    when(dispatchedWasSteal) {
      steals := steals + 1
    }
  }

  val liveCount = CountOne(liveValid.asBits).resize(liveCountWidth)
  when(!ClockDomain.current.isResetActive) {
    assert(dispatched <= accepted)
    assert((accepted - dispatched).resize(liveCountWidth) === liveCount)
  }

  io.acceptedJobs := accepted
  io.dispatchedJobs := dispatched
  io.stealAttempts := attempts
  io.successfulSteals := steals
  io.liveJobs := liveCount
  for (index <- 0 until clusterCount) {
    io.localQueueOccupancy(index) := localQueues(index).io.occupancy
  }
}
