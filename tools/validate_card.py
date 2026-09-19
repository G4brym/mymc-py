#!/usr/bin/env python3
#
# mymc-py: validate a PS2 memory card image (.ps2).
# Part of the mymc-py project (MIT licensed).
#
"""Standalone tool to validate a PS2 ``.ps2`` memory card image.

Checks performed:

* file-system integrity (the reference mymc ``check`` algorithm)
* ECC validity on every page
* a full listing of every save and its files
* if ``--saves-dir`` is given: byte-for-byte comparison of every file on
  the card against the original folder saves

Usage::

    python3 tools/validate_card.py CARD.ps2 [--saves-dir DIR] [--ignore-ecc]

Exit code 0 when every check passes.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

from mymc_py import ps2mc as _ps2mc  # noqa: E402
from mymc_py.ps2mc import ps2mc  # noqa: E402
from mymc_py.ps2mc_dir import DF_EXISTS, DF_DIR, mode_is_file  # noqa: E402

ATTRS = "PS2_MC_Backup_Attributes.BUP.bin"


def main():
    p = argparse.ArgumentParser(
        description="Validate a PS2 .ps2 memory card image.")
    p.add_argument("card", help="path of the .ps2 image")
    p.add_argument("--saves-dir", default=None,
                   help="compare every file byte-for-byte against these "
                        "folder saves")
    p.add_argument("--ignore-ecc", action="store_true",
                   help="do not treat ECC failures as errors")
    args = p.parse_args()

    errors = 0
    with open(args.card, "rb") as f:
        mc = ps2mc(f, args.ignore_ecc)

        ok = mc.check()
        print("filesystem check:", "PASS" if ok else "FAIL")
        if not ok:
            errors += 1

        if not args.ignore_ecc:
            total = mc.clusters_per_card * mc.pages_per_cluster
            bad = 0
            for page in range(total):
                try:
                    mc.read_page(page)
                except _ps2mc.ecc_error:
                    bad += 1
            print("ECC check: %d bad pages of %d" % (bad, total))
            if bad:
                errors += 1

        root = mc.dir_open(b"/")
        card_saves = {}
        for i in range(2, len(root)):
            ent = root[i]
            if not (ent[0] & DF_EXISTS):
                continue
            if not (ent[0] & DF_DIR):
                print("WARNING: non-directory in root:", ent[8])
                errors += 1
                continue
            name = ent[8].decode("latin-1")
            card_saves[name] = []
            d = mc.dir_open(b"/" + ent[8])
            for j in range(2, len(d)):
                fe = d[j]
                if not (fe[0] & DF_EXISTS):
                    continue
                if not mode_is_file(fe[0]):
                    print("WARNING: %s/%s is not a file"
                          % (name, fe[8].decode("latin-1", "replace")))
                    errors += 1
                    continue
                card_saves[name].append(fe[8].decode("latin-1"))
            d.close()
        root.close()

        print("\n%d saves on the card:" % len(card_saves))
        for name in sorted(card_saves):
            print("  %-28s %2d files" % (name, len(card_saves[name])))

        if args.saves_dir:
            expected = sorted(
                f for f in os.listdir(args.saves_dir)
                if os.path.isdir(os.path.join(args.saves_dir, f))
                and not f.startswith("."))
            if sorted(card_saves) != expected:
                print("MISSING/EXTRA saves on card!")
                errors += 1
            compared = 0
            for sname in expected:
                folder = os.path.join(args.saves_dir, sname)
                disk_files = sorted(
                    n for n in os.listdir(folder)
                    if not n.startswith(".") and n != ATTRS)
                card_files = sorted(card_saves.get(sname, []))
                if disk_files != card_files:
                    print("MISMATCH files for %s" % sname)
                    errors += 1
                for fn in disk_files:
                    src = open(os.path.join(folder, fn), "rb").read()
                    ff = mc.open(b"/" + sname.encode("latin-1")
                                 + b"/" + fn.encode("latin-1"), "rb")
                    data = ff.read(len(src) + 16)
                    ff.close()
                    if data != src:
                        print("CONTENT MISMATCH: %s/%s (%d vs %d bytes)"
                              % (sname, fn, len(src), len(data)))
                        errors += 1
                    compared += 1
            print("\ncompared %d files byte-for-byte" % compared)

        free = mc.get_free_space()
        print("\nfree space: %d bytes (%.2f MB) of %.2f MB allocatable"
              % (free, free / 1024 / 1024,
                 mc.get_allocatable_space() / 1024 / 1024))
        mc.close()

    print("\nRESULT:", "ALL CHECKS PASSED" if errors == 0
          else "%d ERROR(S)" % errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())