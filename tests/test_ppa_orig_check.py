"""packaging/ppa/orig_on_launchpad.py : choix -sa / -sd selon l'orig déjà présent chez Launchpad."""
import hashlib
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "packaging" / "ppa" / "orig_on_launchpad.py"
spec = importlib.util.spec_from_file_location("orig_on_launchpad", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

DSC = """Format: 3.0 (quilt)
Source: pdf-equilibrist
Files:
 0123456789abcdef0123456789abcdef 42 pdf-equilibrist_0.2.0.orig.tar.gz
Checksums-Sha1:
 aaaa 42 pdf-equilibrist_0.2.0.orig.tar.gz
Checksums-Sha256:
 0e15affead4c421154f3ff1bb976aa8103edeb6b4efde355626e9f9573bc9ac6 269015774 pdf-equilibrist_0.2.0.orig.tar.gz
 bbbb 1200 pdf-equilibrist_0.2.0-1~noble1.debian.tar.xz
Homepage: https://example.org
"""


def test_parse_dsc_reads_the_sha256_section_only():
    found = mod.parse_dsc_orig(DSC, "pdf-equilibrist_0.2.0.orig.tar.gz")
    assert found == ("0e15affead4c421154f3ff1bb976aa8103edeb6b4efde355626e9f9573bc9ac6", 269015774)


def test_parse_dsc_unknown_file():
    assert mod.parse_dsc_orig(DSC, "autre.orig.tar.gz") is None


def test_compare_states():
    local = ("abc", 10)
    assert mod.compare(None, local) == "absent"
    assert mod.compare(("abc", 10), local) == "same"
    assert mod.compare(("abd", 10), local) == "different"
    assert mod.compare(("abc", 11), local) == "different"


def test_local_digest(tmp_path):
    f = tmp_path / "x.orig.tar.gz"
    f.write_bytes(b"hello")
    assert mod.local_digest(str(f)) == (hashlib.sha256(b"hello").hexdigest(), 5)
