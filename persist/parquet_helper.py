import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional


class ParquetHelper:
    """
    A helper class to perform CRUD operations on a local Parquet file.
    Note: Updates and Deletes require rewriting the file due to Parquet's immutability.
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    def _file_exists(self) -> bool:
        return self.file_path.is_file()

    def create(self, data: List[Dict[str, Any]], append: bool = False) -> None:
        """
        Creates a new Parquet file from a list of dictionaries.
        If append=True and the file exists, it appends the new data.
        """
        df = pd.DataFrame(data)

        if append and self._file_exists():
            existing_df = pd.read_parquet(self.file_path, engine='pyarrow')
            df = pd.concat([existing_df, df], ignore_index=True)

        df.to_parquet(self.file_path, engine='pyarrow', index=False)
        print(f"Successfully wrote {len(df)} records to {self.file_path}")

    def read(self, columns: Optional[List[str]] = None, filters: Optional[List] = None) -> pd.DataFrame:
        """
        Reads data from the Parquet file.
        Filters example: [('column_name', '==', 'value')]
        """
        if not self._file_exists():
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")

        df = pd.read_parquet(
            self.file_path,
            engine='pyarrow',
            columns=columns,
            filters=filters
        )
        return df

    def update(self, condition_col: str, condition_val: Any, update_data: Dict[str, Any]) -> None:
        """
        Updates records where condition_col == condition_val with the values in update_data.
        Rewrites the entire file.
        """
        if not self._file_exists():
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")

        df = pd.read_parquet(self.file_path, engine='pyarrow')

        # Create a boolean mask for the rows to update
        mask = df[condition_col] == condition_val
        updated_count = mask.sum()

        if updated_count == 0:
            print(f"No records found matching {condition_col} == {condition_val}. No update performed.")
            return

        # Apply updates
        for col, val in update_data.items():
            if col in df.columns:
                df.loc[mask, col] = val
            else:
                print(f"Warning: Column '{col}' does not exist in the schema. Skipping.")

        # Overwrite file
        df.to_parquet(self.file_path, engine='pyarrow', index=False)
        print(f"Successfully updated {updated_count} records.")

    def delete(self, condition_col: str, condition_val: Any) -> None:
        """
        Deletes records where condition_col == condition_val.
        Rewrites the entire file.
        """
        if not self._file_exists():
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")

        df = pd.read_parquet(self.file_path, engine='pyarrow')

        original_count = len(df)
        # Keep only the rows that DO NOT match the condition
        df = df[df[condition_col] != condition_val]
        deleted_count = original_count - len(df)

        if deleted_count == 0:
            print(f"No records found matching {condition_col} == {condition_val}. No deletion performed.")
            return

        # Overwrite file
        df.to_parquet(self.file_path, engine='pyarrow', index=False)
        print(f"Successfully deleted {deleted_count} records.")


# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    db = ParquetHelper("../data/parquet/users.parquet")

    # 1. CREATE
    initial_data = [
        {"id": 1, "name": "Alice", "role": "Admin", "active": True},
        {"id": 2, "name": "Bob", "role": "User", "active": True},
        {"id": 3, "name": "Charlie", "role": "User", "active": False}
    ]
    db.create(initial_data)

    # 2. READ (with PyArrow pushdown filters)
    print("\n--- Reading Active Users ---")
    active_users = db.read(filters=[('active', '==', True)])
    print(active_users)

    # 3. UPDATE
    print("\n--- Updating Bob's Role ---")
    db.update(condition_col="name", condition_val="Bob", update_data={"role": "Moderator"})
    print(db.read())

    # 4. DELETE
    print("\n--- Deleting Charlie ---")
    db.delete(condition_col="name", condition_val="Charlie")
    print(db.read())