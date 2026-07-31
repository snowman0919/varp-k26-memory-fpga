package varp

import org.scalatest.funsuite.AnyFunSuite
import spinal.core.sim._
import varp.compute._

import java.io.PrintWriter
import java.nio.file.{Files, Paths}
import scala.io.Source

class GemmaWeightTileRtlParitySpec extends AnyFunSuite {
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
      val rows = lines.tail.map(_.split(",", -1))
      rows
        .groupBy(row => row(header("projection_class")))
        .toSeq
        .sortBy(_._1)
        .map {
          case (projectionClass, unordered) =>
            val ordered =
              unordered.sortBy(row => row(header("k_index")).toInt)
            val activation =
              ordered.map(row => row(header("activation_int8")).toInt)
            val weights = (0 until config.outputDim).map { output =>
              ordered.map(row =>
                row(header(s"weight_n${output}_int8")).toInt
              )
            }
            val expected = (0 until config.outputDim).map { output =>
              ordered.head(header(s"reference_n${output}_int32")).toInt
            }
            Fixture(
              projectionClass,
              activation,
              weights,
              expected,
              ordered.head(header("quantized_tile_sha256"))
            )
        }
    } finally {
      source.close()
    }
  }

  private def drive(
      dut: ComputeCluster,
      fixture: Fixture,
      jobId: Int
  ): Unit = {
    val job = dut.io.command.payload.job
    job.jobId #= jobId
    job.arrivalTimestamp #= 0
    job.layerId #= jobId
    job.operationType #= TileOperation.MatVec
    job.activationId #= jobId
    job.weightBase #= jobId * 4096L
    job.outputBase #= jobId * 64L
    job.kStart #= 0
    job.kLength #= config.inputDim
    job.nStart #= 0
    job.nLength #= config.outputDim
    job.preferredChannel #= 0
    job.preferredLinkBundle #= 0
    job.reductionOwner #= 0
    job.priority #= 0
    job.stealable #= true
    fixture.activation.indices.foreach(index =>
      dut.io.command.payload.activation(index) #= fixture.activation(index)
    )
    fixture.weightsByOutput.indices.foreach { output =>
      fixture.weightsByOutput(output).indices.foreach { input =>
        dut.io.command.payload.weights(output)(input) #=
          fixture.weightsByOutput(output)(input)
      }
    }
  }

  test("three actual Gemma weight tiles match their software INT32 references") {
    val cases = fixtures()
    assert(cases.map(_.projectionClass).toSet == Set(
      "gate_proj",
      "lm_head",
      "o_proj"
    ))
    val compiled = SimConfig.withVerilator
      .workspacePath("build/gemma-weight-tile-parity")
      .compile(new ComputeCluster(0, 1, config))
    val results = cases.zipWithIndex.map {
      case (fixture, jobId) =>
        var observed = Seq.empty[Int]
        var cycles = 0
        compiled.doSim(seed = 0x3a10 + jobId) { dut =>
          dut.clockDomain.forkStimulus(period = 10)
          dut.io.command.valid #= false
          dut.io.result.ready #= true
          drive(dut, fixture, jobId)
          dut.clockDomain.waitSampling()
          dut.io.command.valid #= true
          while (!dut.io.command.ready.toBoolean) {
            dut.clockDomain.waitSampling()
          }
          dut.clockDomain.waitSampling()
          dut.io.command.valid #= false
          while (!dut.io.result.valid.toBoolean && cycles < 200) {
            dut.clockDomain.waitSampling()
            cycles += 1
          }
          assert(cycles < 200)
          observed = (0 until config.outputDim)
            .map(dut.io.result.payload.outputs(_).toInt)
          assert(observed == fixture.expected)
        }
        (fixture, observed, cycles)
    }

    val output = Paths.get("evidence/model/gemma3_1b_rtl_tile_parity.csv")
    Files.createDirectories(output.getParent)
    val writer = new PrintWriter(output.toFile, "UTF-8")
    try {
      writer.println(
        "projection_class,quantized_tile_sha256,expected_int32," +
          "observed_int32,cycles,parity,evidence_type"
      )
      results.foreach {
        case (fixture, observed, cycles) =>
          writer.println(
            Seq(
              fixture.projectionClass,
              fixture.tileSha256,
              fixture.expected.mkString("|"),
              observed.mkString("|"),
              cycles,
              observed == fixture.expected,
              "actual-weight-bounded-rtl-simulated"
            ).mkString(",")
          )
      }
    } finally {
      writer.close()
    }
  }
}
