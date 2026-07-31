package varp

import org.scalatest.funsuite.AnyFunSuite
import spinal.core.sim._
import varp.memory.{BankAwareChannelScheduler, MultiChannelMemoryIngress}

class MultiChannelMemorySchedulerSpec extends AnyFunSuite {
  private def driveRequest(
      dut: MultiChannelMemoryIngress,
      job: Int,
      tile: Int
  ): Unit = {
    dut.io.request.payload.jobId #= job
    dut.io.request.payload.arrivalTimestamp #= job
    dut.io.request.payload.addressBytes #= job * 128
    dut.io.request.payload.lengthBytes #= 128
    dut.io.request.payload.outputTile #= tile
    dut.io.request.payload.preferredChannel #= tile & 3
    dut.io.request.payload.bank #= tile & 7
    dut.io.request.payload.row #= job
    dut.io.request.valid #= true
    while (!dut.io.request.ready.toBoolean) dut.clockDomain.waitSampling()
    dut.clockDomain.waitSampling()
    dut.io.request.valid #= false
  }

  test("output-tile affinity feeds four independent queues") {
    SimConfig
      .compile(new MultiChannelMemoryIngress(4, 4, "output_tile_affine"))
      .doSim(seed = 23) { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.io.request.valid #= false
        for (channel <- 0 until 4) dut.io.channelRequests(channel).ready #= false
        dut.clockDomain.waitSampling()
        for (tile <- 0 until 4) driveRequest(dut, tile + 1, tile)
        dut.clockDomain.waitSampling()
        sleep(1)
        for (channel <- 0 until 4) {
          assert(dut.io.occupancy(channel).toBigInt == 1)
          assert(dut.io.channelRequests(channel).payload.outputTile.toBigInt == channel)
        }
      }
  }

  test("row hit wins before the explicit age cap") {
    SimConfig
      .compile(new BankAwareChannelScheduler(4, depth = 4, bankCount = 8, ageCap = 16))
      .doSim(seed = 29) { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.io.request.valid #= false
        dut.io.command.ready #= false
        dut.clockDomain.waitSampling()

        def enqueue(job: Int, row: Int): Unit = {
          dut.io.request.payload.jobId #= job
          dut.io.request.payload.arrivalTimestamp #= job
          dut.io.request.payload.addressBytes #= job * 128
          dut.io.request.payload.lengthBytes #= 128
          dut.io.request.payload.outputTile #= job
          dut.io.request.payload.preferredChannel #= 0
          dut.io.request.payload.bank #= 0
          dut.io.request.payload.row #= row
          dut.io.request.valid #= true
          while (!dut.io.request.ready.toBoolean) dut.clockDomain.waitSampling()
          dut.clockDomain.waitSampling()
          dut.io.request.valid #= false
        }

        enqueue(1, 7)
        dut.io.command.ready #= true
        dut.clockDomain.waitSampling()
        dut.io.command.ready #= false
        dut.clockDomain.waitSampling()

        enqueue(2, 9)
        enqueue(3, 7)
        dut.io.command.ready #= true
        dut.clockDomain.waitSampling()
        assert(dut.io.command.payload.jobId.toBigInt == 3)
        dut.io.command.ready #= false
        dut.clockDomain.waitSampling()
        assert(dut.io.rowHitSelections.toBigInt == 1)
      }
  }
}
