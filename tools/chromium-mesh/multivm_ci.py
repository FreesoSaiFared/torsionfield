#!/usr/bin/env python3
"""CI proof that Chromium Mesh actions can cross genuinely separate runner VMs."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import mesh

REV = "67505133bc3ef1c64e069cf8de9c853ebf3fb79b"
PASS_KEY = "base/types/pass_key.h"
PROJECTED = "base/types/cxx26_projected_value_t.h"


def compiler():
    cxx = shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        raise RuntimeError("no C++ compiler")
    return cxx


def require_toolchain(expected: str):
    actual = mesh.tool_digest(compiler())
    if actual != expected:
        raise RuntimeError(f"TOOLCHAIN_DIGEST_MISMATCH expected={expected} actual={actual}")
    return actual


def prepare(root: Path, source_root: Path):
    root.mkdir(parents=True, exist_ok=True)
    cas = mesh.CAS(root / "cas")
    cxx = compiler()
    tool_digest = mesh.tool_digest(cxx)
    headers = {
        PASS_KEY: (source_root / PASS_KEY).read_bytes(),
        PROJECTED: (source_root / PROJECTED).read_bytes(),
    }
    deps = mesh.h(mesh.j({k: mesh.h(v) for k, v in headers.items()}))
    bid = mesh.build_id(
        REV,
        deps,
        tool_digest,
        mesh.h(b"github-ubuntu-host"),
        mesh.h(b"multivm-c++20-O0"),
    )
    specs = {
        "a": {
            "source": b'#include "base/types/pass_key.h"\nstruct G{static int m();}; struct P{explicit P(base::PassKey<G>){} }; int G::m(){P p(base::PassKey<G>());return 17;} extern "C" int a(){return G::m();}\n',
            "header": PASS_KEY,
        },
        "b": {
            "source": b'#include "base/types/cxx26_projected_value_t.h"\n#include <type_traits>\n#include <vector>\nstruct F{int operator()(const int&x)const{return x;}}; using T=base::projected_value_t<std::vector<int>::iterator,F>; static_assert(std::is_same_v<T,int>); extern "C" int b(){return 25;}\n',
            "header": PROJECTED,
        },
    }
    actions = {}
    for name, spec in specs.items():
        cc = f"{name}.cc"
        obj = f"{name}.o"
        inputs = {
            cc: cas.put(spec["source"]),
            spec["header"]: cas.put(headers[spec["header"]]),
        }
        act = mesh.action(
            bid,
            [cxx, "-std=c++20", "-O0", "-g", "-I.", cc, "-c", "-o", obj],
            inputs,
            [obj],
        )
        mesh.make_bundle(act, cas, root / f"{name}.tgz")
        actions[name] = act
    meta = {
        "schema": "TORSIONFIELD_CHROMIUM_MESH_MULTIVM/1",
        "build_id": bid,
        "source_revision": REV,
        "toolchain_digest": tool_digest,
        "source_manifest": {k: mesh.h(v) for k, v in headers.items()},
        "actions": actions,
    }
    (root / "metadata.json").write_text(json.dumps(meta, indent=2, sort_keys=True))
    print(json.dumps(meta, indent=2, sort_keys=True))


def worker(root: Path, name: str, worker_id: str):
    meta = json.loads((root / "metadata.json").read_text())
    require_toolchain(meta["toolchain_digest"])
    result = root / f"{name}.result.tgz"
    res = mesh.run_bundle(
        root / f"{name}.tgz",
        result,
        worker_id,
        meta["build_id"],
        root / f"worker-{worker_id}",
    )
    if not res["ok"]:
        raise RuntimeError(res)
    print(json.dumps(res, indent=2, sort_keys=True))


def aggregate(root: Path):
    meta = json.loads((root / "metadata.json").read_text())
    require_toolchain(meta["toolchain_digest"])
    cas = mesh.CAS(root / "aggregate-cas")
    objects = {}
    workers = {}
    for name in ("a", "b"):
        act = meta["actions"][name]
        res = mesh.import_result(root / f"{name}.result.tgz", cas, act)
        if not res["ok"]:
            raise RuntimeError(res)
        objects.update(res["outputs"])
        workers[name] = res["worker_id"]

    cxx = compiler()
    main = b'#include <cstdio>\nextern "C" int a(); extern "C" int b(); int main(){int v=a()+b(); std::printf("%d\\n",v); return v==42?0:1;}\n'
    main_action = mesh.action(
        meta["build_id"],
        [cxx, "-std=c++20", "-O0", "-g", "main.cc", "-c", "-o", "main.o"],
        {"main.cc": cas.put(main)},
        ["main.o"],
    )
    main_bundle = root / "main.tgz"
    main_result = root / "main.result.tgz"
    mesh.make_bundle(main_action, cas, main_bundle)
    mesh.run_bundle(
        main_bundle,
        main_result,
        "aggregate-runner",
        meta["build_id"],
        root / "aggregate-worker",
    )
    main_res = mesh.import_result(main_result, cas, main_action)
    objects.update(main_res["outputs"])

    link = mesh.action(
        meta["build_id"],
        [cxx, "a.o", "b.o", "main.o", "-o", "chromium-mesh-multivm"],
        objects,
        ["chromium-mesh-multivm"],
    )
    link_bundle = root / "link.tgz"
    link_result = root / "link.result.tgz"
    mesh.make_bundle(link, cas, link_bundle)
    link_res0 = mesh.run_bundle(
        link_bundle,
        link_result,
        "aggregate-link-runner",
        meta["build_id"],
        root / "aggregate-link-worker",
    )
    if not link_res0["ok"]:
        raise RuntimeError(link_res0)
    link_res = mesh.import_result(link_result, cas, link)
    exe = root / "chromium-mesh-multivm"
    exe.write_bytes(cas.get(link_res["outputs"]["chromium-mesh-multivm"]))
    exe.chmod(0o755)
    cp = subprocess.run([exe], capture_output=True, text=True)
    if cp.returncode != 0 or cp.stdout.strip() != "42":
        raise RuntimeError(f"mixed-VM executable failed: {cp.returncode} {cp.stdout!r} {cp.stderr!r}")
    proof = {
        "schema": "TORSIONFIELD_CHROMIUM_MESH_MULTIVM_RESULT/1",
        "result": "PASS",
        "build_id": meta["build_id"],
        "source_revision": meta["source_revision"],
        "toolchain_digest": meta["toolchain_digest"],
        "compile_workers": workers,
        "aggregate_worker": "aggregate-runner",
        "link_worker": "aggregate-link-runner",
        "final_digest": mesh.hf(exe),
        "stdout": cp.stdout.strip(),
        "claim": "Objects compiled on separate CI runner VMs with an identical verified compiler identity were admitted by build/action/content identity and linked on a separate aggregate runner.",
        "boundary": "This is not yet an actual GN/Siso Chromium product action or full chrome build.",
    }
    (root / "MULTIVM_RESULT.json").write_text(json.dumps(proof, indent=2, sort_keys=True))
    print(json.dumps(proof, indent=2, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--source-root", type=Path, required=True)
    w = sub.add_parser("worker")
    w.add_argument("--root", type=Path, required=True)
    w.add_argument("--name", choices=("a", "b"), required=True)
    w.add_argument("--worker-id", required=True)
    a = sub.add_parser("aggregate")
    a.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == "prepare":
        prepare(args.root, args.source_root)
    elif args.cmd == "worker":
        worker(args.root, args.name, args.worker_id)
    else:
        aggregate(args.root)


if __name__ == "__main__":
    main()
