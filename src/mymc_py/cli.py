#
# mymc-py command line interface.  Part of the mymc-py project (MIT).
#
"""Command-line interface for the mymc_py library.

Examples::

    # Create a new 8 MB card
    mymc format memcard.ps2 --size 8

    # Assemble a card from uLaunchELF-style folder saves
    mymc build-card memcard.ps2 ./saves --size 16

    # Inspect and manage a card
    mymc ls memcard.ps2 /
    mymc check memcard.ps2
    mymc df memcard.ps2
    mymc extract memcard.ps2 /BESCES-50916RATCHET/icon.sys -o .
"""
import argparse
import os
import sys

from . import ps2mc as _ps2mc
from .builder import build_card as _build_card, CARD_SIZES_MB, \
    list_saves, validate_name, ATTRS_FILENAME, MODE_FILE
from .ps2mc import ps2mc, PS2MC_STANDARD_PAGE_SIZE, \
    PS2MC_STANDARD_PAGES_PER_ERASE_BLOCK, PS2MC_STANDARD_PAGES_PER_CARD
from .ps2mc_dir import DF_EXISTS, DF_DIR


def _open_card(path, mode, ignore_ecc):
    f = open(path, mode)
    return ps2mc(f, ignore_ecc)


def _copy(fout, fin):
    while True:
        s = fin.read(1024 * 1024)
        if not s:
            break
        fout.write(s)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_format(args):
    if not args.force and os.path.exists(args.card):
        raise SystemExit("file exists (use --force to overwrite): %s"
                         % args.card)
    if args.size not in CARD_SIZES_MB:
        raise SystemExit("card size must be 8 or 16 (MB)")
    pages = CARD_SIZES_MB[args.size]
    params = (not args.no_ecc, PS2MC_STANDARD_PAGE_SIZE,
              PS2MC_STANDARD_PAGES_PER_ERASE_BLOCK, pages)
    with open(args.card, "w+b") as f:
        ps2mc(f, True, params).close()
    print("created %s (%d MB)" % (args.card, args.size))


def cmd_build_card(args):
    count = _build_card(args.saves_dir, args.card, size_mb=args.size,
                        force=args.force)
    size = os.path.getsize(args.card)
    print("added %d saves to %s (%.2f MB file, %d MB card)"
          % (count, args.card, size / 1024 / 1024, args.size))


def cmd_ls(args):
    mc = _open_card(args.card, "rb", args.ignore_ecc)
    try:
        target = args.directory.encode("latin-1") if args.directory else b"/"
        dir_ = mc.dir_open(target)
        try:
            for i in range(2 if target == b"/" else 0, len(dir_)):
                ent = dir_[i]
                if not (ent[0] & DF_EXISTS):
                    continue
                kind = "dir " if ent[0] & DF_DIR else "file"
                print("%-5s %10d  %s" % (kind, ent[2],
                                         ent[8].decode("latin-1",
                                                       "replace")))
        finally:
            dir_.close()
    finally:
        mc.close()


def cmd_add(args):
    mc = _open_card(args.card, "r+b", args.ignore_ecc)
    try:
        dest = args.directory.encode("latin-1") if args.directory else b"/"
        if dest != b"/":
            dest += b"/"
        for src in args.files:
            fbytes = os.path.basename(src).encode("latin-1")
            validate_name(fbytes, "file")
            with open(src, "rb") as fin:
                data = fin.read()
            ff = mc.open(dest + fbytes, "wb")
            try:
                ff.write(data)
            finally:
                ff.close()
            ent = mc.get_dirent(dest + fbytes)
            ent[0] = MODE_FILE
            mc.set_dirent(dest + fbytes, ent)
            print("added", os.path.basename(src))
    finally:
        mc.close()


def cmd_mkdir(args):
    mc = _open_card(args.card, "r+b", args.ignore_ecc)
    try:
        for d in args.directories:
            mc.mkdir(d.encode("latin-1"))
            print("made directory", d)
    finally:
        mc.close()


def cmd_remove(args):
    mc = _open_card(args.card, "r+b", args.ignore_ecc)
    try:
        for name in args.files:
            mc.remove(name.encode("latin-1"))
            print("removed", name)
    finally:
        mc.close()


def cmd_delete(args):
    mc = _open_card(args.card, "r+b", args.ignore_ecc)
    try:
        for name in args.directories:
            mc.rmdir(name.encode("latin-1"))
            print("deleted", name)
    finally:
        mc.close()


def cmd_extract(args):
    mc = _open_card(args.card, "rb", args.ignore_ecc)
    try:
        for name in args.files:
            raw = name.encode("latin-1")
            ff = mc.open(raw, "rb")
            try:
                if args.output:
                    out = args.output
                else:
                    out = os.path.basename(name)
                with open(out, "wb") as fo:
                    _copy(fo, ff)
                print("extracted", name, "->", out)
            finally:
                ff.close()
    finally:
        mc.close()


def cmd_check(args):
    mc = _open_card(args.card, "rb", args.ignore_ecc)
    try:
        ok = mc.check()
        print("no errors found" if ok else "errors found")
        return 0 if ok else 1
    finally:
        mc.close()


def cmd_df(args):
    mc = _open_card(args.card, "rb", args.ignore_ecc)
    try:
        free = mc.get_free_space()
        total = mc.get_allocatable_space()
        print("%s: %d bytes free of %d allocatable (%d MB card)"
              % (args.card, free, total, total / 1024 / 1024))
    finally:
        mc.close()


# --------------------------------------------------------------------------
# argument parser
# --------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="mymc",
        description="Manipulate PlayStation 2 memory card images (.ps2). "
                    "Python 3 port of Ross Ridge's mymc.",
    )
    p.add_argument("--version", action="version",
                   version="mymc-py 1.0.0")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    def add_card_arg(sp, help):
        sp.add_argument("card", help=help)

    # format
    sp = sub.add_parser("format", help="create a new memory card image")
    add_card_arg(sp, "path of the .ps2 image to create")
    sp.add_argument("--size", type=int, default=8, choices=sorted(CARD_SIZES_MB),
                    help="card size in MB (default 8)")
    sp.add_argument("--no-ecc", action="store_true",
                    help="create a card without ECC spare data")
    sp.add_argument("-f", "--force", action="store_true",
                    help="overwrite an existing file")
    sp.set_defaults(func=cmd_format)

    # build-card
    sp = sub.add_parser(
        "build-card",
        help="assemble a card from uLaunchELF-style folder saves")
    add_card_arg(sp, "path of the .ps2 image to create")
    sp.add_argument("saves_dir", help="directory of folder saves")
    sp.add_argument("--size", type=int, default=16, choices=sorted(CARD_SIZES_MB),
                    help="card size in MB (default 16)")
    sp.add_argument("-f", "--force", action="store_true",
                    help="overwrite an existing output file")
    sp.set_defaults(func=cmd_build_card)

    # ls
    sp = sub.add_parser("ls", help="list the contents of a directory")
    add_card_arg(sp, "path of the .ps2 image")
    sp.add_argument("directory", nargs="?", default="/",
                    help="directory to list (default /)")
    sp.set_defaults(func=cmd_ls)

    # add
    sp = sub.add_parser("add", help="add files to the card")
    add_card_arg(sp, "path of the .ps2 image")
    sp.add_argument("files", nargs="+", help="local files to add")
    sp.add_argument("-d", "--directory", default=None,
                    help="destination directory on the card")
    sp.set_defaults(func=cmd_add)

    # mkdir
    sp = sub.add_parser("mkdir", help="make directories on the card")
    add_card_arg(sp, "path of the .ps2 image")
    sp.add_argument("directories", nargs="+", help="directories to create")
    sp.set_defaults(func=cmd_mkdir)

    # remove
    sp = sub.add_parser("remove", help="remove files or empty directories")
    add_card_arg(sp, "path of the .ps2 image")
    sp.add_argument("files", nargs="+", help="names to remove")
    sp.set_defaults(func=cmd_remove)

    # delete
    sp = sub.add_parser("delete", help="recursively delete a save directory")
    add_card_arg(sp, "path of the .ps2 image")
    sp.add_argument("directories", nargs="+",
                    help="save directories to delete")
    sp.set_defaults(func=cmd_delete)

    # extract
    sp = sub.add_parser("extract", help="extract files from the card")
    add_card_arg(sp, "path of the .ps2 image")
    sp.add_argument("files", nargs="+",
                    help="card paths to extract (e.g. /SAVE/icon.sys)")
    sp.add_argument("-o", "--output", default=None,
                    help="output path (single file only)")
    sp.set_defaults(func=cmd_extract)

    # check
    sp = sub.add_parser("check", help="check the card for file-system errors")
    add_card_arg(sp, "path of the .ps2 image")
    sp.set_defaults(func=cmd_check)

    # df
    sp = sub.add_parser("df", help="show free space on the card")
    add_card_arg(sp, "path of the .ps2 image")
    sp.set_defaults(func=cmd_df)

    for _name, _sp in sub.choices.items():
        _sp.add_argument("-i", "--ignore-ecc", action="store_true",
                         help="ignore ECC errors while reading")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())