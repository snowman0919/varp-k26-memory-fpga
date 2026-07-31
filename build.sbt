ThisBuild / scalaVersion := "2.12.18"
ThisBuild / version := "0.1.0"
ThisBuild / organization := "org.varp"

lazy val spinalVersion = "1.14.2"

Compile / run / mainClass := Some("varp.k26.GenerateK26WorkStealingTop")
fork := true
Test / fork := true
Compile / scalaSource := baseDirectory.value / "hw/src/main/scala"
Test / scalaSource := baseDirectory.value / "hw/src/test/scala"
resolvers ++= Resolver.sonatypeOssRepos("public")

libraryDependencies ++= Seq(
  "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
  "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
  "com.github.spinalhdl" %% "spinalhdl-sim" % spinalVersion % Test,
  "org.scalatest" %% "scalatest" % "3.2.19" % Test
)

addCompilerPlugin(
  "com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion
)
