#!/usr/bin/env bash
set -euo pipefail
classes=$(mktemp -d)
trap 'rm -rf "$classes"' EXIT
compiler=(javac)
if ! command -v javac >/dev/null; then compiler=(java -m jdk.compiler/com.sun.tools.javac.Main); fi
"${compiler[@]}" -d "$classes" tests/java/android/system/Os.java \
    app/src/main/java/io/github/russianranger/trasc/TarExtractor.java \
    app/src/main/java/io/github/russianranger/trasc/SessionArchive.java \
    app/src/main/java/io/github/russianranger/trasc/ControllerInput.java \
    tests/java/io/github/russianranger/trasc/ManagementHostTest.java
java -cp "$classes" io.github.russianranger.trasc.ManagementHostTest
