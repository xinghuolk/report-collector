from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pdfplumber


@dataclass(kw_only=True)
class RawTableCell:
    row_index: int
    column_index: int
    text: str
    bbox: tuple[float, float, float, float] | None = None
    page_index: int | None = None


@dataclass(kw_only=True)
class RawTableBlock:
    block_id: str
    page_index: int
    page_range: tuple[int, int]
    rows: list[list[str]]
    cells: list[list[RawTableCell]] = field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None
    page_text: str = ""


class PdfTableSource:
    def __init__(self, *, table_settings: dict[str, Any] | None = None) -> None:
        self._table_settings = table_settings or {}

    def extract_raw_table_blocks(
        self,
        *,
        pdf_path: str | None,
        pdf_url: str | None,
    ) -> list[RawTableBlock]:
        with self._open_pdf(pdf_path=pdf_path, pdf_url=pdf_url) as pdf:
            raw_blocks: list[RawTableBlock] = []
            for page in pdf.pages:
                page_number = int(getattr(page, "page_number", len(raw_blocks) + 1))
                page_text = page.extract_text() if hasattr(page, "extract_text") else ""
                page_text = page_text or ""
                extracted_tables, extracted_grids = self._extract_page_tables(page)
                for table_index, table in enumerate(extracted_tables, start=1):
                    extracted_grid = (
                        extracted_grids[table_index - 1]
                        if table_index - 1 < len(extracted_grids)
                        else None
                    )
                    rows = self._table_rows(table, extracted_grid)
                    if not rows:
                        continue
                    cells = self._table_cells(table, rows, page_number=page_number)
                    bbox = self._table_bbox(table, cells)
                    raw_blocks.append(
                        RawTableBlock(
                            block_id=f"{self._document_id(pdf_path, pdf_url)}:page:{page_number}:table:{table_index}",
                            page_index=page_number,
                            page_range=(page_number, page_number),
                            rows=rows,
                            cells=cells,
                            bbox=bbox,
                            page_text=page_text,
                        )
                    )
            return raw_blocks

    def _extract_page_tables(self, page: Any) -> tuple[list[Any], list[list[list[str]]]]:
        tables = page.find_tables(**self._table_settings)
        if tables:
            extracted_grids = self._normalize_grids(page.extract_tables(**self._table_settings))
            return list(tables), extracted_grids

        extracted = page.extract_tables(**self._table_settings)
        return [table for table in extracted if table], self._normalize_grids(extracted)

    def _table_rows(
        self,
        table: Any,
        extracted_grid: list[list[str]] | None,
    ) -> list[list[str]]:
        if hasattr(table, "extract"):
            extracted = table.extract()
            rows = self._normalize_rows(extracted)
            if rows:
                return rows

        if extracted_grid:
            rows = self._normalize_rows(extracted_grid)
            if rows:
                return rows

        if isinstance(table, list):
            return self._normalize_rows(table)

        return []

    def _table_cells(
        self,
        table: Any,
        rows: list[list[str]],
        *,
        page_number: int,
    ) -> list[list[RawTableCell]]:
        candidate_cells = getattr(table, "cells", None)
        if candidate_cells:
            nested_cells = self._normalize_cells(candidate_cells, page_number=page_number)
            if nested_cells:
                return nested_cells

        normalized_cells: list[list[RawTableCell]] = []
        for row_index, row in enumerate(rows):
            normalized_cells.append(
                [
                    RawTableCell(
                        row_index=row_index,
                        column_index=column_index,
                        text=cell,
                        bbox=None,
                        page_index=page_number,
                    )
                    for column_index, cell in enumerate(row)
                ]
            )
        return normalized_cells

    @staticmethod
    def _table_bbox(
        table: Any,
        cells: list[list[RawTableCell]],
    ) -> tuple[float, float, float, float] | None:
        bbox = getattr(table, "bbox", None)
        if bbox is not None:
            return tuple(float(value) for value in bbox)

        points: list[tuple[float, float, float, float]] = [
            cell.bbox for row in cells for cell in row if cell.bbox is not None
        ]
        if not points:
            return None
        x0 = min(point[0] for point in points)
        top = min(point[1] for point in points)
        x1 = max(point[2] for point in points)
        bottom = max(point[3] for point in points)
        return (x0, top, x1, bottom)

    @staticmethod
    def _normalize_rows(raw_rows: Any) -> list[list[str]]:
        rows: list[list[str]] = []
        for row in raw_rows or []:
            normalized_row = [
                "" if cell is None else str(cell).strip()
                for cell in row
            ]
            if any(normalized_row):
                rows.append(normalized_row)
        return rows

    @staticmethod
    def _normalize_grids(
        raw_grids: Any,
    ) -> list[list[list[str]]]:
        normalized_grids: list[list[list[str]]] = []
        for grid in raw_grids or []:
            normalized_grid = PdfTableSource._normalize_rows(grid)
            if normalized_grid:
                normalized_grids.append(normalized_grid)
        return normalized_grids

    def _normalize_cells(
        self,
        raw_cells: Any,
        *,
        page_number: int,
    ) -> list[list[RawTableCell]]:
        if not raw_cells:
            return []

        first_cell = raw_cells[0]
        if isinstance(first_cell, list):
            rows: list[list[RawTableCell]] = []
            for row_index, row in enumerate(raw_cells):
                normalized_row: list[RawTableCell] = []
                for column_index, cell in enumerate(row):
                    if cell is None:
                        continue
                    text = self._cell_text(cell)
                    if not text:
                        continue
                    normalized_row.append(
                        RawTableCell(
                            row_index=row_index,
                            column_index=column_index,
                            text=text,
                            bbox=self._cell_bbox(cell),
                            page_index=page_number,
                        )
                    )
                if normalized_row:
                    rows.append(normalized_row)
            return rows

        return []

    @staticmethod
    def _cell_text(cell: Any) -> str:
        if isinstance(cell, str):
            return cell.strip()
        text = getattr(cell, "text", None)
        if text is not None:
            return str(text).strip()
        return ""

    @staticmethod
    def _cell_bbox(cell: Any) -> tuple[float, float, float, float] | None:
        bbox = getattr(cell, "bbox", None)
        if bbox is not None:
            return tuple(float(value) for value in bbox)
        coordinates = [
            getattr(cell, key, None)
            for key in ("x0", "top", "x1", "bottom")
        ]
        if all(value is not None for value in coordinates):
            return tuple(float(value) for value in coordinates)  # type: ignore[arg-type]
        return None

    @staticmethod
    def _document_id(pdf_path: str | None, pdf_url: str | None) -> str:
        if pdf_path:
            return str(Path(pdf_path))
        if pdf_url:
            return pdf_url
        return "unknown-document"

    @staticmethod
    def _open_pdf(
        *,
        pdf_path: str | None,
        pdf_url: str | None,
    ) -> pdfplumber.PDF:
        if pdf_path is not None:
            return pdfplumber.open(pdf_path)
        if pdf_url is not None:
            response = httpx.get(pdf_url, timeout=30.0)
            response.raise_for_status()
            return pdfplumber.open(BytesIO(response.content))
        raise ValueError("pdf_path or pdf_url is required")
