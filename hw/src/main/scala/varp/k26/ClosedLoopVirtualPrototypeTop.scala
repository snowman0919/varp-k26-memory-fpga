package varp.k26

import spinal.core._
import spinal.lib._
import varp.compute._
import varp.memory._
import varp.scheduler.SchedulerPolicy

/** K26-side command before the external weight tile has returned. */
case class MatVecFetchCommand(config: TileJobConfig = TileJobConfig())
    extends Bundle {
  val job = TileJob(config)
  val activation = Vec(SInt(config.dataWidth bits), config.inputDim)
}

/** One complete weight-tile response from the logical DDR service boundary.
  *
  * The payload is deliberately wider than a physical GT beat. This top proves
  * ownership, backpressure, and exact payload identity across the closed
  * virtual-prototype path; a serializer, GT wrapper, CDC, and MIG remain
  * implementation gates.
  */
case class MemoryWeightResponse(
    channelCount: Int,
    config: TileJobConfig = TileJobConfig()
) extends Bundle {
  private val channelWidth = scala.math.max(1, log2Up(channelCount))
  val jobId = UInt(config.jobIdWidth bits)
  val channel = UInt(channelWidth bits)
  val responseOrdinal = UInt(32 bits)
  val crcBad = Bool()
  val weights =
    Vec(
      Vec(SInt(config.dataWidth bits), config.inputDim),
      config.outputDim
    )
}

/** Closed logical path for the K26--Memory-FPGA virtual prototype.
  *
  * Implemented path:
  *   fetch command -> DMA request -> channel scheduler -> DDR response input
  *   -> locality-selected logical link FIFO -> payload join -> scheduler
  *   -> MatVec result.
  *
  * `memoryResponse` is the DDR-controller/MIG boundary. The per-bundle FIFOs
  * are a logical receive transport with backpressure, not a physical GTH PHY.
  */
class ClosedLoopVirtualPrototypeTop(
    val clusterCount: Int = 4,
    val channelCount: Int = 4,
    val bundleCount: Int = 4,
    val policy: Int = SchedulerPolicy.S3LocalityAware,
    val pendingDepth: Int = 16,
    val linkFifoDepth: Int = 4,
    config: TileJobConfig = TileJobConfig()
) extends Component {
  require(Set(1, 2, 4).contains(clusterCount))
  require(Set(1, 2, 4).contains(channelCount))
  require(Set(1, 2, 4).contains(bundleCount))
  require(pendingDepth >= clusterCount * 2)
  require(linkFifoDepth >= 2)

  val io = new Bundle {
    val now = in UInt (config.timestampWidth bits)
    val fetchCommand = slave Stream (MatVecFetchCommand(config))
    val memoryCommands =
      Vec(master(Stream(MemoryTileRequest(channelCount))), channelCount)
    val memoryResponse =
      slave Stream (MemoryWeightResponse(channelCount, config))
    val results = Vec(master(Stream(MatVecTileResult(config))), clusterCount)

    val clusterChannel =
      in Vec (UInt(config.channelWidth bits), clusterCount)
    val clusterLinkBundle =
      in Vec (UInt(config.bundleWidth bits), clusterCount)
    val activationResident = in Vec (Bool(), clusterCount)
    val residentActivationId =
      in Vec (UInt(config.activationIdWidth bits), clusterCount)

    val dmaRequests = out UInt (64 bits)
    val weightResponses = out UInt (64 bits)
    val payloadsDispatched = out UInt (64 bits)
    val crcErrors = out UInt (64 bits)
    val pendingJobs = out UInt (log2Up(pendingDepth + 1) bits)
    val successfulSteals = out UInt (64 bits)
    val completedJobs = out Vec (UInt(64 bits), clusterCount)
  }

  val pendingValid = Vec(Reg(Bool()) init (False), pendingDepth)
  val pendingResponseAccepted =
    Vec(Reg(Bool()) init (False), pendingDepth)
  val pendingCommand =
    Vec(
      Reg(MatVecFetchCommand(config)) init (MatVecFetchCommand(config).getZero),
      pendingDepth
    )
  val pendingBits = pendingValid.asBits
  val freeMask = ~pendingBits
  val freeAvailable = freeMask.orR
  val freeIndex =
    OHToUInt(OHMasking.first(freeMask))
      .resize(scala.math.max(1, log2Up(pendingDepth)))

  val dmaIngress =
    StreamFifo(MemoryTileRequest(channelCount), pendingDepth)
  dmaIngress.io.push.valid := io.fetchCommand.valid && freeAvailable
  dmaIngress.io.push.payload.jobId := io.fetchCommand.payload.job.jobId
  dmaIngress.io.push.payload.arrivalTimestamp :=
    io.fetchCommand.payload.job.arrivalTimestamp.resized
  dmaIngress.io.push.payload.addressBytes :=
    io.fetchCommand.payload.job.weightBase
  dmaIngress.io.push.payload.lengthBytes :=
    config.inputDim * config.outputDim * (config.dataWidth / 8)
  dmaIngress.io.push.payload.outputTile :=
    io.fetchCommand.payload.job.nStart.resized
  dmaIngress.io.push.payload.preferredChannel :=
    io.fetchCommand.payload.job.preferredChannel.resized
  dmaIngress.io.push.payload.bank :=
    (io.fetchCommand.payload.job.weightBase >> 7).resized
  dmaIngress.io.push.payload.row :=
    (io.fetchCommand.payload.job.weightBase >> 13).resized
  io.fetchCommand.ready := dmaIngress.io.push.ready && freeAvailable

  when(io.fetchCommand.fire) {
    for (slot <- 0 until pendingDepth) {
      when(
        pendingValid(slot) &&
          pendingCommand(slot).job.jobId === io.fetchCommand.payload.job.jobId
      ) {
        assert(False, "duplicate live jobId")
      }
    }
    pendingValid(freeIndex) := True
    pendingResponseAccepted(freeIndex) := False
    pendingCommand(freeIndex) := io.fetchCommand.payload
  }

  val memoryIngress =
    new MultiChannelMemoryIngress(
      channelCount = channelCount,
      queueDepth = 8,
      mappingMode = "bank_aware"
    )
  memoryIngress.io.request << dmaIngress.io.pop
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

  val responseMatchMask = Bits(pendingDepth bits)
  for (slot <- 0 until pendingDepth) {
    responseMatchMask(slot) :=
      pendingValid(slot) &&
        !pendingResponseAccepted(slot) &&
        pendingCommand(slot).job.jobId === io.memoryResponse.payload.jobId
  }
  val responseMatched = responseMatchMask.orR
  val matchedPending = MuxOH(responseMatchMask, pendingCommand)
  val responseBundle = matchedPending.job.preferredLinkBundle.resized

  val linkFifos =
    Array.fill(bundleCount)(
      StreamFifo(MemoryWeightResponse(channelCount, config), linkFifoDepth)
    )
  val selectedBundleReady = Vec(Bool(), bundleCount)
  for (bundle <- 0 until bundleCount) {
    linkFifos(bundle).io.push.valid :=
      io.memoryResponse.valid && responseMatched && responseBundle === bundle
    linkFifos(bundle).io.push.payload := io.memoryResponse.payload
    selectedBundleReady(bundle) := linkFifos(bundle).io.push.ready
  }
  io.memoryResponse.ready :=
    responseMatched && selectedBundleReady(responseBundle)
  when(io.memoryResponse.fire) {
    assert(responseMatched, "DDR response must match one outstanding job")
    assert(CountOne(responseMatchMask) === 1)
    for (slot <- 0 until pendingDepth) {
      when(responseMatchMask(slot)) {
        pendingResponseAccepted(slot) := True
      }
    }
  }

  val linkValidBits = Bits(bundleCount bits)
  for (bundle <- 0 until bundleCount) {
    linkValidBits(bundle) := linkFifos(bundle).io.pop.valid
  }
  val linkSelectedOH = OHMasking.first(linkValidBits)
  val linkOutput = Stream(MemoryWeightResponse(channelCount, config))
  linkOutput.valid := linkValidBits.orR
  linkOutput.payload :=
    MuxOH(linkSelectedOH, linkFifos.map(_.io.pop.payload).toSeq)
  for (bundle <- 0 until bundleCount) {
    linkFifos(bundle).io.pop.ready :=
      linkOutput.ready && linkSelectedOH(bundle)
  }

  val joinedMatchMask = Bits(pendingDepth bits)
  for (slot <- 0 until pendingDepth) {
    joinedMatchMask(slot) :=
      pendingValid(slot) &&
        pendingCommand(slot).job.jobId === linkOutput.payload.jobId
  }
  val joinedMatched = joinedMatchMask.orR
  val joinedPending = MuxOH(joinedMatchMask, pendingCommand)

  val computeTop =
    new K26WorkStealingTop(
      clusterCount = clusterCount,
      channelCount = channelCount,
      bundleCount = bundleCount,
      policy = policy,
      commandStoreDepth = pendingDepth,
      config = config
    )
  computeTop.io.now := io.now
  computeTop.io.clusterChannel := io.clusterChannel
  computeTop.io.clusterLinkBundle := io.clusterLinkBundle
  computeTop.io.activationResident := io.activationResident
  computeTop.io.residentActivationId := io.residentActivationId
  computeTop.io.memoryRequest.valid := False
  computeTop.io.memoryRequest.payload.assignDontCare()
  computeTop.io.linkInput.valid := False
  computeTop.io.linkInput.payload.assignDontCare()
  for (channel <- 0 until channelCount) {
    computeTop.io.memoryCommands(channel).ready := True
  }
  for (bundle <- 0 until bundleCount) {
    computeTop.io.linkBundles(bundle).ready := True
  }

  computeTop.io.command.valid :=
    linkOutput.valid && joinedMatched && !linkOutput.payload.crcBad
  computeTop.io.command.payload.job := joinedPending.job
  computeTop.io.command.payload.activation := joinedPending.activation
  computeTop.io.command.payload.weights := linkOutput.payload.weights
  linkOutput.ready :=
    Mux(
      linkOutput.payload.crcBad,
      True,
      joinedMatched && computeTop.io.command.ready
    )
  when(linkOutput.valid) {
    assert(joinedMatched, "link payload must match one outstanding job")
    assert(CountOne(joinedMatchMask) === 1)
  }
  when(computeTop.io.command.fire) {
    for (slot <- 0 until pendingDepth) {
      when(joinedMatchMask(slot)) {
        pendingValid(slot) := False
        pendingResponseAccepted(slot) := False
      }
    }
  }

  for (cluster <- 0 until clusterCount) {
    io.results(cluster) << computeTop.io.results(cluster)
    io.completedJobs(cluster) := computeTop.io.completedJobs(cluster)
  }

  val dmaRequestCount = Reg(UInt(64 bits)) init (0)
  val weightResponseCount = Reg(UInt(64 bits)) init (0)
  val dispatchedPayloadCount = Reg(UInt(64 bits)) init (0)
  val crcErrorCount = Reg(UInt(64 bits)) init (0)
  when(io.memoryCommands.map(_.fire).reduce(_ || _)) {
    dmaRequestCount := dmaRequestCount + 1
  }
  when(io.memoryResponse.fire) {
    weightResponseCount := weightResponseCount + 1
  }
  when(computeTop.io.command.fire) {
    dispatchedPayloadCount := dispatchedPayloadCount + 1
  }
  when(linkOutput.fire && linkOutput.payload.crcBad) {
    crcErrorCount := crcErrorCount + 1
  }

  io.dmaRequests := dmaRequestCount
  io.weightResponses := weightResponseCount
  io.payloadsDispatched := dispatchedPayloadCount
  io.crcErrors := crcErrorCount
  io.pendingJobs := CountOne(pendingBits).resize(log2Up(pendingDepth + 1))
  io.successfulSteals := computeTop.io.successfulSteals

  when(!ClockDomain.current.isResetActive) {
    assert(CountOne(pendingBits) <= pendingDepth)
    assert(dispatchedPayloadCount <= weightResponseCount)
    // Registered counters may observe a command and its zero-latency response
    // on adjacent sampling edges. The quiescent test below checks equality.
    assert(weightResponseCount <= dmaRequestCount + 1)
  }
}

object GenerateClosedLoopVirtualPrototypeTop {
  def main(args: Array[String]): Unit = {
    val target = if (args.nonEmpty) args(0) else "build/closed-loop-rtl"
    SpinalConfig(
      targetDirectory = target,
      headerWithRepoHash = false
    ).generateVerilog(new ClosedLoopVirtualPrototypeTop())
  }
}
