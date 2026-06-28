import pandas as pd

DOMESTIC_MERCHANTS = {"swiggy", "ola", "irctc", "zomato", "bigbasket", "blinkit"}


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    # Statistical outlier: amount > 3x account median
    medians = df.groupby("account_id")["amount"].median()
    for idx, row in df.iterrows():
        acc_median = medians.get(row["account_id"], None)
        if acc_median and pd.notna(row["amount"]) and row["amount"] > 3 * acc_median:
            df.at[idx, "is_anomaly"] = True
            reason = df.at[idx, "anomaly_reason"] or ""
            df.at[idx, "anomaly_reason"] = (
                reason + f"Amount {row['amount']} exceeds 3x account median ({acc_median:.2f}). "
            ).strip()

    # Currency mismatch: USD on domestic merchant
    for idx, row in df.iterrows():
        merchant_lower = str(row.get("merchant", "")).lower()
        if row["currency"] == "USD" and merchant_lower in DOMESTIC_MERCHANTS:
            df.at[idx, "is_anomaly"] = True
            reason = df.at[idx, "anomaly_reason"] or ""
            df.at[idx, "anomaly_reason"] = (
                reason + f"USD currency on domestic merchant '{row['merchant']}'. "
            ).strip()

    return df