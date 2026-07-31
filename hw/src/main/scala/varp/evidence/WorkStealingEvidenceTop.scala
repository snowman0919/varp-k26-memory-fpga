package varp.evidence

import spinal.core._
import spinal.lib._
import varp.compute._
import varp.scheduler._

/** Instrumented evidence harness around the production scheduler and MatVec
  * clusters.
  *
  * This component does not replace the paper top.  It exposes the temporal
  * signals required to audit one bounded stealing event while reusing the
  * production TileScheduler, payload store, ComputeClusterArray and actual
  * DecodeMatVecInt8 datapath.
  */
class WorkStealingEvidenceTop(
    val clusterCount: Int = 4,
    val storeDepth: Int = 32,
    config: TileJobConfig = TileJobConfig()
) extends Component {
  require(clusterCount == 4)
  require(storeDepth >= 16)

  private val clusterWidth = log2Up(clusterCount)

  val io = new Bundle {
    val now = in UInt (config.timestampWidth bits)
    val command = slave Stream (MatVecTileCommand(config))
    val clusterEnable = in Vec (Bool(), clusterCount)
    val results =
      Vec(master(Stream(MatVecTileResult(config))), clusterCount)

    val queueOccupancy =
      out Vec (UInt(log2Up(9) bits), clusterCount)
    val victimQueue = out UInt (clusterWidth bits)
    val dispatchTarget = out UInt (clusterWidth bits)
    val eligible = out Bool ()
    val age = out UInt (config.timestampWidth bits)
    val localityScore = out UInt (64 bits)
    val stealEvent = out Bool ()
    val dispatchJobId = out UInt (config.jobIdWidth bits)
    val matVecActive = out Vec (Bool(), clusterCount)
    val matVecStart = out Vec (Bool(), clusterCount)
    val matVecResult = out Vec (Bool(), clusterCount)
    val acceptedJobs = out UInt (64 bits)
    val dispatchedJobs = out UInt (64 bits)
    val successfulSteals = out UInt (64 bits)
  }

  val scheduler = new TileScheduler(
    clusterCount = clusterCount,
    policy = SchedulerPolicy.S3LocalityAware,
    config = config,
    queueDepth = 8
  )
  val clusters = new ComputeClusterArray(
    clusterCount = clusterCount,
    config = config,
    queueDepth = 4,
    outputDepth = 2
  )

  scheduler.io.now := io.now
  for (index <- 0 until clusterCount) {
    scheduler.io.clusterChannel(index) := index
    scheduler.io.clusterLinkBundle(index) := index
    scheduler.io.activationResident(index) := False
    scheduler.io.residentActivationId(index) := 0
  }

  val storeValid = Vec(Reg(Bool()) init (False), storeDepth)
  val storePayload = Vec(
    Reg(MatVecTileCommand(config)) init (MatVecTileCommand(config).getZero),
    storeDepth
  )
  val freeMask = Bits(storeDepth bits)
  val duplicateMask = Bits(storeDepth bits)
  for (slot <- 0 until storeDepth) {
    freeMask(slot) := !storeValid(slot)
    duplicateMask(slot) :=
      storeValid(slot) &&
        storePayload(slot).job.jobId === io.command.payload.job.jobId
  }
  val freeAvailable = freeMask.orR
  val freeIndex = OHToUInt(OHMasking.first(freeMask)).resize(log2Up(storeDepth))

  scheduler.io.input.valid := io.command.valid && freeAvailable
  scheduler.io.input.payload := io.command.payload.job
  io.command.ready := scheduler.io.input.ready && freeAvailable
  when(io.command.fire) {
    assert(!duplicateMask.orR)
    storeValid(freeIndex) := True
    storePayload(freeIndex) := io.command.payload
  }

  io.victimQueue := 0
  io.dispatchTarget := 0
  io.eligible := False
  io.age := 0
  io.localityScore := 0
  io.stealEvent := False
  io.dispatchJobId := 0

  for (cluster <- 0 until clusterCount) {
    val matchMask = Bits(storeDepth bits)
    for (slot <- 0 until storeDepth) {
      matchMask(slot) :=
        storeValid(slot) &&
          storePayload(slot).job.jobId ===
            scheduler.io.dispatch(cluster).payload.job.jobId
    }
    val matchAvailable = matchMask.orR
    val selectedCommand = MuxOH(matchMask, storePayload)
    clusters.io.commands(cluster).valid :=
      scheduler.io.dispatch(cluster).valid &&
        matchAvailable &&
        io.clusterEnable(cluster)
    clusters.io.commands(cluster).payload := selectedCommand
    scheduler.io.dispatch(cluster).ready :=
      clusters.io.commands(cluster).ready &&
        matchAvailable &&
        io.clusterEnable(cluster)

    when(scheduler.io.dispatch(cluster).valid) {
      io.eligible := scheduler.io.dispatch(cluster).payload.stolen
      io.victimQueue := scheduler.io.dispatch(cluster).payload.sourceCluster
      io.dispatchTarget := cluster
      io.age :=
        io.now -
          scheduler.io.dispatch(cluster).payload.job.arrivalTimestamp
      io.localityScore :=
        scheduler.io.dispatch(cluster).payload.localityScore
      io.dispatchJobId :=
        scheduler.io.dispatch(cluster).payload.job.jobId
    }
    when(scheduler.io.dispatch(cluster).fire) {
      io.stealEvent := scheduler.io.dispatch(cluster).payload.stolen
    }

    when(clusters.io.commands(cluster).fire) {
      assert(CountOne(matchMask) === 1)
      for (slot <- 0 until storeDepth) {
        when(matchMask(slot)) {
          storeValid(slot) := False
        }
      }
    }

    io.results(cluster) << clusters.io.results(cluster)
    io.queueOccupancy(cluster) :=
      scheduler.io.localQueueOccupancy(cluster)
    io.matVecActive(cluster) := clusters.io.matVecActive(cluster)
    io.matVecStart(cluster) := clusters.io.matVecStart(cluster)
    io.matVecResult(cluster) := clusters.io.matVecResult(cluster)
  }

  io.acceptedJobs := scheduler.io.acceptedJobs
  io.dispatchedJobs := scheduler.io.dispatchedJobs
  io.successfulSteals := scheduler.io.successfulSteals

  val storedCount = CountOne(storeValid.asBits)
  when(!ClockDomain.current.isResetActive) {
    assert(scheduler.io.liveJobs === storedCount.resized)
  }
}
