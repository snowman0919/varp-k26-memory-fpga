package varp

import org.scalatest.funsuite.AnyFunSuite
import spinal.core.sim._
import varp.compute._
import varp.k26.ClosedLoopVirtualPrototypeTop
import varp.scheduler.SchedulerPolicy

import java.io.PrintWriter
import java.nio.file.{Files, Paths}
import scala.io.Source

final class ClosedLoopVirtualPrototypeTopSpec extends AnyFunSuite {
  private case class Fixture(
      projectionClass: String,
      activation: Seq[Int],
      weightsByOutput: Seq[Seq[Int]],
      expected: Seq[Int],
      tileSha256: String
  )

  private val config = TileJobConfig()

  private def fixtures(): Seq[Fixture] = {
    val path =
      Paths.get("experiments/gemma3_1b/representative_weight_tiles_int8.csv")
    require(Files.isRegularFile(path), s"missing generated fixture: $path")
    val source = Source.fromFile(path.toFile, "UTF-8")
    try {
      val lines = source.getLines().toVector
      val header = lines.head.split(",", -1).zipWithIndex.toMap
      lines.tail
        .map(_.split(",", -1))
        .groupBy(row => row(header("projection_class")))
        .toSeq
        .sortBy(_._1)
        .map {
          case (projectionClass, unordered) =>
            val ordered = unordered.sortBy(row => row(header("k_index")).toInt)
            Fixture(
              projectionClass,
              ordered.map(row => row(header("activation_int8")).toInt),
              (0 until config.outputDim).map(output =>
                ordered.map(row => row(header(s"weight_n${output}_int8")).toInt)
              ),
              (0 until config.outputDim).map(output =>
                ordered.head(header(s"reference_n${output}_int32")).toInt
              ),
              ordered.head(header("quantized_tile_sha256"))
            )
        }
    } finally {
      source.close()
    }
  }

  test("actual Gemma tiles cross DMA response and logical link before MatVec") {
    val cases = fixtures()
    val traces = collection.mutable.ArrayBuffer.empty[Seq[Any]]
    SimConfig.withVerilator
      .workspacePath("build/closed-loop-gemma-tile")
      .compile(
        new ClosedLoopVirtualPrototypeTop(
          clusterCount = 1,
          channelCount = 1,
          bundleCount = 1,
          policy = SchedulerPolicy.S0GlobalFifo,
          pendingDepth = 8,
          linkFifoDepth = 2
        )
      )
      .doSim(seed = 0x26) { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.io.fetchCommand.valid #= false
        dut.io.memoryResponse.valid #= false
        dut.io.memoryCommands(0).ready #= true
        dut.io.results(0).ready #= true
        dut.io.clusterChannel(0) #= 0
        dut.io.clusterLinkBundle(0) #= 0
        dut.io.activationResident(0) #= true
        dut.io.residentActivationId(0) #= 0
        dut.io.now #= 0
        var cycle = 0L
        def tick(): Unit = {
          cycle += 1
          dut.io.now #= cycle
          dut.clockDomain.waitSampling()
        }
        (0 until 5).foreach(_ => tick())

        cases.zipWithIndex.foreach {
          case (fixture, index) =>
            val jobId = 100 + index
            val job = dut.io.fetchCommand.payload.job
            job.jobId #= jobId
            job.arrivalTimestamp #= cycle
            job.layerId #= index
            job.operationType #= TileOperation.MatVec
            job.activationId #= index
            job.weightBase #= 0x1000 + index * 0x100
            job.outputBase #= 0x2000 + index * 0x100
            job.kStart #= 0
            job.kLength #= config.inputDim
            job.nStart #= 0
            job.nLength #= config.outputDim
            job.preferredChannel #= 0
            job.preferredLinkBundle #= 0
            job.reductionOwner #= 0
            job.priority #= 0
            job.stealable #= true
            fixture.activation.indices.foreach(position =>
              dut.io.fetchCommand.payload.activation(position) #=
                fixture.activation(position)
            )

            val acceptedCycle = cycle
            dut.io.fetchCommand.valid #= true
            while (!dut.io.fetchCommand.ready.toBoolean) tick()
            tick()
            dut.io.fetchCommand.valid #= false

            while (!dut.io.memoryCommands(0).valid.toBoolean) tick()
            assert(
              dut.io.memoryCommands(0).payload.jobId.toBigInt == jobId
            )
            val dmaCycle = cycle
            tick()

            dut.io.memoryResponse.payload.jobId #= jobId
            dut.io.memoryResponse.payload.channel #= 0
            dut.io.memoryResponse.payload.responseOrdinal #= index
            dut.io.memoryResponse.payload.crcBad #= false
            fixture.weightsByOutput.indices.foreach { output =>
              fixture.weightsByOutput(output).indices.foreach { input =>
                dut.io.memoryResponse.payload.weights(output)(input) #=
                  fixture.weightsByOutput(output)(input)
              }
            }
            dut.io.memoryResponse.valid #= true
            while (!dut.io.memoryResponse.ready.toBoolean) tick()
            val responseCycle = cycle
            tick()
            dut.io.memoryResponse.valid #= false

            var waited = 0
            while (!dut.io.results(0).valid.toBoolean && waited < 300) {
              tick()
              waited += 1
            }
            assert(waited < 300)
            assert(dut.io.results(0).payload.job.jobId.toBigInt == jobId)
            val observed = fixture.expected.indices.map(position =>
              dut.io.results(0).payload.outputs(position).toInt
            )
            assert(observed == fixture.expected)
            val resultCycle = cycle
            traces += Seq(
              fixture.projectionClass,
              fixture.tileSha256,
              jobId,
              acceptedCycle,
              dmaCycle,
              responseCycle,
              resultCycle,
              observed.mkString("|"),
              fixture.expected.mkString("|"),
              observed == fixture.expected,
              "actual-weight-closed-logical-path-rtl-simulated"
            )
            tick()
          }

        assert(dut.io.dmaRequests.toBigInt == cases.size)
        assert(dut.io.weightResponses.toBigInt == cases.size)
        assert(dut.io.payloadsDispatched.toBigInt == cases.size)
        assert(dut.io.completedJobs(0).toBigInt == cases.size)
        assert(dut.io.pendingJobs.toBigInt == 0)
        assert(dut.io.crcErrors.toBigInt == 0)
      }

    val output = Paths.get("evidence/model/gemma3_1b_closed_loop_trace.csv")
    Files.createDirectories(output.getParent)
    val writer = new PrintWriter(output.toFile, "UTF-8")
    try {
      writer.println(
        "projection_class,quantized_tile_sha256,job_id,fetch_accept_cycle," +
          "dma_command_cycle,ddr_response_cycle,matvec_result_cycle," +
          "observed_int32,expected_int32,parity,evidence_type"
      )
      traces.foreach(row => writer.println(row.mkString(",")))
    } finally {
      writer.close()
    }
  }
}
