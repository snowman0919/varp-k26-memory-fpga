package varp.k26

import spinal.core._
import spinal.lib._
import varp.compute._
import varp.link._
import varp.memory._
import varp.scheduler._

/** Paper-target integration shell for the K26--memory-FPGA virtual prototype.
  *
  * The command stream contains the concrete activation and weight tile used by
  * the imported 16x4 INT8 MatVec.  TileScheduler owns placement and stealing;
  * the associative command store keeps the corresponding data payload until
  * the selected ComputeCluster accepts it.  The memory-channel and link-bundle
  * planes remain explicit streams because physical DDR PHYs and GT wrappers
  * are board/tool generated boundaries, not portable RTL.
  */
class K26WorkStealingTop(
    val clusterCount: Int = 4,
    val channelCount: Int = 4,
    val bundleCount: Int = 4,
    val policy: Int = SchedulerPolicy.S3LocalityAware,
    val commandStoreDepth: Int = 32,
    config: TileJobConfig = TileJobConfig()
) extends Component {
  require(Set(1, 2, 4).contains(clusterCount))
  require(Set(1, 2, 4).contains(channelCount))
  require(Set(1, 2, 4).contains(bundleCount))
  require(commandStoreDepth >= clusterCount * 2)

  val io = new Bundle {
    val now = in UInt (config.timestampWidth bits)
    val command = slave Stream (MatVecTileCommand(config))
    val results =
      Vec(master(Stream(MatVecTileResult(config))), clusterCount)

    val clusterChannel =
      in Vec (UInt(config.channelWidth bits), clusterCount)
    val clusterLinkBundle =
      in Vec (UInt(config.bundleWidth bits), clusterCount)
    val activationResident = in Vec (Bool(), clusterCount)
    val residentActivationId =
      in Vec (UInt(config.activationIdWidth bits), clusterCount)

    val memoryRequest =
      slave Stream (MemoryTileRequest(channelCount))
    val memoryCommands =
      Vec(master(Stream(MemoryTileRequest(channelCount))), channelCount)

    val linkInput = slave Stream (BundleRoutedPacket(bundleCount))
    val linkBundles =
      Vec(master(Stream(LinkPacket())), bundleCount)

    val acceptedJobs = out UInt (64 bits)
    val dispatchedJobs = out UInt (64 bits)
    val successfulSteals = out UInt (64 bits)
    val completedJobs = out Vec (UInt(64 bits), clusterCount)
    val clusterBusyCycles = out Vec (UInt(64 bits), clusterCount)
    val clusterIdleCycles = out Vec (UInt(64 bits), clusterCount)
    val bundleAssignments = out Vec (UInt(64 bits), bundleCount)
    val bundleReroutes = out UInt (64 bits)
  }

  val scheduler =
    new TileScheduler(
      clusterCount = clusterCount,
      policy = policy,
      config = config,
      queueDepth = 8
    )
  val clusters =
    new ComputeClusterArray(
      clusterCount = clusterCount,
      config = config,
      queueDepth = 4,
      outputDepth = 2
    )

  scheduler.io.now := io.now
  scheduler.io.clusterChannel := io.clusterChannel
  scheduler.io.clusterLinkBundle := io.clusterLinkBundle
  scheduler.io.activationResident := io.activationResident
  scheduler.io.residentActivationId := io.residentActivationId

  val storeValid =
    Vec(Reg(Bool()) init (False), commandStoreDepth)
  val storePayload =
    Vec(
      Reg(MatVecTileCommand(config)) init (MatVecTileCommand(config).getZero),
      commandStoreDepth
    )
  val freeMask = Bits(commandStoreDepth bits)
  val duplicateMask = Bits(commandStoreDepth bits)
  for (slot <- 0 until commandStoreDepth) {
    freeMask(slot) := !storeValid(slot)
    duplicateMask(slot) :=
      storeValid(slot) &&
        storePayload(slot).job.jobId === io.command.payload.job.jobId
  }
  val freeAvailable = freeMask.orR
  val freeIndex =
    OHToUInt(OHMasking.first(freeMask))
      .resize(scala.math.max(1, log2Up(commandStoreDepth)))

  scheduler.io.input.valid := io.command.valid && freeAvailable
  scheduler.io.input.payload := io.command.payload.job
  io.command.ready := scheduler.io.input.ready && freeAvailable

  when(io.command.fire) {
    assert(!duplicateMask.orR)
    storeValid(freeIndex) := True
    storePayload(freeIndex) := io.command.payload
  }

  for (cluster <- 0 until clusterCount) {
    val matchMask = Bits(commandStoreDepth bits)
    for (slot <- 0 until commandStoreDepth) {
      matchMask(slot) :=
        storeValid(slot) &&
          storePayload(slot).job.jobId ===
            scheduler.io.dispatch(cluster).payload.job.jobId
    }
    val matchAvailable = matchMask.orR
    val selectedCommand = MuxOH(matchMask, storePayload)

    clusters.io.commands(cluster).valid :=
      scheduler.io.dispatch(cluster).valid && matchAvailable
    clusters.io.commands(cluster).payload := selectedCommand
    scheduler.io.dispatch(cluster).ready :=
      clusters.io.commands(cluster).ready && matchAvailable

    when(clusters.io.commands(cluster).fire) {
      assert(CountOne(matchMask) === 1)
      assert(
        selectedCommand.job.jobId ===
          scheduler.io.dispatch(cluster).payload.job.jobId
      )
      for (slot <- 0 until commandStoreDepth) {
        when(matchMask(slot)) {
          storeValid(slot) := False
        }
      }
    }

    io.results(cluster) << clusters.io.results(cluster)
    io.completedJobs(cluster) := clusters.io.completedJobs(cluster)
    io.clusterBusyCycles(cluster) := clusters.io.busyCycles(cluster)
    io.clusterIdleCycles(cluster) := clusters.io.idleCycles(cluster)
  }

  val memoryIngress =
    new MultiChannelMemoryIngress(
      channelCount = channelCount,
      queueDepth = 8,
      mappingMode = "bank_aware"
    )
  memoryIngress.io.request << io.memoryRequest
  for (channel <- 0 until channelCount) {
    val channelScheduler =
      new BankAwareChannelScheduler(
        channelCount = channelCount,
        depth = 4,
        policy = "row_hit_with_age_cap",
        ageCap = 32
      )
    channelScheduler.io.request << memoryIngress.io.channelRequests(channel)
    io.memoryCommands(channel) << channelScheduler.io.command
  }

  val bundleRouter = new BundleRouter(bundleCount)
  bundleRouter.io.input << io.linkInput
  for (bundle <- 0 until bundleCount) {
    io.linkBundles(bundle) << bundleRouter.io.bundles(bundle)
  }

  io.acceptedJobs := scheduler.io.acceptedJobs
  io.dispatchedJobs := scheduler.io.dispatchedJobs
  io.successfulSteals := scheduler.io.successfulSteals
  io.bundleAssignments := bundleRouter.io.assignments
  io.bundleReroutes := bundleRouter.io.reroutes

  val storedCount = CountOne(storeValid.asBits)
  when(!ClockDomain.current.isResetActive) {
    assert(storedCount <= commandStoreDepth)
    assert(scheduler.io.liveJobs === storedCount.resized)
  }
}

object GenerateK26WorkStealingTop {
  def main(args: Array[String]): Unit = {
    val target = if (args.nonEmpty) args(0) else "build/k26-rtl"
    SpinalConfig(
      targetDirectory = target,
      headerWithRepoHash = false
    ).generateVerilog(
      new K26WorkStealingTop()
    )
  }
}
