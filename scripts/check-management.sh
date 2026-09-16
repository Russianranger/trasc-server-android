#!/usr/bin/env bash
set -euo pipefail
classes=$(mktemp -d)
trap 'rm -rf "$classes"' EXIT
compiler=(javac)
if ! command -v javac >/dev/null; then compiler=(java -m jdk.compiler/com.sun.tools.javac.Main); fi
"${compiler[@]}" -d "$classes" tests/java/android/system/Os.java \
    app/src/main/java/io/github/russianranger/trasc/AudioPcmSession.java \
    tests/java/io/github/russianranger/trasc/AudioHostTest.java \
    app/src/main/java/io/github/russianranger/trasc/TarExtractor.java \
    app/src/main/java/io/github/russianranger/trasc/SessionArchive.java \
    app/src/main/java/io/github/russianranger/trasc/LocalLogs.java \
    app/src/main/java/io/github/russianranger/trasc/ControllerInput.java \
    app/src/main/java/io/github/russianranger/trasc/DisplayInput.java \
    app/src/main/java/io/github/russianranger/trasc/ClientPrefix.java \
    app/src/main/java/io/github/russianranger/trasc/RfbConnection.java \
    app/src/main/java/io/github/russianranger/trasc/ClientFrameStats.java \
    app/src/main/java/io/github/russianranger/trasc/ProotAcceleration.java \
    tests/java/io/github/russianranger/trasc/ProotAccelerationHostTest.java \
    tests/java/io/github/russianranger/trasc/ClientHostTest.java \
    tests/java/io/github/russianranger/trasc/ManagementHostTest.java \
    tests/java/io/github/russianranger/trasc/RuntimeSessionHostTest.java
java -cp "$classes" io.github.russianranger.trasc.AudioHostTest
java -cp "$classes" io.github.russianranger.trasc.ManagementHostTest
java -cp "$classes" io.github.russianranger.trasc.ClientHostTest
java -cp "$classes" io.github.russianranger.trasc.ProotAccelerationHostTest
if [[ $# -gt 0 ]]; then
    java -Xmx512m -cp "$classes" io.github.russianranger.trasc.RuntimeSessionHostTest "$1"
fi
