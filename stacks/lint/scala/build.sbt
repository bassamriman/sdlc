// project/plugins.sbt:
//   addSbtPlugin("ch.epfl.scala" % "sbt-scalafix" % "0.14.10")
//   addSbtPlugin("org.wartremover" % "sbt-wartremover" % "3.6.3")
// Check: sbt "scalafixAll --check" && sbt compile. Non-exhaustive match on sealed/enum is a compiler warning, fatal under -Werror.
scalacOptions ++= Seq("-Werror", "-Wunused:all", "-Wvalue-discard", "-Wnonunit-statement", "-deprecation", "-feature")

Compile / compile / wartremoverErrors ++= Warts.unsafe ++ Seq(Wart.MutableDataStructures, Wart.While)
