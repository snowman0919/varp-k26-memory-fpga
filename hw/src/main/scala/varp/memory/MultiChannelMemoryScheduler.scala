package varp.memory

import spinal.core._
import spinal.lib._

case class MemoryTileRequest(channelCount: Int) extends Bundle {
  private val channelWidth = scala.math.max(1, log2Up(channelCount))
  val jobId = UInt(32 bits)
  val arrivalTimestamp = UInt(32 bits)
  val addressBytes = UInt(64 bits)
  val lengthBytes = UInt(32 bits)
  val outputTile = UInt(16 bits)
  val preferredChannel = UInt(channelWidth bits)
  val bank = UInt(4 bits)
  val row = UInt(16 bits)
}

/**
  * Address mapping followed by an independent ingress FIFO per DDR channel.
  */
class MultiChannelMemoryIngress(
    channelCount: Int,
    queueDepth: Int,
    mappingMode: String
) extends Component {
  require(Set(1, 2, 4).contains(channelCount))
  require(queueDepth >= 2)
  require(
    Set("linear", "burst_interleaved", "output_tile_affine", "bank_aware")
      .contains(mappingMode)
  )
  private val channelWidth = scala.math.max(1, log2Up(channelCount))

  val io = new Bundle {
    val request = slave Stream (MemoryTileRequest(channelCount))
    val channelRequests =
      Vec(master Stream (MemoryTileRequest(channelCount)), channelCount)
    val occupancy =
      out Vec (UInt(log2Up(queueDepth + 1) bits), channelCount)
  }

  val mappedChannel = UInt(channelWidth bits)
  if (channelCount == 1) {
    mappedChannel := 0
  } else {
    mappingMode match {
      case "linear" =>
        mappedChannel := io.request.payload.addressBytes(
          channelWidth - 1 downto 0
        )
      case "burst_interleaved" =>
        mappedChannel := (io.request.payload.addressBytes >> 7)(
          channelWidth - 1 downto 0
        )
      case "output_tile_affine" =>
        mappedChannel := io.request.payload.outputTile(
          channelWidth - 1 downto 0
        )
      case "bank_aware" =>
        mappedChannel := io.request.payload.preferredChannel
    }
  }

  val queues =
    Array.fill(channelCount)(StreamFifo(MemoryTileRequest(channelCount), queueDepth))
  val readyByChannel = Vec(Bool(), channelCount)
  for (channel <- 0 until channelCount) {
    queues(channel).io.push.valid :=
      io.request.valid && mappedChannel === channel
    queues(channel).io.push.payload := io.request.payload
    readyByChannel(channel) := queues(channel).io.push.ready
    io.channelRequests(channel) << queues(channel).io.pop
    io.occupancy(channel) := queues(channel).io.occupancy
  }
  if (channelCount == 1) {
    io.request.ready := readyByChannel(0)
  } else {
    io.request.ready := readyByChannel(mappedChannel)
  }
}

/**
  * Small per-channel request window with FCFS, oldest-ready, or row-hit policy.
  *
  * row_hit_with_age_cap selects a current open-row hit unless any request has
  * reached ageCap. The cap prevents starvation and exposes the tradeoff as a
  * configuration parameter rather than a hidden optimum.
  */
class BankAwareChannelScheduler(
    channelCount: Int,
    depth: Int = 4,
    bankCount: Int = 8,
    policy: String = "row_hit_with_age_cap",
    ageCap: Int = 32
) extends Component {
  require(Set(1, 2, 4).contains(channelCount))
  require(depth >= 2)
  require(bankCount >= 1 && bankCount <= 16)
  require(Set("fcfs", "oldest_ready", "row_hit_with_age_cap").contains(policy))
  require(ageCap >= 1)

  val io = new Bundle {
    val request = slave Stream (MemoryTileRequest(channelCount))
    val command = master Stream (MemoryTileRequest(channelCount))
    val occupancy = out UInt (log2Up(depth + 1) bits)
    val rowHitSelections = out UInt (64 bits)
    val ageCapSelections = out UInt (64 bits)
  }

  val valid = Vec(Reg(Bool()) init (False), depth)
  val requests =
    Vec(Reg(MemoryTileRequest(channelCount)) init (MemoryTileRequest(channelCount).getZero), depth)
  val ages = Vec(Reg(UInt(32 bits)) init (0), depth)
  val openRowValid = Vec(Reg(Bool()) init (False), bankCount)
  val openRows = Vec(Reg(UInt(16 bits)) init (0), bankCount)
  val rowHitCount = Reg(UInt(64 bits)) init (0)
  val ageCapCount = Reg(UInt(64 bits)) init (0)

  val validBits = valid.asBits
  val freeOH = OHMasking.first(~validBits)
  io.request.ready := !validBits.andR

  when(io.request.fire) {
    for (slot <- 0 until depth) {
      when(freeOH(slot)) {
        valid(slot) := True
        requests(slot) := io.request.payload
        ages(slot) := 0
      }
    }
  }

  val rowHitMask = Bits(depth bits)
  val urgentMask = Bits(depth bits)
  for (slot <- 0 until depth) {
    val bank = requests(slot).bank(log2Up(bankCount) - 1 downto 0)
    rowHitMask(slot) :=
      valid(slot) && openRowValid(bank) && openRows(bank) === requests(slot).row
    urgentMask(slot) := valid(slot) && ages(slot) >= ageCap
  }

  def oldestOneHot(mask: Bits): Bits = {
    var found: Bool = False
    var bestAge: UInt = U(0, 32 bits)
    var best: Bits = B(0, depth bits)
    for (slot <- 0 until depth) {
      val take = mask(slot) && (!found || ages(slot) > bestAge)
      best = Mux(take, B(BigInt(1) << slot, depth bits), best)
      bestAge = Mux(take, ages(slot), bestAge)
      found = found || mask(slot)
    }
    best
  }

  val selectedOH = Bits(depth bits)
  val selectedByRowHit = Bool()
  val selectedByAgeCap = Bool()
  selectedByRowHit := False
  selectedByAgeCap := False
  if (policy == "row_hit_with_age_cap") {
    when(urgentMask.orR) {
      selectedOH := oldestOneHot(urgentMask)
      selectedByAgeCap := True
    } elsewhen (rowHitMask.orR) {
      selectedOH := oldestOneHot(rowHitMask)
      selectedByRowHit := True
    } otherwise {
      selectedOH := oldestOneHot(validBits)
    }
  } else {
    selectedOH := oldestOneHot(validBits)
  }

  io.command.valid := selectedOH.orR
  io.command.payload := MuxOH(selectedOH, requests)

  for (slot <- 0 until depth) {
    when(valid(slot) && !(io.command.fire && selectedOH(slot))) {
      ages(slot) := ages(slot) + 1
    }
    when(io.command.fire && selectedOH(slot)) {
      valid(slot) := False
      ages(slot) := 0
    }
  }
  when(io.command.fire) {
    val bank = io.command.payload.bank(log2Up(bankCount) - 1 downto 0)
    openRowValid(bank) := True
    openRows(bank) := io.command.payload.row
    when(selectedByRowHit) {
      rowHitCount := rowHitCount + 1
    }
    when(selectedByAgeCap) {
      ageCapCount := ageCapCount + 1
    }
  }

  io.occupancy := CountOne(validBits).resize(log2Up(depth + 1))
  io.rowHitSelections := rowHitCount
  io.ageCapSelections := ageCapCount
}
