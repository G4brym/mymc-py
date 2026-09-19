# mymc-py

**Python 3 library and CLI tools for PlayStation 2 memory card images (`.ps2`).**

`mymc-py` reads, writes, formats, inspects and repairs PS2 memory card image
files - and can assemble a working card directly from the **folder saves**
produced by `uLaunchELF` / `OPL` backups.  The resulting `.ps2` images are
fully compatible with **PCSX2** and **AetherSX2** (Android).

This project is a **Python 3 port of Ross Ridge's `mymc`** (public domain) -
the reference implementation of the PS2 memory card file system - plus a
modern CLI, a folder-save→card builder, a validator, and tests.

---

## Table of contents

- [Why this library exists](#why-this-library-exists)
- [Features](#features)
- [Install](#install)
- [Quick start (CLI)](#quick-start-cli)
- [Library API](#library-api)
- [The folder-save format](#the-folder-save-format)
- [The `.ps2` image format](#the-ps2-image-format)
- [Validation & testing](#validation--testing)
- [Compatibility](#compatibility)
- [Limitations](#limitations)

---

## Why this library exists

PS2 memory cards are small NAND-flash cards with a proprietary file system
documented by Ross Ridge in the public-domain
[*PlayStation 2 Memory Card File System*](https://github.com/PCSX2/pcsx2/blob/master/pcsx2/Reference/PS2-MemoryCardFileSystem.htm)
spec.  The most common way players back up their saves is with `uLaunchELF`,
which copies each save to a USB stick as a **folder** (one folder per save,
containing `icon.sys`, the save data files, etc.).

Emulators such as PCSX2/AetherSX2 do **not** consume those folders directly -
they need a raw **`.ps2` memory card image**.  `mymc-py` converts between the
two and provides the full card-manipulation machinery in pure Python.

## Features

- **Format** PS2 memory card images (8 or 16 MB, with or without ECC).
- **Build** a card from `uLaunchELF`-style folder saves (`build-card`).
- **Read / write / list / extract** files and directories on a card.
- **Check** card file-system integrity and **validate ECC** on every page.
- Byte-for-byte faithful: preserves file names, sizes and the directory-entry
  mode flags used by real cards (`0x8427` directories, `0x8497` files).
- Zero runtime dependencies, pure standard library, Python 3.8+.
- `.ps2` output identical to what PCSX2/AetherSX2 expect (512-byte pages +
  16-byte ECC spare areas, "Sony PS2 Memory Card Format" superblock).

## Install

From source (recommended for now):

```bash
git clone https://github.com/G4brym/mymc-py.git
cd mymc-py
pip install -e .
# or, without installing:
PYTHONPATH=src python3 -m mymc_py.cli --help
```

Requirements: **Python 3.8+**, no third-party packages.

## Quick start (CLI)

```bash
# Assemble a 16 MB card from a folder of uLaunchELF saves
mymc build-card memcard.ps2 ./saves --size 16

# Create a blank 8 MB card
mymc format memcard.ps2 --size 8

# Inspect it
mymc ls memcard.ps2 /
mymc df memcard.ps2

# Integrity check
mymc check memcard.ps2

# Manage files/directories
mymc mkdir memcard.ps2 /BESLES-12345GAME1
mymc add  memcard.ps2 icon.sys -d /BESLES-12345GAME1
mymc extract memcard.ps2 /BESLES-12345GAME1/icon.sys -o .
mymc remove memcard.ps2 /BESLES-12345GAME1/icon.sys
mymc delete memcard.ps2 /BESLES-12345GAME1
```

All commands accept `-i/--ignore-ecc` to tolerate ECC damage while reading.

## Library API

```python
import mymc_py
from mymc_py.ps2mc import ps2mc
from mymc_py.builder import build_card

# 1) Assemble a card from folder saves (one folder per save)
build_card("/path/to/saves", "memcard.ps2", size_mb=16)

# 2) Open a card and walk the root directory
with open("memcard.ps2", "rb") as f:
    mc = ps2mc(f, ignore_ecc=False)     # False => ECC is verified
    root = mc.dir_open(b"/")
    for i in range(2, len(root)):
        ent = root[i]
        if ent[0] & mymc_py.DF_EXISTS:
            print(ent[8].decode("latin-1"))   # save directory name
    mc.close()

# 3) Read a save file back
with open("memcard.ps2", "rb") as f:
    mc = ps2mc(f, False)
    fh = mc.open(b"/BESLES-12345GAME1/save0.bin", "rb")
    data = fh.read()            # exact bytes as stored on the card
    fh.close()
    mc.close()
```

See `mymc_py/__init__.py` for the exported API (constants such as
`DF_EXISTS`, `DF_DIR`, `DF_FILE` and the ECC helpers are re-exported there).

## The folder-save format

`uLaunchELF` (and OPL) back up saves to `mass:/` as **folders**:

```
saves/
├── BESCES-50916RATCHET/          ← save directory (name = save name)
│   ├── icon.sys                  ← PS2 save icon metadata (PS2D header)
│   ├── static.ico                ← icon bitmap
│   └── save0.bin                 ← the save data
└── BESLES-52541GTA50000/
    ├── icon.sys
    └── ...
```

`build_card` maps **each folder to one save directory** and copies every file
inside it, except:

- hidden files (`.DS_Store`, `.*`)
- `PS2_MC_Backup_Attributes.BUP.bin` - a backup-tool metadata file written by
  some uLaunchELF "backup" flows; it is **not** part of the save.

The real data file is often named exactly like the folder (e.g.
`BESCES-50916RATCHET`); it is kept as-is and is a real save file.

> **Note for users restoring real backups:** if the original backup omitted
> files (some backup tools only dump part of a save), the rebuilt save will be
> incomplete.  Run `tools/validate_card.py --saves-dir ./saves` after building
> to detect missing files.

## The `.ps2` image format

* 512-byte **pages** (the flash page size), 2 pages per 1024-byte **cluster**.
* Every page carries a 16-byte **spare area** (12 bytes of Hamming-code ECC +
  4 unused), so an 8 MB card image is 16,384 × 528 = **8,650,752 bytes** and a
  16 MB card is **17,301,504 bytes**.
* Superblock at page 0: `"Sony PS2 Memory Card Format "` magic, version
  `1.2.0.0`, geometry, indirect-FAT table and bad-block list.
* Allocation via an **indirect FAT** (chain end `0xFFFFFFFF`, free
  `0x7FFFFFFF`, allocated `0x80000000|next`).
* Directories are 512-byte entries; every directory starts with `.` and `..`.

This is the exact layout implemented by `mymc`/`ps2mc` (Ross Ridge) and
followed by PCSX2's `MemoryCardFile.cpp`, so images are interchangeable
between this library, PCSX2 and AetherSX2.

## Validation & testing

```bash
# Build a card and validate it against the source folders
python3 tools/build_card.py ./saves memcard.ps2 --size 16
python3 tools/validate_card.py memcard.ps2 --saves-dir ./saves

# Run the test suite (no dependencies)
python3 -m unittest discover -s tests -v
```

`tools/validate_card.py` checks: file-system integrity (the reference `mymc`
algorithm), ECC on every page, the save/file listing, and byte-for-byte
equality of every file with the source folders.

## Compatibility

- **PCSX2** - reads `.ps2` images directly; the formatted check
  (`"Sony PS2 Memory Card Format"` magic at offset 0) passes.
- **AetherSX2** (Android) - forks PCSX2's memory-card code and derives the
  card size from the file size, so 8/16 MB images both work.  Place the file
  in the emulator's `memcards` folder (e.g.
  `Android/data/xyz.aethersx2.android/files/memcards/Mcd001.ps2`).
- **Real PS2 / OPL VMC** - standard 8 MB images are the safest choice;
  16 MB third-party cards were supported by many games.

## Limitations

- PSU/MAX/CBS save-file **import/export** is not included (the original
  `ps2save.py` module is not part of this port).  Use folder saves with
  `build-card`, or the raw `add`/`extract` commands.
- The original `mymcsup` C-acceleration module is not bundled; the pure-Python
  ECC implementation is used instead (fast enough for interactive use).
- Card sizes are limited to 8/16 MB by the CLI for clarity; the underlying
  `ps2mc.format()` supports arbitrary page counts if you need more.