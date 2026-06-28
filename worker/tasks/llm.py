import os, json
import pandas as pd
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

VALID_CATEGORIES = [
    "Food", "Shopping", "Travel", "Transport",
    "Utilities", "Cash Withdrawal", "Entertainment", "Other"
]

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
model = genai.GenerativeModel("gemini-1.5-flash")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_gemini(prompt: str) -> str:
    response = model.generate_content(prompt)
    return response.text


def classify_and_summarise(df: pd.DataFrame):
    # --- Step 1: Classify missing/uncategorised transactions in one batch ---
    uncategorised_mask = df["category"].isin(["Uncategorised", "", None])
    uncategorised = df[uncategorised_mask].copy()

    if not uncategorised.empty:
        rows_for_llm = uncategorised[["merchant", "amount", "currency", "notes"]].to_dict(orient="records")
        prompt = f"""
You are a financial transaction classifier.
Classify each transaction into exactly one of these categories:
{', '.join(VALID_CATEGORIES)}

Return ONLY a valid JSON array of strings in the same order as the input.
No explanation. No markdown. Just the JSON array.

Transactions:
{json.dumps(rows_for_llm, indent=2)}
"""
        try:
            raw = _call_gemini(prompt)
            raw = raw.strip().strip("```json").strip("```").strip()
            categories = json.loads(raw)
            for i, idx in enumerate(uncategorised.index):
                cat = categories[i] if i < len(categories) else "Other"
                df.at[idx, "llm_category"] = cat if cat in VALID_CATEGORIES else "Other"
        except Exception as e:
            for idx in uncategorised.index:
                df.at[idx, "llm_failed"] = True

    # --- Step 2: Narrative summary in one LLM call ---
    inr_total = float(df[df["currency"] == "INR"]["amount"].sum())
    usd_total = float(df[df["currency"] == "USD"]["amount"].sum())
    top_merchants = (
        df.groupby("merchant")["amount"].sum()
        .sort_values(ascending=False)
        .head(3)
        .index.tolist()
    )
    anomaly_count = int(df["is_anomaly"].sum())
    category_breakdown = {
        k: float(v) for k, v in df.groupby("category")["amount"].sum().to_dict().items()
    }

    summary_prompt = f"""
You are a financial risk analyst. Analyse these transaction statistics and return ONLY a valid JSON object.
No markdown. No explanation.

Stats:
- Total spend INR: {inr_total:.2f}
- Total spend USD: {usd_total:.2f}
- Top merchants: {top_merchants}
- Anomaly count: {anomaly_count}
- Category breakdown: {json.dumps(category_breakdown)}

Return JSON with keys:
- total_spend_inr (number)
- total_spend_usd (number)
- top_merchants (list of 3 strings)
- anomaly_count (number)
- narrative (2-3 sentence string)
- risk_level ("low", "medium", or "high")
"""
    summary_data = {
        "total_spend_inr": round(inr_total, 2),
        "total_spend_usd": round(usd_total, 2),
        "top_merchants": top_merchants,
        "anomaly_count": anomaly_count,
        "narrative": "Summary generated from transaction data.",
        "risk_level": "medium" if anomaly_count > 3 else "low",
    }

    try:
        raw = _call_gemini(summary_prompt)
        raw = raw.strip().strip("```json").strip("```").strip()
        llm_summary = json.loads(raw)
        summary_data.update(llm_summary)
    except Exception:
        pass  # Fall back to computed summary_data

    return df, summary_data