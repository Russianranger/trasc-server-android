#!/usr/bin/env bash
set -euo pipefail
cc -std=c11 -Wall -Wextra -Werror tests/frame_protocol.c -o /tmp/trasc-frame-test
/tmp/trasc-frame-test
cc -std=c11 -Wall -Wextra -Werror tests/frame_transfer.c -o /tmp/trasc-transfer-test
/tmp/trasc-transfer-test
g++ -std=c++14 -O2 -Wall -Wextra -Werror tests/fast_decimal.cpp -o /tmp/trasc-decimal-test
/tmp/trasc-decimal-test
g++ -std=c++14 -O2 -Wall -Wextra -Werror tests/takp_camera_recenter.cpp -o /tmp/trasc-takp-camera-test
/tmp/trasc-takp-camera-test
classes=$(mktemp -d)
trap 'rm -rf "$classes"' EXIT
python3 tests/build_checksum_fixture.py "$classes/checksum.cpp"
g++ -std=c++14 -O0 -Ibackend "$classes/checksum.cpp" -o "$classes/checksum"
"$classes/checksum"
compiler=(javac)
if ! command -v javac >/dev/null; then compiler=(java -m jdk.compiler/com.sun.tools.javac.Main); fi
"${compiler[@]}" -d "$classes" tests/java/android/system/Os.java \
    app/src/main/java/io/github/russianranger/trasc/AudioPcmSession.java \
    app/src/main/java/io/github/russianranger/trasc/AudioBufferPolicy.java \
    tests/java/io/github/russianranger/trasc/AudioHostTest.java \
    app/src/main/java/io/github/russianranger/trasc/TarExtractor.java \
    app/src/main/java/io/github/russianranger/trasc/SessionArchive.java \
    app/src/main/java/io/github/russianranger/trasc/SessionTransfer.java \
    app/src/main/java/io/github/russianranger/trasc/SessionPreferences.java \
    app/src/main/java/io/github/russianranger/trasc/AllProfileSwap.java \
    tests/java/io/github/russianranger/trasc/AllSessionHostTest.java \
    tests/java/io/github/russianranger/trasc/TarExtractorHostTest.java \
    app/src/main/java/io/github/russianranger/trasc/WorldProfiles.java \
    app/src/main/java/io/github/russianranger/trasc/ServerRuntimeIdentity.java \
    tests/java/io/github/russianranger/trasc/ServerRuntimeIdentityHostTest.java \
    tests/java/io/github/russianranger/trasc/WorldProfilesHostTest.java \
    app/src/main/java/io/github/russianranger/trasc/StorageFiles.java \
    tests/java/io/github/russianranger/trasc/StorageFilesTest.java \
    app/src/main/java/io/github/russianranger/trasc/LocalLogs.java \
    app/src/main/java/io/github/russianranger/trasc/LogRetention.java \
    app/src/main/java/io/github/russianranger/trasc/LogCleanup.java \
    tests/java/io/github/russianranger/trasc/LogRetentionHostTest.java \
    app/src/main/java/io/github/russianranger/trasc/ControllerInput.java \
    app/src/main/java/io/github/russianranger/trasc/RelativeInput.java \
    app/src/main/java/io/github/russianranger/trasc/DisplayInput.java \
    app/src/main/java/io/github/russianranger/trasc/GameCommand.java \
    tests/java/io/github/russianranger/trasc/GameCommandHostTest.java \
    app/src/main/java/io/github/russianranger/trasc/ClientPrefix.java \
    app/src/main/java/io/github/russianranger/trasc/ClientProfilePolicy.java \
    tests/java/io/github/russianranger/trasc/ClientProfilePolicyHostTest.java \
    app/src/main/java/io/github/russianranger/trasc/ClientTransientPaths.java \
    tests/java/io/github/russianranger/trasc/ClientTransientPathsHostTest.java \
    app/src/main/java/io/github/russianranger/trasc/ClientOverlayPosition.java \
    tests/java/io/github/russianranger/trasc/ClientOverlayPositionHostTest.java \
    app/src/main/java/io/github/russianranger/trasc/RfbConnection.java \
    app/src/main/java/io/github/russianranger/trasc/ClientFrameStats.java \
    app/src/main/java/io/github/russianranger/trasc/ProotAcceleration.java \
    tests/java/io/github/russianranger/trasc/ProotAccelerationHostTest.java \
    tests/java/io/github/russianranger/trasc/ClientHostTest.java \
    tests/java/io/github/russianranger/trasc/ManagementHostTest.java \
    tests/java/io/github/russianranger/trasc/RuntimeSessionHostTest.java
java -cp "$classes" io.github.russianranger.trasc.GameCommandHostTest
java -cp "$classes" io.github.russianranger.trasc.AudioHostTest
java -cp "$classes" io.github.russianranger.trasc.LogRetentionHostTest
java -cp "$classes" io.github.russianranger.trasc.ManagementHostTest
java -Xmx96m -cp "$classes" io.github.russianranger.trasc.AllSessionHostTest
if [[ ${TRASC_ARCHIVE_HEAVY_TESTS:-0} == 1 ]]; then
    # Optional disk/time-intensive qualification: a sparse >4GiB payload,
    # 190k inventory records, and a near-limit long-name/link index at 96MiB.
    for archive_case in --zip64 --entries --metadata; do
        java -Xmx96m -cp "$classes" io.github.russianranger.trasc.AllSessionHostTest "$archive_case"
    done
fi
java -cp "$classes" io.github.russianranger.trasc.TarExtractorHostTest
java -cp "$classes" io.github.russianranger.trasc.WorldProfilesHostTest
java -cp "$classes" io.github.russianranger.trasc.ServerRuntimeIdentityHostTest
java -cp "$classes" io.github.russianranger.trasc.StorageFilesTest
java -cp "$classes" io.github.russianranger.trasc.ClientHostTest
java -cp "$classes" io.github.russianranger.trasc.ClientProfilePolicyHostTest
java -cp "$classes" io.github.russianranger.trasc.ClientTransientPathsHostTest
java -cp "$classes" io.github.russianranger.trasc.ClientOverlayPositionHostTest
java -cp "$classes" io.github.russianranger.trasc.ProotAccelerationHostTest
if [[ $# -gt 0 ]]; then
    java -Xmx512m -cp "$classes" io.github.russianranger.trasc.RuntimeSessionHostTest "$1"
fi
