#!/usr/bin/env bash
# Type-check ALL app sources on Linux against hand-written API stubs of SwiftUI (incl. iOS 26 Liquid Glass / Tab) /
# Combine / Charts / UIKit / CoreBluetooth / AVFoundation / UserNotifications / CoreLocation / MapKit (the *.swift files here), through SIL
# (so definite-initialisation errors show too); #Preview bodies are rewritten to functions and checked as well. It catches Swift-language errors
# in our code (types, labels, result-builder bodies, optionals, our own members); it does NOT prove the Apple API
# signatures (the stubs are an approximation) and it cannot check delegate-selector matching. Xcode is the real test.
# Needs a Swift toolchain on PATH (tested with 6.0.3 RELEASE ubuntu24.04).   Usage: ios/tools/linux_typecheck/run.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; APP="$HERE/../../HeatGuardian"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
cp "$HERE"/*.swift "$W"/
( cd "$W" && swiftc -parse-as-library -emit-module -module-name UIKit UIKit.swift -o UIKit.swiftmodule \
  && swiftc -parse-as-library -emit-module -module-name Combine Combine.swift -o Combine.swiftmodule \
  && swiftc -parse-as-library -emit-module -module-name SwiftUI -I . SwiftUI.swift -o SwiftUI.swiftmodule \
  && swiftc -parse-as-library -emit-module -module-name Charts -I . Charts.swift -o Charts.swiftmodule \
  && swiftc -parse-as-library -emit-module -module-name Others Others.swift -o Others.swiftmodule )
mkdir "$W/app"
find "$APP" -name '*.swift' | while read -r f; do
  export HGF="$(basename "$f" .swift | tr -c 'A-Za-z0-9\n' '_')"
  sed -E 's/^import (CoreBluetooth|AVFoundation|UserNotifications|UniformTypeIdentifiers|CoreLocation|MapKit|Security|MessageUI)$/import Others/' "$f" \
    | perl -pe 's/^#Preview(\("[^"]*"\))?\s*\{/"\@MainActor \@ViewBuilder func __preview_$ENV{HGF}_".(++$n)."() -> some View {"/e' \
    > "$W/app/$(basename "$f")"   # #Preview bodies become ViewBuilder functions so they are type-checked too
done
( cd "$W/app" && swiftc -emit-sil -wmo -o /dev/null -parse-as-library -module-name HeatGuardian -I "$W" *.swift )   # SIL: also runs definite-initialisation / missing-return checks
echo "linux_typecheck: $(ls "$W/app" | wc -l) app files type-check against the stubs"
