from pathlib import Path

import fitz
from pdf_equilibrist.operations.protect import encrypt, decrypt, is_encrypted


def _create_sample_pdf(path: Path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Secret")
    doc.save(str(path))
    doc.close()
    return path


def test_encrypt_decrypt(tmp_path: Path):
    source = tmp_path / "source.pdf"
    encrypted = tmp_path / "encrypted.pdf"

    _create_sample_pdf(source)
    doc = fitz.open(str(source))
    encrypt(doc, encrypted, user_password="user123", owner_password="owner456")
    doc.close()

    enc_doc = fitz.open(str(encrypted))
    assert is_encrypted(enc_doc)
    assert not decrypt(enc_doc, "wrongpass")
    assert decrypt(enc_doc, "user123")
    enc_doc.close()
