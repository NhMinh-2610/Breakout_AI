from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import pytest

from breakout_ai.books import BookError, BookLibrary, extract_pages
from breakout_ai.storage import Store


def pdf_bytes(texts, encrypted=False):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})})})
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("ascii"))
            page.replace_contents(stream)
    if encrypted:
        writer.encrypt("test-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_extraction_preserves_physical_page_references(store):
    library = BookLibrary(store)
    library.ingest("book.pdf", pdf_bytes(["Financial statements and cash flow.", "Margin of safety and intrinsic value."]), "Finance book", "Author")
    passage = library.search("biên an toàn")[0]
    assert passage.page == 2 and passage.title == "Finance book"
    assert "trang PDF 2" in passage.citation()["source_title"]


def test_markdown_has_passage_location_instead_of_invented_page(store):
    library = BookLibrary(store)
    library.ingest("../../book.md", "Biên an toàn margin of safety".encode())
    passage = library.search("margin of safety")[0]
    assert passage.page is None and "đoạn" in passage.citation()["source_title"]
    assert library.documents()[0]["filename"] == "book.md"


def test_duplicate_content_is_not_indexed_twice(store):
    library = BookLibrary(store)
    first, created = library.ingest("book.txt", b"Margin of safety and valuation.")
    second, duplicate = library.ingest("renamed.txt", b"Margin of safety and valuation.")
    assert created and not duplicate and first == second
    assert len(library.documents()) == 1


def test_book_search_and_deletion_are_workspace_scoped(settings, store):
    library = BookLibrary(store)
    identifier, _ = library.ingest("book.txt", b"Margin of safety.")
    other = BookLibrary(Store(settings.database_path, "other"))
    assert other.documents() == other.search("margin") == []
    other.delete(identifier)
    assert library.search("margin")
    library.delete(identifier)
    assert library.documents() == library.search("margin") == []


@pytest.mark.parametrize("name,data", [("scan.pdf", pdf_bytes([""])), ("locked.pdf", pdf_bytes(["Text"], encrypted=True)), ("broken.pdf", b"not a pdf"), ("book.exe", b"content"), ("book.txt", b"\xff\xfe")])
def test_unsupported_unreadable_or_scanned_inputs_fail_without_indexing(store, name, data):
    library = BookLibrary(store)
    with pytest.raises(BookError):
        library.ingest(name, data)
    assert library.documents() == []


def test_library_limit_is_enforced_atomically(store, monkeypatch):
    import breakout_ai.books as module
    monkeypatch.setattr(module, "MAX_WORKSPACE_CHUNKS", 1)
    library = BookLibrary(store)
    library.ingest("first.txt", b"First document margin of safety.")
    with pytest.raises(BookError):
        library.ingest("second.txt", b"Second document valuation.")
    assert len(library.documents()) == 1
