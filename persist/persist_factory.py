from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .jsonl_helper import JsonlHelper
from .parquet_helper import ParquetHelper


DataInput = Union[Dict[str, Any], List[Dict[str, Any]], pd.DataFrame]


class PersistFactory:
    """
    Unified local persistence interface for `jsonl` and `parquet`.
    """

    def __init__(self, fmt: str, file_path: str):
        normalized = fmt.strip().lower()
        if normalized not in {"jsonl", "parquet"}:
            raise ValueError("Unsupported format. Use 'jsonl' or 'parquet'.")

        self.format = normalized
        self.file_path = file_path
        self._helper = JsonlHelper(file_path) if normalized == "jsonl" else ParquetHelper(file_path)

    def write(self, data: DataInput, append: bool = False) -> None:
        """
        Write data into local file.
        Accepted input:
        - dict
        - list[dict]
        - pandas.DataFrame
        """
        records = self._to_records(data)

        if self.format == "jsonl":
            self._helper.write_all(records, append=append)
            return

        self._helper.create(records, append=append)

    def read(
        self,
        columns: Optional[List[str]] = None,
        filters: Optional[List] = None,
        as_dataframe: bool = False,
    ) -> Union[List[Dict[str, Any]], pd.DataFrame]:
        """
        Read data from local file.

        For parquet:
        - supports `columns` and `filters`
        - returns DataFrame by default

        For jsonl:
        - `columns` and `filters` are ignored
        - returns list[dict] by default
        - set as_dataframe=True to return a DataFrame
        """
        if self.format == "jsonl":
            rows = self._helper.read_all()
            if as_dataframe:
                return pd.DataFrame(rows)
            return rows

        df = self._helper.read(columns=columns, filters=filters)
        if as_dataframe:
            return df
        return df

    @staticmethod
    def _to_records(data: DataInput) -> List[Dict[str, Any]]:
        if isinstance(data, pd.DataFrame):
            return data.to_dict(orient="records")
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            if not all(isinstance(item, dict) for item in data):
                raise TypeError("List input must contain dictionaries only.")
            return data
        raise TypeError("data must be a dict, list of dicts, or pandas.DataFrame.")
