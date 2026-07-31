package varp.compute

import spinal.core._

final case class TileJobConfig(
    jobIdWidth: Int = 32,
    timestampWidth: Int = 64,
    layerIdWidth: Int = 16,
    activationIdWidth: Int = 32,
    addressWidth: Int = 64,
    indexWidth: Int = 16,
    channelWidth: Int = 2,
    bundleWidth: Int = 2,
    ownerWidth: Int = 2,
    priorityWidth: Int = 8,
    inputDim: Int = 16,
    outputDim: Int = 4,
    dataWidth: Int = 8,
    accWidth: Int = 32
) {
  require(inputDim == 16, "the imported legacy primitive has a 16-entry K tile")
  require(outputDim == 4, "the imported legacy primitive has a 4-entry N tile")
  require(Set(1, 2).contains(channelWidth))
  require(Set(1, 2).contains(bundleWidth))
  require(Set(1, 2).contains(ownerWidth))
}

object TileOperation {
  val MatVec = 0
  val Attention = 1
  val Mlp = 2
  val LmHead = 3
}

/** Complete scheduler identity for one full-K, N-axis output tile. */
case class TileJob(config: TileJobConfig = TileJobConfig()) extends Bundle {
  val jobId = UInt(config.jobIdWidth bits)
  val arrivalTimestamp = UInt(config.timestampWidth bits)
  val layerId = UInt(config.layerIdWidth bits)
  val operationType = UInt(2 bits)
  val activationId = UInt(config.activationIdWidth bits)
  val weightBase = UInt(config.addressWidth bits)
  val outputBase = UInt(config.addressWidth bits)
  val kStart = UInt(config.indexWidth bits)
  val kLength = UInt(config.indexWidth bits)
  val nStart = UInt(config.indexWidth bits)
  val nLength = UInt(config.indexWidth bits)
  val preferredChannel = UInt(config.channelWidth bits)
  val preferredLinkBundle = UInt(config.bundleWidth bits)
  val reductionOwner = UInt(config.ownerWidth bits)
  val priority = UInt(config.priorityWidth bits)
  val stealable = Bool()
}

case class MatVecTileCommand(config: TileJobConfig = TileJobConfig())
    extends Bundle {
  val job = TileJob(config)
  val activation = Vec(SInt(config.dataWidth bits), config.inputDim)
  val weights =
    Vec(
      Vec(SInt(config.dataWidth bits), config.inputDim),
      config.outputDim
    )
}

case class MatVecTileResult(config: TileJobConfig = TileJobConfig())
    extends Bundle {
  val job = TileJob(config)
  val outputs = Vec(SInt(config.accWidth bits), config.outputDim)
}
