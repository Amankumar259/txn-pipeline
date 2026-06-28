import pandas as pd
from io import StringIO


def parse_date(val):
    for fmt in ("%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return pd.to_datetime(val, format=fmt).date().isoformat()
        except Exception:
            continue
    return None


def clean_csv(csv_text: str) -> pd.DataFrame:
    df = pd.read_csv(StringIO(csv_text))

    # Normalise column names
    df.columns = [c.strip().lower() for c in df.columns]

    # Normalise dates
    df["date"] = df["date"].astype(str).apply(parse_date)

    # Strip $ from amounts and convert to float
    df["amount"] = (
        df["amount"].astype(str).str.replace("$", "", regex=False).str.strip()
    )
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Uppercase currency and status
    df["currency"] = df["currency"].astype(str).str.upper().str.strip()
    df["status"] = df["status"].astype(str).str.upper().str.strip()

    # Fill missing categories
    df["category"] = df["category"].fillna("Uncategorised")
    df["category"] = df["category"].replace("", "Uncategorised")

    # Remove exact duplicate rows
    df = df.drop_duplicates()

    # Reset index
    df = df.reset_index(drop=True)

    # Init anomaly columns
    df["is_anomaly"] = False
    df["anomaly_reason"] = ""

    return df