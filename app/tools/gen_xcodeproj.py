#!/usr/bin/env python3
"""Writes ios/HeatGuardian.xcodeproj (project.pbxproj + shared scheme + workspace) from the files on disk.

    python3 -I ios/tools/gen_xcodeproj.py

Hand-rolled on purpose (no XcodeGen on this Linux box): object ids are md5-derived (stable, 24 hex, unique — the
script asserts it), every source / resource file found under ios/HeatGuardian and ios/HeatGuardianTests is put in a
group and a build phase. ios/project.yml is the XcodeGen fallback that describes the same project.
"""
import hashlib, os, sys

IOS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP, TESTS = "HeatGuardian", "HeatGuardianTests"
BUNDLE_ID = "gr.heatguardian.family"
DEPLOY = "26.0"
IDS = {}


def oid(*key):
    k = "/".join(key)
    if k not in IDS:
        h = hashlib.md5(("hg-ios:" + k).encode()).hexdigest()[:24].upper()
        assert h not in IDS.values(), "id collision " + k
        IDS[k] = h
    return IDS[k]


def q(s):
    """OpenStep string: bare when safe, else quoted."""
    import re
    if s and re.fullmatch(r"[A-Za-z0-9_./]+", s) and not s.startswith("/"):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


FTYPE = {".swift": "sourcecode.swift", ".json": "text.json", ".wav": "audio.wav", ".plist": "text.plist.xml",
         ".xcassets": "folder.assetcatalog", ".md": "net.daringfireball.markdown",
         ".entitlements": "text.plist.entitlements"}


def scan(root):
    """-> list of (relpath from IOS, kind) where kind in source/resource/plist/asset"""
    out = []
    base = os.path.join(IOS, root)
    for dp, dns, fns in os.walk(base):
        dns.sort()
        if dp.endswith(".xcassets"):
            dns[:] = []
            continue
        for d in list(dns):
            if d.endswith(".xcassets"):
                out.append((os.path.relpath(os.path.join(dp, d), IOS), "resource"))
        for f in sorted(fns):
            rel = os.path.relpath(os.path.join(dp, f), IOS)
            ext = os.path.splitext(f)[1]
            if f.startswith("."): continue
            if ext == ".swift": out.append((rel, "source"))
            elif f == "Info.plist" or ext == ".entitlements": out.append((rel, "plist"))   # referenced, not built
            elif ext in (".json", ".wav"): out.append((rel, "resource"))
    return sorted(out)


def main():
    app_files, test_files = scan(APP), scan(TESTS)
    o = []  # sections: list of (isa, [(id, body)])
    sec = {}
    def add(isa, i, body): sec.setdefault(isa, []).append((i, body))

    P_APP = oid("product", APP); P_TEST = oid("product", TESTS)
    T_APP = oid("target", APP); T_TEST = oid("target", TESTS)
    PROJ = oid("project")
    # build phases
    SRC_APP, RES_APP, FW_APP = oid("phase", APP, "src"), oid("phase", APP, "res"), oid("phase", APP, "fw")
    SRC_T, RES_T, FW_T = oid("phase", TESTS, "src"), oid("phase", TESTS, "res"), oid("phase", TESTS, "fw")

    # file refs + build files
    phase_files = {SRC_APP: [], RES_APP: [], SRC_T: [], RES_T: []}
    fref = {}
    for files, tgt in ((app_files, APP), (test_files, TESTS)):
        for rel, kind in files:
            name = os.path.basename(rel)
            ext = os.path.splitext(name)[1]
            fr = oid("file", rel); fref[rel] = fr
            add("PBXFileReference", fr, "{isa = PBXFileReference; lastKnownFileType = %s; path = %s; sourceTree = \"<group>\"; }"
                % (FTYPE.get(ext, "text"), q(name)))
            if kind == "plist": continue
            ph = (SRC_APP if kind == "source" else RES_APP) if tgt == APP else (SRC_T if kind == "source" else RES_T)
            bf = oid("build", tgt, rel)
            add("PBXBuildFile", bf, "{isa = PBXBuildFile; fileRef = %s /* %s */; }" % (fr, name))
            phase_files[ph].append((bf, name))
    add("PBXFileReference", P_APP, "{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = %s.app; sourceTree = BUILT_PRODUCTS_DIR; }" % APP)
    add("PBXFileReference", P_TEST, "{isa = PBXFileReference; explicitFileType = wrapper.cfbundle; includeInIndex = 0; path = %s.xctest; sourceTree = BUILT_PRODUCTS_DIR; }" % TESTS)
    readme = oid("file", "README.md")
    add("PBXFileReference", readme, "{isa = PBXFileReference; lastKnownFileType = net.daringfireball.markdown; path = README.md; sourceTree = \"<group>\"; }")

    # groups (mirror the folder tree)
    groups = {}
    def group_for(dirrel):
        if dirrel in groups: return groups[dirrel]
        gid = oid("group", dirrel); groups[dirrel] = {"id": gid, "children": [], "name": os.path.basename(dirrel)}
        parent = os.path.dirname(dirrel)
        if parent: group_for(parent)["children"].append((gid, os.path.basename(dirrel)))
        return groups[dirrel]
    for rel, _ in app_files + test_files:
        group_for(os.path.dirname(rel))["children"].append((fref[rel], os.path.basename(rel)))
    PRODUCTS = oid("group", "Products"); MAIN = oid("group", "<main>")
    for g in groups.values():
        kids = sorted(g["children"], key=lambda c: (not any(c[0] == x["id"] for x in groups.values()), c[1].lower()))
        add("PBXGroup", g["id"], "{isa = PBXGroup; children = (%s); path = %s; sourceTree = \"<group>\"; }"
            % ("".join("%s /* %s */, " % c for c in kids), q(g["name"])))
    add("PBXGroup", PRODUCTS, "{isa = PBXGroup; children = (%s /* %s.app */, %s /* %s.xctest */, ); name = Products; sourceTree = \"<group>\"; }" % (P_APP, APP, P_TEST, TESTS))
    add("PBXGroup", MAIN, "{isa = PBXGroup; children = (%s /* README.md */, %s /* %s */, %s /* %s */, %s /* Products */, ); sourceTree = \"<group>\"; }"
        % (readme, groups[APP]["id"], APP, groups[TESTS]["id"], TESTS, PRODUCTS))

    # phases
    def phase(isa, i, items):
        add(isa, i, "{isa = %s; buildActionMask = 2147483647; files = (%s); runOnlyForDeploymentPostprocessing = 0; }"
            % (isa, "".join("%s /* %s in %s */, " % (b, n, "Sources" if isa == "PBXSourcesBuildPhase" else "Resources") for b, n in items)))
    phase("PBXSourcesBuildPhase", SRC_APP, phase_files[SRC_APP]); phase("PBXResourcesBuildPhase", RES_APP, phase_files[RES_APP])
    phase("PBXSourcesBuildPhase", SRC_T, phase_files[SRC_T]); phase("PBXResourcesBuildPhase", RES_T, phase_files[RES_T])
    add("PBXFrameworksBuildPhase", FW_APP, "{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }")
    add("PBXFrameworksBuildPhase", FW_T, "{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }")

    # dependency test -> app
    PROXY, DEP = oid("proxy"), oid("dep")
    add("PBXContainerItemProxy", PROXY, "{isa = PBXContainerItemProxy; containerPortal = %s /* Project object */; proxyType = 1; remoteGlobalIDString = %s; remoteInfo = %s; }" % (PROJ, T_APP, APP))
    add("PBXTargetDependency", DEP, "{isa = PBXTargetDependency; target = %s /* %s */; targetProxy = %s /* PBXContainerItemProxy */; }" % (T_APP, APP, PROXY))

    # build settings
    def bs(d):
        def val(v):
            if isinstance(v, list): return "(" + "".join(q(x) + ", " for x in v) + ")"
            return q(str(v))
        return "{" + "".join("%s = %s; " % (k, val(v)) for k, v in sorted(d.items())) + "}"
    common = dict(ALWAYS_SEARCH_USER_PATHS="NO", CLANG_ENABLE_MODULES="YES", CLANG_ENABLE_OBJC_ARC="YES",
                  COPY_PHASE_STRIP="NO", ENABLE_STRICT_OBJC_MSGSEND="YES", ENABLE_USER_SCRIPT_SANDBOXING="YES",
                  GCC_C_LANGUAGE_STANDARD="gnu17", IPHONEOS_DEPLOYMENT_TARGET=DEPLOY, LOCALIZATION_PREFERS_STRING_CATALOGS="YES",
                  MTL_FAST_MATH="YES", SDKROOT="iphoneos", SWIFT_VERSION="5.0", ASSETCATALOG_COMPILER_GENERATE_SWIFT_ASSET_SYMBOL_EXTENSIONS="YES")
    pdebug = dict(common, DEBUG_INFORMATION_FORMAT="dwarf", ENABLE_TESTABILITY="YES", GCC_OPTIMIZATION_LEVEL="0",
                  GCC_PREPROCESSOR_DEFINITIONS=["DEBUG=1", "$(inherited)"], MTL_ENABLE_DEBUG_INFO="INCLUDE_SOURCE",
                  ONLY_ACTIVE_ARCH="YES", SWIFT_ACTIVE_COMPILATION_CONDITIONS="DEBUG $(inherited)", SWIFT_OPTIMIZATION_LEVEL="-Onone")
    prelease = dict(common, DEBUG_INFORMATION_FORMAT="dwarf-with-dsym", ENABLE_NS_ASSERTIONS="NO", MTL_ENABLE_DEBUG_INFO="NO",
                    SWIFT_COMPILATION_MODE="wholemodule", VALIDATE_PRODUCT="YES")
    app = dict(ASSETCATALOG_COMPILER_APPICON_NAME="AppIcon", ASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME="AccentColor",
               CODE_SIGN_STYLE="Automatic", CURRENT_PROJECT_VERSION="1", DEVELOPMENT_TEAM="", ENABLE_PREVIEWS="YES",
               GENERATE_INFOPLIST_FILE="NO", INFOPLIST_FILE="HeatGuardian/Info.plist",
               LD_RUNPATH_SEARCH_PATHS=["$(inherited)", "@executable_path/Frameworks"], MARKETING_VERSION="1.0",
               PRODUCT_BUNDLE_IDENTIFIER=BUNDLE_ID, PRODUCT_NAME="$(TARGET_NAME)", SUPPORTED_PLATFORMS="iphoneos iphonesimulator",
               SUPPORTS_MACCATALYST="NO", SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD="NO", SUPPORTS_XR_DESIGNED_FOR_IPHONE_IPAD="NO",
               SWIFT_EMIT_LOC_STRINGS="NO", SWIFT_VERSION="5.0", TARGETED_DEVICE_FAMILY="1")
    test = dict(BUNDLE_LOADER="$(TEST_HOST)", CODE_SIGN_STYLE="Automatic", CURRENT_PROJECT_VERSION="1", DEVELOPMENT_TEAM="",
                GENERATE_INFOPLIST_FILE="YES", MARKETING_VERSION="1.0", PRODUCT_BUNDLE_IDENTIFIER=BUNDLE_ID + ".tests",
                PRODUCT_NAME="$(TARGET_NAME)", SWIFT_EMIT_LOC_STRINGS="NO", SWIFT_VERSION="5.0", TARGETED_DEVICE_FAMILY="1",
                TEST_HOST="$(BUILT_PRODUCTS_DIR)/HeatGuardian.app/$(BUNDLE_EXECUTABLE_FOLDER_PATH)/HeatGuardian")
    lists = {}
    for owner, (dbg, rel) in {"project": (pdebug, prelease), APP: (app, app), TESTS: (test, test)}.items():
        ids = []
        for cname, d in (("Debug", dbg), ("Release", rel)):
            cid = oid("config", owner, cname); ids.append((cid, cname))
            add("XCBuildConfiguration", cid, "{isa = XCBuildConfiguration; buildSettings = %s; name = %s; }" % (bs(d), cname))
        lid = oid("configlist", owner); lists[owner] = lid
        add("XCConfigurationList", lid, "{isa = XCConfigurationList; buildConfigurations = (%s); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; }"
            % "".join("%s /* %s */, " % c for c in ids))

    add("PBXNativeTarget", T_APP, "{isa = PBXNativeTarget; buildConfigurationList = %s; buildPhases = (%s /* Sources */, %s /* Frameworks */, %s /* Resources */, ); buildRules = (); dependencies = (); name = %s; productName = %s; productReference = %s /* %s.app */; productType = \"com.apple.product-type.application\"; }"
        % (lists[APP], SRC_APP, FW_APP, RES_APP, APP, APP, P_APP, APP))
    add("PBXNativeTarget", T_TEST, "{isa = PBXNativeTarget; buildConfigurationList = %s; buildPhases = (%s /* Sources */, %s /* Frameworks */, %s /* Resources */, ); buildRules = (); dependencies = (%s /* PBXTargetDependency */, ); name = %s; productName = %s; productReference = %s /* %s.xctest */; productType = \"com.apple.product-type.bundle.unit-test\"; }"
        % (lists[TESTS], SRC_T, FW_T, RES_T, DEP, TESTS, TESTS, P_TEST, TESTS))
    add("PBXProject", PROJ, "{isa = PBXProject; attributes = {BuildIndependentTargetsInParallel = 1; LastSwiftUpdateCheck = 1500; LastUpgradeCheck = 1500; TargetAttributes = {%s = {CreatedOnToolsVersion = 15.0; }; %s = {CreatedOnToolsVersion = 15.0; TestTargetID = %s; }; }; }; buildConfigurationList = %s; compatibilityVersion = \"Xcode 14.0\"; developmentRegion = el; hasScannedForEncodings = 0; knownRegions = (el, en, Base, ); mainGroup = %s; productRefGroup = %s /* Products */; projectDirPath = \"\"; projectRoot = \"\"; targets = (%s /* %s */, %s /* %s */, ); }"
        % (T_APP, T_TEST, T_APP, lists["project"], MAIN, PRODUCTS, T_APP, APP, T_TEST, TESTS))

    out = ["// !$*UTF8*$!", "{", "\tarchiveVersion = 1;", "\tclasses = {", "\t};", "\tobjectVersion = 56;", "\tobjects = {", ""]
    for isa in sorted(sec):
        out.append("/* Begin %s section */" % isa)
        for i, body in sorted(sec[isa]):
            out.append("\t\t%s = %s;" % (i, body))
        out.append("/* End %s section */" % isa)
        out.append("")
    out += ["\t};", "\trootObject = %s /* Project object */;" % PROJ, "}", ""]
    proj = os.path.join(IOS, APP + ".xcodeproj")
    os.makedirs(os.path.join(proj, "xcshareddata", "xcschemes"), exist_ok=True)
    os.makedirs(os.path.join(proj, "project.xcworkspace"), exist_ok=True)
    open(os.path.join(proj, "project.pbxproj"), "w").write("\n".join(out))
    open(os.path.join(proj, "project.xcworkspace", "contents.xcworkspacedata"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<Workspace\n   version = "1.0">\n   <FileRef\n      location = "self:">\n   </FileRef>\n</Workspace>\n')
    ref = lambda t, p: ('<BuildableReference BuildableIdentifier = "primary" BlueprintIdentifier = "%s" BuildableName = "%s" '
                        'BlueprintName = "%s" ReferencedContainer = "container:HeatGuardian.xcodeproj"></BuildableReference>' % (t, p, os.path.splitext(p)[0]))
    scheme = f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion = "1500" version = "1.7">
   <BuildAction parallelizeBuildables = "YES" buildImplicitDependencies = "YES">
      <BuildActionEntries>
         <BuildActionEntry buildForTesting = "YES" buildForRunning = "YES" buildForProfiling = "YES" buildForArchiving = "YES" buildForAnalyzing = "YES">
            {ref(T_APP, APP + ".app")}
         </BuildActionEntry>
      </BuildActionEntries>
   </BuildAction>
   <TestAction buildConfiguration = "Debug" selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv = "YES">
      <Testables>
         <TestableReference skipped = "NO">
            {ref(T_TEST, TESTS + ".xctest")}
         </TestableReference>
      </Testables>
   </TestAction>
   <LaunchAction buildConfiguration = "Debug" selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB" launchStyle = "0" useCustomWorkingDirectory = "NO" ignoresPersistentStateOnLaunch = "NO" debugDocumentVersioning = "YES" debugServiceExtension = "internal" allowLocationSimulation = "YES">
      <BuildableProductRunnable runnableDebuggingMode = "0">
         {ref(T_APP, APP + ".app")}
      </BuildableProductRunnable>
   </LaunchAction>
   <ProfileAction buildConfiguration = "Release" shouldUseLaunchSchemeArgsEnv = "YES" savedToolIdentifier = "" useCustomWorkingDirectory = "NO" debugDocumentVersioning = "YES">
      <BuildableProductRunnable runnableDebuggingMode = "0">
         {ref(T_APP, APP + ".app")}
      </BuildableProductRunnable>
   </ProfileAction>
   <AnalyzeAction buildConfiguration = "Debug"></AnalyzeAction>
   <ArchiveAction buildConfiguration = "Release" revealArchiveInOrganizer = "YES"></ArchiveAction>
</Scheme>
'''
    open(os.path.join(proj, "xcshareddata", "xcschemes", APP + ".xcscheme"), "w").write(scheme)
    n_src = len(phase_files[SRC_APP]); n_res = len(phase_files[RES_APP])
    print("wrote %s: %d app sources, %d app resources, %d test sources, %d test resources, %d objects"
          % (proj, n_src, n_res, len(phase_files[SRC_T]), len(phase_files[RES_T]), len(IDS)))


if __name__ == "__main__":
    main()
