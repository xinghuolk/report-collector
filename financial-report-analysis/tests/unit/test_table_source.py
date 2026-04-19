from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass
class _FakeCell:
    text: str | None
    x0: float
    top: float
    x1: float
    bottom: float
    row_number: int
    column_number: int


class _FakeTable:
    def __init__(self, cells: list[list[_FakeCell]]) -> None:
        self.cells = cells


class _FakePage:
    def __init__(self, page_number: int, tables: list[_FakeTable]) -> None:
        self.page_number = page_number
        self._tables = tables

    def extract_tables(self, **_: object) -> list[list[list[str | None]]]:
        return [
            [[cell.text for cell in row] for row in table.cells]
            for table in self._tables
        ]

    def find_tables(self, **_: object) -> list[_FakeTable]:
        return self._tables


class _FakePdf:
    def __init__(self, pages: list[_FakePage]) -> None:
        self.pages = pages

    def __enter__(self) -> _FakePdf:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def test_extract_raw_table_blocks_preserve_grid_and_page_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financial_report_analysis.ingestion import table_source

    page = _FakePage(
        page_number=7,
        tables=[
            _FakeTable(
                cells=[
                    [
                        _FakeCell("项目", 10.0, 20.0, 40.0, 30.0, 0, 0),
                        _FakeCell("2024年度", 40.0, 20.0, 70.0, 30.0, 0, 1),
                    ],
                    [
                        _FakeCell("营业收入", 10.0, 30.0, 40.0, 40.0, 1, 0),
                        _FakeCell("3,638,911,068.29", 40.0, 30.0, 70.0, 40.0, 1, 1),
                    ],
                ]
            )
        ],
    )

    monkeypatch.setattr(table_source.pdfplumber, "open", lambda *_args, **_kwargs: _FakePdf([page]))

    source = table_source.PdfTableSource()
    blocks = source.extract_raw_table_blocks(pdf_path="/tmp/fake.pdf", pdf_url=None)

    assert len(blocks) == 1
    block = blocks[0]
    assert block.page_index == 7
    assert block.page_range == (7, 7)
    assert block.rows == [["项目", "2024年度"], ["营业收入", "3,638,911,068.29"]]
    assert block.cells[1][1].text == "3,638,911,068.29"
    assert block.bbox == (10.0, 20.0, 70.0, 40.0)

