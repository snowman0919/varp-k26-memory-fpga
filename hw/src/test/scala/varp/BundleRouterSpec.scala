package varp

import org.scalatest.funsuite.AnyFunSuite
import spinal.core.sim._
import varp.link.{BundleRouter, LinkWaitCounterBank}

class BundleRouterSpec extends AnyFunSuite {
  test("preferred bundle is retained and eligible stalled work may reroute") {
    SimConfig.compile(new BundleRouter(4)).doSim(seed = 17) { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.input.valid #= false
      for (bundle <- 0 until 4) dut.io.bundles(bundle).ready #= false
      dut.clockDomain.waitSampling()

      dut.io.input.payload.preferredBundle #= 2
      dut.io.input.payload.sourceCluster #= 2
      dut.io.input.payload.stolen #= false
      dut.io.input.payload.rerouteAllowed #= true
      dut.io.input.payload.packet.record #= 0x1234
      dut.io.input.payload.packet.epoch #= 1
      dut.io.input.payload.packet.transportOrdinal #= 7
      dut.io.input.payload.packet.payloadBytes #= 16
      dut.io.input.payload.packet.crcBad #= false
      dut.io.input.payload.packet.wireBytes #= 64
      dut.io.input.valid #= true

      dut.io.bundles(2).ready #= true
      dut.clockDomain.waitSampling()
      dut.io.input.valid #= false
      dut.clockDomain.waitSampling()
      assert(dut.io.assignments(2).toBigInt == 1)
      assert(dut.io.reroutes.toBigInt == 0)

      dut.io.bundles(2).ready #= false
      dut.io.bundles(1).ready #= true
      dut.io.input.valid #= true
      dut.clockDomain.waitSampling()
      dut.io.input.valid #= false
      dut.clockDomain.waitSampling()
      assert(dut.io.assignments(1).toBigInt == 1)
      assert(dut.io.reroutes.toBigInt == 1)

      dut.io.input.valid #= true
      for (bundle <- 0 until 4) dut.io.bundles(bundle).ready #= false
      dut.clockDomain.waitSampling(3)
      dut.io.input.valid #= false
      dut.clockDomain.waitSampling()
      assert(dut.io.bundleContentionWait.toBigInt == 3)
    }
  }

  test("wait accounting is exclusive and reports overlaps") {
    SimConfig.compile(new LinkWaitCounterBank).doSim(seed = 19) { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.blocked #= false
      dut.io.requestSerializerBlocked #= false
      dut.io.requestCreditBlocked #= false
      dut.io.requestCdcBlocked #= false
      dut.io.outstandingTableFull #= false
      dut.io.responseSerializerBlocked #= false
      dut.io.responseCdcBlocked #= false
      dut.io.consumerFifoFull #= false
      dut.io.bundleContention #= false
      dut.clockDomain.waitSampling()

      dut.io.blocked #= true
      dut.io.requestSerializerBlocked #= true
      dut.clockDomain.waitSampling()
      dut.io.requestCreditBlocked #= true
      dut.clockDomain.waitSampling()
      dut.io.outstandingTableFull #= true
      dut.clockDomain.waitSampling()
      dut.io.blocked #= false
      dut.clockDomain.waitSampling()

      assert(dut.io.totalBlockedCycles.toBigInt == 3)
      assert(dut.io.requestSerializerWait.toBigInt == 1)
      assert(dut.io.requestCreditWait.toBigInt == 1)
      assert(dut.io.outstandingTableFullWait.toBigInt == 1)
      assert(dut.io.overlapCycles.toBigInt == 2)
      assert(dut.io.unattributedCycles.toBigInt == 0)
    }
  }
}
