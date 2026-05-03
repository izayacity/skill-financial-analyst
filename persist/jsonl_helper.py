import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator


class JsonlHelper:
    """
    A helper class to perform Read and Write operations on a JSONL file.
    """

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    def write_all(self, data: List[Dict[str, Any]], append: bool = False) -> None:
        """
        Writes a list of dictionaries to a JSONL file.
        If append=True, it adds to the end of the existing file.
        """
        mode = 'a' if append else 'w'

        with open(self.file_path, mode, encoding='utf-8') as f:
            for item in data:
                # Convert the dictionary to a JSON string and write it with a newline
                f.write(json.dumps(item) + '\n')

        action = "Appended" if append else "Wrote"
        print(f"Successfully {action.lower()} {len(data)} records to {self.file_path}")

    def append_one(self, item: Dict[str, Any]) -> None:
        """
        Appends a single dictionary to the JSONL file.
        Highly efficient for streaming or logging.
        """
        with open(self.file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(item) + '\n')

    def read_all(self) -> List[Dict[str, Any]]:
        """
        Reads the entire JSONL file into memory and returns a list of dictionaries.
        Warning: Not recommended for extremely large files (use read_stream instead).
        """
        if not self.file_path.is_file():
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")

        data = []
        with open(self.file_path, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue  # Skip empty lines
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse line {line_number}: {e}")

        return data

    def read_stream(self) -> Iterator[Dict[str, Any]]:
        """
        Yields dictionaries one by one.
        Use this for massive files to keep memory usage low.
        """
        if not self.file_path.is_file():
            raise FileNotFoundError(f"The file {self.file_path} does not exist.")

        with open(self.file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)


# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    db = JsonlHelper("../data/jsonl/data.jsonl")

    # 1. WRITE
    initial_data = [
        {"id": 1, "event": "login", "user": "Alice", "status": "success"},
        {"id": 2, "event": "click", "user": "Bob", "target": "submit_btn"}
    ]
    db.write_all(initial_data, append=False)

    # 2. APPEND A SINGLE RECORD (Great for logs)
    db.append_one({"id": 3, "event": "logout", "user": "Alice", "duration_sec": 450})
    print("\n--- Appended 1 record ---")

    # 3. READ ALL (For smaller datasets)
    print("\n--- Reading Entire File ---")
    all_records = db.read_all()
    for record in all_records:
        print(record)

    # 4. READ STREAM (For massive datasets - memory efficient)
    print("\n--- Streaming File Line-by-Line ---")
    for record in db.read_stream():
        if record.get("user") == "Alice":
            print(f"Found Alice's event: {record['event']}")