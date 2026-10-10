"""Execute the named SQL blocks in sql/kpis.sql."""

from __future__ import annotations

import re
import sqlite3

import pandas as pd

from pipeline.config import SQL_DIR


def parse_named_sql(text: str) -> list[tuple[str, str]]:
    marks = list(re.finditer(r"(?m)^-- @name\s+(\S+)\s*$", text))
    blocks: list[tuple[str, str]] = []
    for index, mark in enumerate(marks):
        start = mark.end()
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        body = text[start:end].strip().rstrip(";").strip()
        # executescript wants the semicolons that separate statements inside a block.
        raw = text[start:end].strip()
        blocks.append((mark.group(1), raw if mark.group(1).startswith("_") else body))
    return blocks


def run_kpis(db_path) -> dict[str, pd.DataFrame]:
    blocks = parse_named_sql((SQL_DIR / "kpis.sql").read_text())
    results: dict[str, pd.DataFrame] = {}
    with sqlite3.connect(db_path) as conn:
        for name, sql in blocks:
            if name.startswith("_"):
                conn.executescript(sql)
                continue
            results[name] = pd.read_sql_query(sql, conn)
    return results
