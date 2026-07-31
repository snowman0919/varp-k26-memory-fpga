package varp.compute

import spinal.core._
import spinal.lib._

/** One concrete compute cluster with FCFS command and output buffering. */
class MatVecTileConsumer(
    config: TileJobConfig = TileJobConfig(),
    weightFifoDepth: Int = 4,
    outputFifoDepth: Int = 2
) extends Component {
  require(weightFifoDepth >= 2)
  require(outputFifoDepth >= 2)

  val io = new Bundle {
    val command = slave Stream (MatVecTileCommand(config))
    val result = master Stream (MatVecTileResult(config))
    val queueOccupancy = out UInt (log2Up(weightFifoDepth + 1) bits)
    val outputOccupancy = out UInt (log2Up(outputFifoDepth + 1) bits)
    val active = out Bool ()
    val computeCycles = out UInt (16 bits)
    val matVecActive = out Bool ()
    val matVecStart = out Bool ()
    val matVecResult = out Bool ()
  }

  val weightFifo =
    StreamFifo(MatVecTileCommand(config), weightFifoDepth)
  val outputBuffer =
    StreamFifo(MatVecTileResult(config), outputFifoDepth)
  val adapter = new LegacyMatVecAdapter(config)

  weightFifo.io.push << io.command
  adapter.io.command << weightFifo.io.pop
  outputBuffer.io.push << adapter.io.result
  io.result << outputBuffer.io.pop

  io.queueOccupancy := weightFifo.io.occupancy
  io.outputOccupancy := outputBuffer.io.occupancy
  io.active :=
    adapter.io.active || weightFifo.io.occupancy =/= 0 ||
      outputBuffer.io.occupancy =/= 0
  io.computeCycles := adapter.io.computeCycles
  io.matVecActive := adapter.io.active
  io.matVecStart := adapter.io.command.fire
  io.matVecResult := adapter.io.result.fire
}

class ComputeCluster(
    val clusterId: Int,
    val clusterCount: Int,
    config: TileJobConfig = TileJobConfig(),
    queueDepth: Int = 4,
    outputDepth: Int = 2
) extends Component {
  require(Set(1, 2, 4).contains(clusterCount))
  require(clusterId >= 0 && clusterId < clusterCount)

  val io = new Bundle {
    val command = slave Stream (MatVecTileCommand(config))
    val result = master Stream (MatVecTileResult(config))
    val acceptedJobs = out UInt (64 bits)
    val completedJobs = out UInt (64 bits)
    val busyCycles = out UInt (64 bits)
    val idleCycles = out UInt (64 bits)
    val queueOccupancy = out UInt (log2Up(queueDepth + 1) bits)
    val outputOccupancy = out UInt (log2Up(outputDepth + 1) bits)
    val matVecActive = out Bool ()
    val matVecStart = out Bool ()
    val matVecResult = out Bool ()
  }

  val consumer =
    new MatVecTileConsumer(config, queueDepth, outputDepth)
  consumer.io.command << io.command
  io.result << consumer.io.result

  val accepted = Reg(UInt(64 bits)) init (0)
  val completed = Reg(UInt(64 bits)) init (0)
  val busy = Reg(UInt(64 bits)) init (0)
  val idle = Reg(UInt(64 bits)) init (0)
  when(io.command.fire) {
    accepted := accepted + 1
  }
  when(io.result.fire) {
    completed := completed + 1
  }
  when(consumer.io.active) {
    busy := busy + 1
  } otherwise {
    idle := idle + 1
  }

  when(!ClockDomain.current.isResetActive) {
    assert(completed <= accepted)
    when(io.command.fire) {
      assert(io.command.payload.job.kStart === 0)
      assert(io.command.payload.job.kLength === config.inputDim)
      assert(io.command.payload.job.nLength > 0)
      assert(io.command.payload.job.nLength <= config.outputDim)
      if (clusterCount < (1 << config.ownerWidth)) {
        assert(io.command.payload.job.reductionOwner < clusterCount)
      }
    }
    when(io.result.fire) {
      assert(io.result.payload.job.kStart === 0)
      assert(io.result.payload.job.kLength === config.inputDim)
    }
  }

  io.acceptedJobs := accepted
  io.completedJobs := completed
  io.busyCycles := busy
  io.idleCycles := idle
  io.queueOccupancy := consumer.io.queueOccupancy
  io.outputOccupancy := consumer.io.outputOccupancy
  io.matVecActive := consumer.io.matVecActive
  io.matVecStart := consumer.io.matVecStart
  io.matVecResult := consumer.io.matVecResult
}

/** Elaboration boundary used by the 1/2/4-cluster controlled experiment. */
class ComputeClusterArray(
    val clusterCount: Int,
    config: TileJobConfig = TileJobConfig(),
    queueDepth: Int = 4,
    outputDepth: Int = 2
) extends Component {
  require(Set(1, 2, 4).contains(clusterCount))

  val io = new Bundle {
    val commands =
      Vec(slave(Stream(MatVecTileCommand(config))), clusterCount)
    val results =
      Vec(master(Stream(MatVecTileResult(config))), clusterCount)
    val acceptedJobs = out Vec (UInt(64 bits), clusterCount)
    val completedJobs = out Vec (UInt(64 bits), clusterCount)
    val busyCycles = out Vec (UInt(64 bits), clusterCount)
    val idleCycles = out Vec (UInt(64 bits), clusterCount)
    val queueOccupancy =
      out Vec (UInt(log2Up(queueDepth + 1) bits), clusterCount)
    val matVecActive = out Vec (Bool(), clusterCount)
    val matVecStart = out Vec (Bool(), clusterCount)
    val matVecResult = out Vec (Bool(), clusterCount)
  }

  for (index <- 0 until clusterCount) {
    val cluster = new ComputeCluster(
      index,
      clusterCount,
      config,
      queueDepth,
      outputDepth
    )
    cluster.io.command << io.commands(index)
    io.results(index) << cluster.io.result
    io.acceptedJobs(index) := cluster.io.acceptedJobs
    io.completedJobs(index) := cluster.io.completedJobs
    io.busyCycles(index) := cluster.io.busyCycles
    io.idleCycles(index) := cluster.io.idleCycles
    io.queueOccupancy(index) := cluster.io.queueOccupancy
    io.matVecActive(index) := cluster.io.matVecActive
    io.matVecStart(index) := cluster.io.matVecStart
    io.matVecResult(index) := cluster.io.matVecResult
  }
}

/** Deterministic, fresh-JVM generation boundary for paper evidence.
  *
  * Test-suite elaboration order can change anonymous SpinalHDL names, so the
  * paper never hashes Verilog emitted as a side effect of a multi-suite test.
  */
object GenerateComputeClusterArray {
  def main(args: Array[String]): Unit = {
    require(
      args.length == 2,
      "usage: GenerateComputeClusterArray <1|2|4> <target-directory>"
    )
    val clusters = args(0).toInt
    require(Set(1, 2, 4).contains(clusters))
    SpinalConfig(
      targetDirectory = args(1),
      headerWithRepoHash = false
    ).generateVerilog(
      new ComputeClusterArray(clusterCount = clusters)
    )
  }
}
