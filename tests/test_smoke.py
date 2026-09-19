#
# mymc-py smoke tests.  Part of the mymc-py project (MIT licensed).
#
"""Smoke tests for the mymc_py library and builder.

Run with::

    python3 -m unittest discover -s tests -v
    # or (from the repo root, with the package installed):
    python3 -m unittest tests.test_smoke -v
"""
import os
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from mymc_py import build_card, ps2mc  # noqa: E402
from mymc_py.builder import list_saves  # noqa: E402
from mymc_py.ps2mc import ps2mc as Ps2mc  # noqa: E402
from mymc_py.ps2mc_dir import DF_EXISTS, DF_DIR, mode_is_file  # noqa: E402
from mymc_py.ps2mc_ecc import ecc_calculate_page  # noqa: E402

MAGIC = b"Sony PS2 Memory Card Format"


def make_fake_save(root, name, files):
    """Create a folder-save with the given files (name -> bytes)."""
    folder = os.path.join(root, name)
    os.makedirs(folder, exist_ok=True)
    for fname, data in files.items():
        with open(os.path.join(folder, fname), "wb") as f:
            f.write(data)


class SmokeTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mymc_py_test_")
        self.saves = os.path.join(self.tmp, "saves")
        os.makedirs(self.saves)
        make_fake_save(self.saves, "BESLES-AAA10000",
                       {"icon.sys": b"PS2D" + b"\x00" * 960,
                        "save0.bin": os.urandom(4096)})
        make_fake_save(self.saves, "BESCES-BBB20000",
                       {"icon.sys": b"PS2D" + b"\x00" * 960,
                        "static.ico": os.urandom(2048),
                        "slot.dat": os.urandom(3000)})
        self.card = os.path.join(self.tmp, "memcard.ps2")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_card_roundtrip(self):
        build_card(self.saves, self.card, size_mb=8)
        self.assertTrue(os.path.exists(self.card))
        # PCSX2/AetherSX2 formatted check: magic at offset 0
        with open(self.card, "rb") as f:
            self.assertEqual(f.read(27), MAGIC)

        with open(self.card, "rb") as f:
            mc = Ps2mc(f, False)  # ECC checking on
            self.assertTrue(mc.check())
            # byte-for-byte comparison
            for sname in list_saves(self.saves):
                d = mc.dir_open(b"/" + sname.encode("latin-1"))
                names = [e[8].decode("latin-1") for e in d
                         if e[0] & DF_EXISTS and not e[0] & DF_DIR]
                d.close()
                folder = os.path.join(self.saves, sname)
                self.assertEqual(sorted(names),
                                 sorted(n for n in os.listdir(folder)
                                        if not n.startswith(".")))
                for fname in names:
                    with open(os.path.join(folder, fname), "rb") as fo:
                        src = fo.read()
                    ff = mc.open(b"/" + sname.encode("latin-1")
                                 + b"/" + fname.encode("latin-1"), "rb")
                    data = ff.read(len(src) + 16)
                    ff.close()
                    self.assertEqual(data, src)
            mc.close()

    def test_ecc_valid_on_all_pages(self):
        build_card(self.saves, self.card, size_mb=8)
        with open(self.card, "rb") as f:
            mc = Ps2mc(f, True)
            mc.ignore_ecc = False
            for p in range(mc.clusters_per_card * mc.pages_per_cluster):
                mc.read_page(p)  # raises ecc_error on failure
            mc.close()

    def test_format_add_extract(self):
        with open(self.card, "w+b") as f:
            params = (True, 512, 16, 16384)
            mc = Ps2mc(f, True, params)
            mc.mkdir(b"/MYSAVE")
            data = b"hello world" * 100
            ff = mc.open(b"/MYSAVE/DATA.BIN", "wb")
            try:
                ff.write(data)
            finally:
                ff.close()
            mc.close()

        with open(self.card, "rb") as f:
            mc = Ps2mc(f, False)
            ff = mc.open(b"/MYSAVE/DATA.BIN", "rb")
            self.assertEqual(ff.read(2000), data)
            ff.close()
            mc.close()


if __name__ == "__main__":
    unittest.main()