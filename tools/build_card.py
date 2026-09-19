#!/usr/bin/env python3
#
# mymc-py: build a PS2 memory card image from uLaunchELF-style folder saves.
# Part of the mymc-py project (MIT licensed).
#
"""Standalone tool to assemble a ``.ps2`` memory card from folder saves.

Each subfolder of ``SAVES_DIR`` is treated as one save directory; every
file in it (except the backup-tool metadata file
``PS2_MC_Backup_Attributes.BUP.bin``) becomes a file of that save.

Usage::

    python3 tools/build_card.py SAVES_DIR OUTPUT.ps2 [--size 8|16]

Example::

    python3 tools/build_card.py ./saves memcard.ps2 --size 16
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

from mymc_py.builder import build_card  # noqa: E402


def main():
    p = argparse.ArgumentParser(
        description="Build a PS2 .ps2 memory card from uLaunchELF-style "
                    "folder saves.")
    p.add_argument("saves_dir", help="directory containing the folder saves")
    p.add_argument("output", help="path of the .ps2 image to create")
    p.add_argument("--size", type=int, default=16, choices=[8, 16],
                  help="card size in MB (default 16)")
    p.add_argument("-f", "--force", action="store_true",
                  help="overwrite an existing output file")
    args = p.parse_args()

    count = build_card(args.saves_dir, args.output, size_mb=args.size,
                       force=args.force)
    size = os.path.getsize(args.output)
    print("added %d saves to %s (%.2f MB file, %d MB card)"
          % (count, args.output, size / 1024 / 1024, args.size))


if __name__ == "__main__":
    main()