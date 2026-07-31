package varp.link

import spinal.core._

/** Logical packet carried by BundleRouter.
  *
  * Physical serialization, credit return, CRC handling, GT wrappers, and a
  * receive path are intentionally outside the current public RTL boundary.
  */
case class LinkPacket() extends Bundle {
  val record = Bits(256 bits)
  val epoch = UInt(32 bits)
  val transportOrdinal = UInt(32 bits)
  val payloadBytes = UInt(32 bits)
  val crcBad = Bool()
  val wireBytes = UInt(32 bits)
}
