package varp.link

import spinal.core._
import spinal.lib._

case class BundleRoutedPacket(bundleCount: Int) extends Bundle {
  private val bundleWidth = scala.math.max(1, log2Up(bundleCount))
  val packet = LinkPacket()
  val sourceCluster = UInt(2 bits)
  val preferredBundle = UInt(bundleWidth bits)
  val stolen = Bool()
  val rerouteAllowed = Bool()
}

/**
  * Job/cluster-affine logical router.
  *
  * The preferred bundle is retained whenever it can accept the packet. A
  * work-steal-aware packet may use the first available alternative only when
  * rerouteAllowed is asserted. Packet serialization, credit FIFOs, GT wrappers,
  * and a receive path are external/unimplemented boundaries.
  */
class BundleRouter(bundleCount: Int) extends Component {
  require(Set(1, 2, 4).contains(bundleCount))
  private val bundleWidth = scala.math.max(1, log2Up(bundleCount))

  val io = new Bundle {
    val input = slave Stream (BundleRoutedPacket(bundleCount))
    val bundles = Vec(master Stream (LinkPacket()), bundleCount)
    val assignments = out Vec (UInt(64 bits), bundleCount)
    val reroutes = out UInt (64 bits)
    val bundleContentionWait = out UInt (64 bits)
  }

  val assignmentCounts = Vec(Reg(UInt(64 bits)) init (0), bundleCount)
  val rerouteCount = Reg(UInt(64 bits)) init (0)
  val contentionWait = Reg(UInt(64 bits)) init (0)

  val selected = UInt(bundleWidth bits)
  val selectedValid = Bool()
  val preferredReady = Bool()
  selected := io.input.payload.preferredBundle
  selectedValid := False
  preferredReady := False

  for (bundle <- 0 until bundleCount) {
    when(io.input.payload.preferredBundle === bundle) {
      preferredReady := io.bundles(bundle).ready
      when(io.bundles(bundle).ready) {
        selected := bundle
        selectedValid := True
      }
    }
  }

  val fallbackReady = Bits(bundleCount bits)
  for (bundle <- 0 until bundleCount) {
    fallbackReady(bundle) := io.bundles(bundle).ready
  }
  val fallbackOH = OHMasking.first(fallbackReady)
  when(
    io.input.valid &&
      io.input.payload.rerouteAllowed &&
      !preferredReady &&
      fallbackReady.orR
  ) {
    selected := OHToUInt(fallbackOH).resize(bundleWidth)
    selectedValid := True
  }

  for (bundle <- 0 until bundleCount) {
    io.bundles(bundle).valid :=
      io.input.valid && selectedValid && selected === bundle
    io.bundles(bundle).payload := io.input.payload.packet
  }
  io.input.ready := selectedValid

  when(io.input.valid && !io.input.ready) {
    contentionWait := contentionWait + 1
  }
  when(io.input.fire) {
    for (bundle <- 0 until bundleCount) {
      when(selected === bundle) {
        assignmentCounts(bundle) := assignmentCounts(bundle) + 1
      }
    }
    when(selected =/= io.input.payload.preferredBundle) {
      rerouteCount := rerouteCount + 1
      assert(io.input.payload.rerouteAllowed)
    }
  }

  io.assignments := assignmentCounts
  io.reroutes := rerouteCount
  io.bundleContentionWait := contentionWait
}

/**
  * Exclusive wait-cause accounting.
  *
  * Several raw conditions may overlap on a cycle. The documented priority
  * below assigns every blocked cycle to exactly one counter, while overlapCycles
  * reports that multiple raw causes were simultaneously true.
  */
class LinkWaitCounterBank extends Component {
  val io = new Bundle {
    val blocked = in Bool ()
    val requestSerializerBlocked = in Bool ()
    val requestCreditBlocked = in Bool ()
    val requestCdcBlocked = in Bool ()
    val outstandingTableFull = in Bool ()
    val responseSerializerBlocked = in Bool ()
    val responseCdcBlocked = in Bool ()
    val consumerFifoFull = in Bool ()
    val bundleContention = in Bool ()

    val requestSerializerWait = out UInt (64 bits)
    val requestCreditWait = out UInt (64 bits)
    val requestCdcWait = out UInt (64 bits)
    val outstandingTableFullWait = out UInt (64 bits)
    val responseSerializerWait = out UInt (64 bits)
    val responseCdcWait = out UInt (64 bits)
    val consumerFifoFullWait = out UInt (64 bits)
    val bundleContentionWait = out UInt (64 bits)
    val totalBlockedCycles = out UInt (64 bits)
    val overlapCycles = out UInt (64 bits)
    val unattributedCycles = out UInt (64 bits)
  }

  val counters = Vec(Reg(UInt(64 bits)) init (0), 8)
  val total = Reg(UInt(64 bits)) init (0)
  val overlaps = Reg(UInt(64 bits)) init (0)
  val unattributed = Reg(UInt(64 bits)) init (0)
  val causes = Bits(8 bits)
  causes(0) := io.requestSerializerBlocked
  causes(1) := io.requestCreditBlocked
  causes(2) := io.requestCdcBlocked
  causes(3) := io.outstandingTableFull
  causes(4) := io.responseSerializerBlocked
  causes(5) := io.responseCdcBlocked
  causes(6) := io.consumerFifoFull
  causes(7) := io.bundleContention

  when(io.blocked) {
    total := total + 1
    when(CountOne(causes) > 1) {
      overlaps := overlaps + 1
    }
    when(io.outstandingTableFull) {
      counters(3) := counters(3) + 1
    } elsewhen (io.requestCreditBlocked) {
      counters(1) := counters(1) + 1
    } elsewhen (io.requestSerializerBlocked) {
      counters(0) := counters(0) + 1
    } elsewhen (io.requestCdcBlocked) {
      counters(2) := counters(2) + 1
    } elsewhen (io.consumerFifoFull) {
      counters(6) := counters(6) + 1
    } elsewhen (io.responseSerializerBlocked) {
      counters(4) := counters(4) + 1
    } elsewhen (io.responseCdcBlocked) {
      counters(5) := counters(5) + 1
    } elsewhen (io.bundleContention) {
      counters(7) := counters(7) + 1
    } otherwise {
      unattributed := unattributed + 1
    }
  }

  io.requestSerializerWait := counters(0)
  io.requestCreditWait := counters(1)
  io.requestCdcWait := counters(2)
  io.outstandingTableFullWait := counters(3)
  io.responseSerializerWait := counters(4)
  io.responseCdcWait := counters(5)
  io.consumerFifoFullWait := counters(6)
  io.bundleContentionWait := counters(7)
  io.totalBlockedCycles := total
  io.overlapCycles := overlaps
  io.unattributedCycles := unattributed
}
