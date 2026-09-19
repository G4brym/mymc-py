#
# mymc_py package
#
# Python 3 port of "mymc" by Ross Ridge (public domain).  See NOTICE and
# README for the full attribution and license terms (MIT).
#
"""mymc_py - a Python 3 library for manipulating PlayStation 2 memory cards.

This is a Python 3 port of Ross Ridge's ``mymc`` / ``ps2mc`` utilities.  It
reads and writes PS2 memory card images (``.ps2`` files, 512-byte data pages
with 16-byte ECC spare areas) using the exact on-card file system layout:

* superblock ("Sony PS2 Memory Card Format ...", version 1.2)
* indirect FAT (cluster-based allocation, chain end 0xFFFFFFFF)
* hierarchical directories with 512-byte directory entries
* Hamming-code ECC for every page

Typical use::

    import mymc_py
    from mymc_py.ps2mc import ps2mc

    with open("memcard.ps2", "r+b") as f:
        mc = ps2mc(f, ignore_ecc=False)
        root = mc.dir_open(b"/")
        for i in range(2, len(root)):
            ent = root[i]
            if ent[0] & 0x8000:            # DF_EXISTS
                print(ent[8].decode("latin-1"))
        mc.close()

Or use the high-level :func:`mymc_py.builder.build_card` to assemble a card
from uLaunchELF-style folder saves::

    mymc_py.build_card("/path/to/saves", "memcard.ps2", size_mb=16)
"""

from . import ps2mc, ps2mc_dir, ps2mc_ecc, round as _round  # noqa: F401
from .ps2mc import (  # noqa: F401
    ps2mc,
    error,
    io_error,
    corrupt,
    ecc_error,
    path_not_found,
    file_not_found,
    dir_not_found,
    PS2MC_MAGIC,
    PS2MC_FAT_ALLOCATED_BIT,
    PS2MC_FAT_CHAIN_END,
    PS2MC_FAT_CHAIN_END_UNALLOC,
    PS2MC_FAT_CLUSTER_MASK,
    PS2MC_CLUSTER_SIZE,
    PS2MC_STANDARD_PAGE_SIZE,
    PS2MC_STANDARD_PAGES_PER_CARD,
    PS2MC_STANDARD_PAGES_PER_ERASE_BLOCK,
)
from .ps2mc_dir import (  # noqa: F401
    DF_READ,
    DF_WRITE,
    DF_EXECUTE,
    DF_RWX,
    DF_PROTECTED,
    DF_FILE,
    DF_DIR,
    DF_POCKETSTN,
    DF_PSX,
    DF_HIDDEN,
    DF_EXISTS,
    PS2MC_DIRENT_LENGTH,
    mode_is_file,
    mode_is_dir,
    unpack_dirent,
    pack_dirent,
)
from .ps2mc_ecc import (  # noqa: F401
    ECC_CHECK_OK,
    ECC_CHECK_CORRECTED,
    ECC_CHECK_FAILED,
    ecc_calculate,
    ecc_check,
    ecc_calculate_page,
    ecc_check_page,
)
from .builder import build_card, list_saves, validate_name  # noqa: F401

__version__ = "1.0.0"