#!/usr/bin/env python3
"""Structural check of ios/HeatGuardian.xcodeproj/project.pbxproj without Xcode.

    pip install --break-system-packages pbxproj openstep_parser   # once
    python3 ios/tools/check_xcodeproj.py

1. parses with openstep_parser (the plist/OpenStep grammar Xcode uses) and with mod-pbxproj (XcodeProject.load)
2. every id is 24 upper-hex and unique; every reference resolves to an object
3. every PBXBuildFile is in exactly one build phase and every phase entry is a PBXBuildFile
4. every file reference in the group tree exists on disk (group paths resolved like Xcode does)
5. every .swift under ios/HeatGuardian is compiled by the app target, every test .swift by the test target
6. Info.plist parses and has the required keys; the shared scheme's BlueprintIdentifiers are the targets
"""
import os, plistlib, re, sys
import openstep_parser
from pbxproj import XcodeProject

IOS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PBX = os.path.join(IOS, "HeatGuardian.xcodeproj", "project.pbxproj")
bad = 0
def check(c, msg):
    global bad
    if not c: bad += 1; print("FAIL", msg)

text = open(PBX).read()
root = openstep_parser.OpenStepDecoder.ParseFromString(text)
objs = root["objects"]
XcodeProject.load(PBX)   # raises on a grammar error

for k in objs: check(re.fullmatch(r"[0-9A-F]{24}", k), "id format " + k)
ids_in_text = re.findall(r"^\t\t([0-9A-F]{24}) = \{", text, re.M)
check(len(ids_in_text) == len(set(ids_in_text)) == len(objs), "unique ids")

def refs(v):
    if isinstance(v, str):
        if re.fullmatch(r"[0-9A-F]{24}", v): yield v
    elif isinstance(v, dict):
        for x in v.values(): yield from refs(x)
    elif isinstance(v, list):
        for x in v: yield from refs(x)
for k, o in objs.items():
    for r in refs({kk: vv for kk, vv in o.items() if kk != "remoteGlobalIDString"}):
        check(r in objs, "%s (%s) -> missing %s" % (k, o["isa"], r))
check(root["rootObject"] in objs and objs[root["rootObject"]]["isa"] == "PBXProject", "rootObject")

phases = {k: o for k, o in objs.items() if o["isa"].endswith("BuildPhase")}
seen = {}
for pk, p in phases.items():
    for f in p["files"]:
        check(objs[f]["isa"] == "PBXBuildFile", "phase entry not a PBXBuildFile " + f)
        seen[f] = seen.get(f, 0) + 1
for k, o in objs.items():
    if o["isa"] == "PBXBuildFile": check(seen.get(k) == 1, "build file in %s phases: %s" % (seen.get(k), k))

# group tree -> disk
proj = objs[root["rootObject"]]
paths = {}
def walk(gid, base):
    g = objs[gid]
    here = os.path.join(base, g.get("path", "")) if g.get("sourceTree") == "<group>" else base
    for c in g.get("children", []):
        o = objs[c]
        if o["isa"] == "PBXGroup": walk(c, here)
        elif o["isa"] == "PBXFileReference" and o.get("sourceTree") == "<group>":
            p = os.path.join(here, o["path"]); paths[c] = p
            check(os.path.exists(p), "missing on disk: " + os.path.relpath(p, IOS))
walk(proj["mainGroup"], IOS)
for k, o in objs.items():
    if o["isa"] == "PBXFileReference" and o.get("sourceTree") == "<group>":
        check(k in paths, "file ref not in the group tree: " + o["path"])

targets = {objs[t]["name"]: objs[t] for t in proj["targets"]}
def compiled(tname):
    t = targets[tname]; out = set()
    for ph in t["buildPhases"]:
        if objs[ph]["isa"] == "PBXSourcesBuildPhase":
            for bf in objs[ph]["files"]: out.add(os.path.realpath(paths[objs[bf]["fileRef"]]))
    return out
def resources(tname):
    t = targets[tname]; out = set()
    for ph in t["buildPhases"]:
        if objs[ph]["isa"] == "PBXResourcesBuildPhase":
            for bf in objs[ph]["files"]: out.add(os.path.basename(paths[objs[bf]["fileRef"]]))
    return out
for d, tname in (("HeatGuardian", "HeatGuardian"), ("HeatGuardianTests", "HeatGuardianTests")):
    for dp, _, fns in os.walk(os.path.join(IOS, d)):
        for f in fns:
            if f.endswith(".swift"):
                check(os.path.realpath(os.path.join(dp, f)) in compiled(tname), "%s not compiled by %s" % (f, tname))
for r in ("plan.json", "sim_heatwave.json", "htt_chamber.json", "chime.wav", "Assets.xcassets"):
    check(r in resources("HeatGuardian"), "app resource " + r)
for r in ("status_vectors.json", "forecast_vectors.json", "eco_vectors_app.json", "herday_vectors_app.json", "herday_vectors_fw.json"):
    check(r in resources("HeatGuardianTests"), "test resource " + r)

app_cfgs = [objs[c]["buildSettings"] for c in objs[targets["HeatGuardian"]["buildConfigurationList"]]["buildConfigurations"]]
for s in app_cfgs:
    check(s["PRODUCT_BUNDLE_IDENTIFIER"] == "gr.heatguardian.family", "bundle id")
    check(s["CODE_SIGN_STYLE"] == "Automatic", "automatic signing")
    check(s["TARGETED_DEVICE_FAMILY"] == "1", "iPhone only")
    check(os.path.exists(os.path.join(IOS, s["INFOPLIST_FILE"])), "INFOPLIST_FILE path")
for c in objs[proj["buildConfigurationList"]]["buildConfigurations"]:
    check(objs[c]["buildSettings"]["IPHONEOS_DEPLOYMENT_TARGET"] == "26.0", "deployment 26.0")

pl = plistlib.load(open(os.path.join(IOS, "HeatGuardian", "Info.plist"), "rb"))
check("bluetooth-central" in pl.get("UIBackgroundModes", []), "UIBackgroundModes bluetooth-central")
check("Η εφαρμογή" in pl.get("NSBluetoothAlwaysUsageDescription", "") and "The app" in pl["NSBluetoothAlwaysUsageDescription"], "BT usage el+en")
check("UILaunchScreen" in pl, "UILaunchScreen")
for k in ("NSLocationWhenInUseUsageDescription", "NSLocationAlwaysAndWhenInUseUsageDescription"):   # Her Day (Elder mode visits)
    check("Το Heat Guardian" in pl.get(k, "") or "Για να" in pl.get(k, ""), k + " Greek")
    check("iPhone" in pl.get(k, "") and " / " in pl.get(k, ""), k + " Greek / English")

sch = open(os.path.join(IOS, "HeatGuardian.xcodeproj", "xcshareddata", "xcschemes", "HeatGuardian.xcscheme")).read()
for bid in re.findall(r'BlueprintIdentifier = "([0-9A-F]+)"', sch):
    check(bid in proj["targets"], "scheme blueprint " + bid)
import xml.dom.minidom; xml.dom.minidom.parseString(sch)

print("check_xcodeproj: %d objects, %d targets, %d app sources; %s" % (len(objs), len(targets), len(compiled("HeatGuardian")), "OK" if not bad else "%d FAILURES" % bad))
sys.exit(1 if bad else 0)
