#!/usr/bin/env bash
# RUNS the XCTests of the non-UI code on Linux (real execution, not just a type-check): the pure-Foundation app files
# are built as module "HeatGuardian" (-enable-testing), the XCTest files are compiled against it with a generated
# XCTMain list, and the test vectors are copied next to the binary (Bundle(for:) = the executable's folder on Linux).
# Needs a Swift toolchain with XCTest on PATH (tested with 6.0.3 RELEASE ubuntu24.04).   Usage: ios/tools/linux_xctest/run.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; IOS="$HERE/../.."; APP="$IOS/HeatGuardian"; T="$IOS/HeatGuardianTests"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
SRC=( BLE/Frames.swift BLE/EcoFrames.swift Model/Plan.swift Model/Indoor.swift Model/Week.swift Model/Routine.swift
      Model/Replay.swift Model/NudgePlanner.swift Model/EventLog.swift Model/Strings.swift Model/Strings+Eco.swift
      Model/Strings+HerDay.swift Model/HerDay.swift Model/HerDayRoutine.swift Model/HerDayBand.swift Model/HerDayDemo.swift
      Model/Visits.swift ViewModels/LogRows.swift ViewModels/HerDayDisplay.swift Model/AlertQuality.swift Model/Strings+Quality.swift
      Model/Medications.swift Model/ReportLedger.swift Model/HeatReport.swift Model/HeatReportDemo.swift Model/Strings+Report.swift Model/HeatBody.swift Model/Strings+Body.swift
      Model/Tower/LadderEvents.swift Model/Tower/SMSText.swift Model/Tower/SMSRouting.swift Model/Tower/Outbox.swift
      Model/Tower/Twilio.swift Model/Tower/TowerEngine.swift Model/Tower/DayStory.swift Model/Tower/Balance.swift Model/Strings+Tower.swift
      Model/FitCheck.swift Model/Strings+Fit.swift )
TESTS=( HerDayTests EcoFramesTests FramesTests AlertQualityTests ReportTests TowerTests FitCheckTests AppFinishTests )
( cd "$W" && swiftc -parse-as-library -emit-library -static -emit-module -module-name HeatGuardian -enable-testing \
    $(for f in "${SRC[@]}"; do echo "$APP/$f"; done) -o libHeatGuardian.a )
# XCTMain list from the `func test…()` methods of each test class
{
  echo "import XCTest"
  echo "@testable import HeatGuardian"
  echo "XCTMain(["
  for c in "${TESTS[@]}"; do
    echo "  testCase(["
    grep -oE 'func (test[A-Za-z0-9_]+)\(\)' "$T/$c.swift" | sed -E "s/func (test[A-Za-z0-9_]+)\(\)/    (\"\1\", $c.\1),/"
    echo "  ]),"
  done
  echo "])"
} > "$W/main.swift"
cp "$T"/*.json "$APP"/Resources/*.json "$W"/   # test vectors + the app bundle resources (plan.json, replays)
( cd "$W" && swiftc -I . -L . -lHeatGuardian -lXCTest main.swift $(for c in "${TESTS[@]}"; do echo "$T/$c.swift"; done) -o hgtests \
  && ./hgtests )
