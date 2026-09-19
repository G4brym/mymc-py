#
# mymc-py builder: assemble a PS2 memory card image from uLaunchELF-style
# folder save backups.  Part of the mymc-py project (MIT licensed).
#
"""High-level helper to build a PS2 ``.ps2`` memory card from folder saves.

The ``uLaunchELF`` folder-save format (a plain folder per save on a USB
stick / mass device) is the most common way PS2 saves are backed up.  Each
folder in ``saves_dir`` becomes one save directory on the card and every
file inside it (except the backup-tool metadata file
``PS2_MC_Backup_Attributes.BUP.bin``) becomes a file of that save::

    saves/
    ├── BESCES-50916RATCHET/        <- save directory
    │   ├── icon.sys
    │   ├── static.ico
    │   └── save0.bin
    ├── BESLES-52541GTA50000/
    │   ├── icon.sys
    │   └── ...
    └── ...

The resulting image is a standard PS2 8/16 MB memory card with 512-byte
pages + 16-byte ECC spare areas (the format used by PCSX2 and AetherSX2).
"""
import os

from .ps2mc import ps2mc, PS2MC_STANDARD_PAGE_SIZE, \
    PS2MC_STANDARD_PAGES_PER_ERASE_BLOCK
from .ps2mc_dir import DF_RWX, DF_DIR, DF_FILE, DF_0400, DF_0080, DF_EXISTS

__all__ = ["build_card", "list_saves", "validate_name", "MODE_DIR",
           "MODE_FILE", "ATTRS_FILENAME", "CARD_SIZES_MB"]

# Standard card sizes in pages (2 pages per 1024-byte cluster).
CARD_SIZES_MB = {8: 16384, 16: 32768}

# Mode flags used on real cards (copied by uLaunchELF from the source card):
# directories 0x8427, files 0x8497.
MODE_DIR = DF_RWX | DF_DIR | DF_0400 | DF_EXISTS
MODE_FILE = DF_RWX | DF_FILE | DF_0400 | DF_0080 | DF_EXISTS

# Metadata file written by uLaunchELF "backup" that is not part of the save.
ATTRS_FILENAME = "PS2_MC_Backup_Attributes.BUP.bin"


def validate_name(raw, what):
    """Validate a PS2 file-system name (<= 32 bytes, no '?', '*', '/' or
    control characters).  Raises ``ValueError`` on invalid names."""
    if len(raw) > 32:
        raise ValueError(
            "%s name too long (%d > 32): %r" % (what, len(raw), raw))
    for ch in raw:
        if ch in (ord('?'), ord('*'), ord('/')) or ch < 32:
            raise ValueError(
                "%s name contains illegal character %r: %r"
                % (what, ch, raw))


def list_saves(saves_dir):
    """Return the sorted list of save folders under ``saves_dir``
    (ignoring hidden files and directories)."""
    return sorted(
        f for f in os.listdir(saves_dir)
        if os.path.isdir(os.path.join(saves_dir, f)) and not f.startswith("."))


def build_card(saves_dir, out_path, size_mb=16, force=False):
    """Create a PS2 memory card image at ``out_path`` containing every
    folder save found under ``saves_dir``.

    :param saves_dir: directory holding the folder saves (one folder per save)
    :param out_path:   path of the ``.ps2`` image to write
    :param size_mb:    card size in MB, 8 or 16 (default 16)
    :param force:      overwrite ``out_path`` if it already exists
    :returns:          the total number of saves added
    :raises ValueError: on invalid names, unsupported size or an existing
                       output file; propagates ``ps2mc`` errors on I/O.
    """
    folders = list_saves(saves_dir)
    if not folders:
        raise ValueError("no save folders found in %s" % saves_dir)
    if size_mb not in CARD_SIZES_MB:
        raise ValueError("card size must be 8 or 16 (MB), got %r" % size_mb)
    if os.path.exists(out_path) and not force:
        raise ValueError("output file already exists: %s" % out_path)

    pages = CARD_SIZES_MB[size_mb]
    with open(out_path, "w+b") as f:
        params = (True, PS2MC_STANDARD_PAGE_SIZE,
                  PS2MC_STANDARD_PAGES_PER_ERASE_BLOCK, pages)
        mc = ps2mc(f, True, params)
        try:
            for folder in folders:
                fpath = os.path.join(saves_dir, folder)
                sname = folder.encode("latin-1")
                validate_name(sname, "save")
                mc.mkdir(b"/" + sname)

                files = sorted(
                    n for n in os.listdir(fpath)
                    if not n.startswith(".") and n != ATTRS_FILENAME
                    and os.path.isfile(os.path.join(fpath, n)))
                for fname in files:
                    fbytes = fname.encode("latin-1")
                    validate_name(fbytes, "file")
                    with open(os.path.join(fpath, fname), "rb") as fin:
                        data = fin.read()
                    ff = mc.open(b"/" + sname + b"/" + fbytes, "wb")
                    try:
                        ff.write(data)
                    finally:
                        ff.close()
                    ent = mc.get_dirent(b"/" + sname + b"/" + fbytes)
                    ent[0] = MODE_FILE
                    mc.set_dirent(b"/" + sname + b"/" + fbytes, ent)
        finally:
            mc.close()
    return len(folders)