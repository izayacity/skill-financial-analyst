import csv
from pathlib import Path


def allocate_cash_by_weight(cash_amount, csv_path="../resources/target_portfolio.csv"):
    """
    Allocate a cash amount based on stock weights in a CSV file.

    CSV format expected:
        stock_name,weight
    Where weight can be values like "12%" or "0.12".

    Returns:
        dict[str, float]: {stock_name: allocated_market_value}
    """
    if cash_amount < 0:
        raise ValueError("cash_amount must be non-negative")

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Portfolio file not found: {csv_path}")

    parsed_weights = {}
    with path.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if len(row) < 2:
                continue

            stock_name = row[0].strip()
            raw_weight = row[1].strip().replace(" ", "")
            if not stock_name or not raw_weight:
                continue

            if raw_weight.endswith("%"):
                weight = float(raw_weight[:-1]) / 100.0
            else:
                weight = float(raw_weight)
                if weight > 1:
                    weight = weight / 100.0

            if weight < 0:
                raise ValueError(f"Weight for {stock_name} must be non-negative")
            parsed_weights[stock_name] = weight

    if not parsed_weights:
        return {}

    total_weight = sum(parsed_weights.values())
    if total_weight <= 0:
        raise ValueError("Total weight must be greater than 0")

    # Normalize weights to handle rounding or incomplete totals.
    return {
        stock: round(cash_amount * (weight / total_weight), 2)
        for stock, weight in parsed_weights.items()
    }


if __name__ == "__main__":
    stock_size = allocate_cash_by_weight(150000)
    print(stock_size)