from __future__ import annotations

import io
import math
import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import pandas as pd


KEYWORD_MAP = {
    "sales": ["sales", "revenue", "amount", "total", "price"],
    "profit": ["profit", "margin", "gain"],
    "orders": ["orders", "transactions", "count", "qty", "quantity"],
    "customers": ["customer", "client", "user", "buyer"],
    "date": ["date", "time", "month", "day", "year"],
    "region": ["region", "country", "state", "city", "segment"],
    "product": ["product", "item", "sku", "category"],
}


def normalize_column_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def strip_id_suffix(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"(_id|id)$", "", value)
    return value


def is_datetime_like_series(series: pd.Series) -> bool:
    non_null = series.dropna()
    if non_null.empty:
        return False

    sample = non_null.head(min(len(non_null), 50))
    parsed = 0

    for value in sample:
        text = str(value).strip()
        if not text:
            continue
        try:
            from datetime import datetime
            from dateutil.parser import parse as parse_date

            safe_text = text[:-1] + "+00:00" if text.endswith("Z") else text
            datetime.fromisoformat(safe_text)
            parsed += 1
        except ValueError:
            try:
                from dateutil.parser import parse as parse_date
                parse_date(text)
                parsed += 1
            except Exception:
                pass

    return parsed / max(len(sample), 1) > 0.8


def detect_dataframe_type(df: pd.DataFrame) -> Dict[str, Any]:
    numeric_columns = []
    categorical_columns = []
    datetime_columns = []

    for col in df.columns:
        series = df[col]
        normalized = normalize_column_name(col)
        numeric_values = pd.to_numeric(series, errors="coerce")
        if numeric_values.notna().sum() / max(len(series), 1) > 0.8:
            numeric_columns.append(str(col))
            continue

        if is_datetime_like_series(series):
            datetime_columns.append(str(col))
            continue

        if series.nunique(dropna=True) <= min(len(series), 20):
            categorical_columns.append(str(col))
        else:
            categorical_columns.append(str(col))

    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "datetime_columns": datetime_columns,
        "columns": [str(col) for col in df.columns],
    }


def read_uploaded_file(filename: str, raw_bytes: bytes) -> pd.DataFrame:
    lower = filename.lower()
    stream = io.BytesIO(raw_bytes)

    if lower.endswith(".csv"):
        return pd.read_csv(stream)

    if lower.endswith((".xlsx", ".xls", ".xlsm")):
        return pd.read_excel(stream, engine="openpyxl")

    raise ValueError(f"Unsupported file type: {filename}")


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cloned = df.copy()
    cleaned_columns = []
    seen = defaultdict(int)
    for col in cloned.columns:
        base = normalize_column_name(col)
        count = seen[base]
        seen[base] += 1
        cleaned = base if count == 0 else f"{base}_{count + 1}"
        cleaned_columns.append(cleaned)

    cloned.columns = cleaned_columns
    return cloned


def build_join_candidates(dfs: List[pd.DataFrame]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for i in range(len(dfs)):
        left = dfs[i]
        for j in range(i + 1, len(dfs)):
            right = dfs[j]
            left_norm = {normalize_column_name(col): str(col) for col in left.columns}
            right_norm = {normalize_column_name(col): str(col) for col in right.columns}
            join_keys = []
            for key in sorted(set(left_norm) & set(right_norm)):
                join_keys.append((left_norm[key], right_norm[key]))

            if not join_keys:
                for left_key in left_norm:
                    for right_key in right_norm:
                        if strip_id_suffix(left_key) == strip_id_suffix(right_key):
                            join_keys.append((left_norm[left_key], right_norm[right_key]))
                            break

            if join_keys:
                candidates.append({
                    "left_index": i,
                    "right_index": j,
                    "join_keys": join_keys,
                    "left_table": left.columns.tolist(),
                    "right_table": right.columns.tolist(),
                })
    return candidates


def merge_all_tables(dfs: List[pd.DataFrame]) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    if not dfs:
        return pd.DataFrame(), []

    merged = dfs[0].copy()
    join_history: List[Dict[str, Any]] = []

    for index, next_df in enumerate(dfs[1:], start=1):
        left_keys = [normalize_column_name(col) for col in merged.columns]
        right_keys = [normalize_column_name(col) for col in next_df.columns]
        match_candidates = []
        for left_col in merged.columns:
            left_norm = normalize_column_name(left_col)
            for right_col in next_df.columns:
                right_norm = normalize_column_name(right_col)
                if left_norm == right_norm or strip_id_suffix(left_norm) == strip_id_suffix(right_norm):
                    match_candidates.append((str(left_col), str(right_col)))

        if not match_candidates:
            continue

        left_join_col, right_join_col = match_candidates[0]
        merged = merged.merge(
            next_df,
            left_on=left_join_col,
            right_on=right_join_col,
            how="left",
            suffixes=("_left", "_right"),
        )
        join_history.append({
            "from_table": index - 1,
            "to_table": index,
            "join_keys": [left_join_col, right_join_col],
        })

    return merged, join_history


def summarize_table(df: pd.DataFrame) -> Dict[str, Any]:
    numeric_columns = []
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_columns.append(str(col))
        else:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().sum() / max(len(df), 1) > 0.8:
                numeric_columns.append(str(col))
    top_numeric = numeric_columns[:5]
    top_categories = []
    for col in df.columns:
        if str(col) not in top_numeric and df[col].nunique(dropna=True) <= min(len(df), 12):
            top_categories.append(str(col))

    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "numeric_columns": top_numeric,
        "top_categories": top_categories[:5],
    }


def choose_chart_type(prompt: str, df: pd.DataFrame, x_axis: str | None, y_axis: str | None) -> str:
    lower = prompt.lower()
    if any(word in lower for word in ["trend", "over time", "time series", "trend over", "month", "quarter", "year"]):
        return "line"
    if any(word in lower for word in ["share", "percentage", "distribution", "proportion", "compare", "ratio"]):
        return "doughnut"
    if any(word in lower for word in ["relationship", "correlation", "scatter", "impact", "pattern"]):
        return "scatter"
    if x_axis and y_axis:
        return "bar"
    return "bar"


def infer_columns_for_prompt(df: pd.DataFrame, prompt: str) -> Tuple[str | None, str | None]:
    prompt_lower = prompt.lower()
    df_columns = [str(col).lower() for col in df.columns]

    def matches(col_name: str) -> bool:
        return any(keyword in col_name for keyword in [
            "region", "country", "segment", "category", "product", "state", "city", "month", "year", "date", "status"
        ]) or any(word in prompt_lower for word in ["by", "across", "per", "for"]) and any(word in col_name for word in ["region", "country", "segment", "product", "category"])

    x_axis = None
    y_axis = None

    for col in df.columns:
        col_lower = str(col).lower()
        if x_axis is None and matches(col_lower):
            x_axis = str(col)
            continue
        if y_axis is None and pd.api.types.is_numeric_dtype(df[col]):
            y_axis = str(col)
            continue

    if y_axis is None:
        for col in df.columns:
            numeric_series = pd.to_numeric(df[col], errors="coerce")
            if numeric_series.notna().sum() > 0:
                y_axis = str(col)
                break

    if x_axis is None:
        for col in df.columns:
            if str(col).lower() not in ["id", "index"]:
                x_axis = str(col)
                break

    return x_axis, y_axis


def aggregate_for_chart(df: pd.DataFrame, x_axis: str | None, y_axis: str | None) -> List[Dict[str, Any]]:
    if x_axis is None or y_axis is None:
        return []

    temp = df[[x_axis, y_axis]].copy()
    if pd.api.types.is_numeric_dtype(temp[y_axis]):
        grouped = temp.groupby(x_axis, dropna=False)[y_axis].sum().reset_index()
    else:
        converted = pd.to_numeric(temp[y_axis], errors="coerce")
        if converted.notna().sum() > 0:
            temp[y_axis] = converted
            grouped = temp.groupby(x_axis, dropna=False)[y_axis].sum().reset_index()
        else:
            grouped = temp[[x_axis]].value_counts().reset_index(name="count")
            grouped = grouped.rename(columns={0: y_axis})

    labels = grouped[x_axis].fillna("Unknown").astype(str).tolist()
    values = grouped[y_axis].fillna(0).tolist()
    return [{"label": label, "value": float(value) if isinstance(value, (int, float)) else 0} for label, value in zip(labels, values)]


def generate_default_suggestions(df: pd.DataFrame) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    columns = list(df.columns)
    numeric_columns = [col for col in columns if pd.api.types.is_numeric_dtype(df[col]) or pd.to_numeric(df[col], errors="coerce").notna().sum() > 0]
    category_candidates = [col for col in columns if col not in numeric_columns]

    if not numeric_columns:
        numeric_columns = [col for col in columns if col.lower() in ["count", "total", "amount", "sales", "revenue"]]

    metric = numeric_columns[0] if numeric_columns else columns[0] if columns else "value"
    category = category_candidates[0] if category_candidates else columns[0] if columns else "label"
    datetime_cols = [col for col in columns if pd.api.types.is_datetime64_any_dtype(df[col]) or is_datetime_like_series(df[col])]

    if datetime_cols:
        x_axis = datetime_cols[0]
        chart_type = "line"
        data_points = aggregate_for_chart(df, x_axis, metric)
    else:
        x_axis = category
        chart_type = "bar"
        data_points = aggregate_for_chart(df, x_axis, metric)

    suggestions.append({
        "title": f"{metric.title()} by {x_axis.title()}",
        "chart_type": chart_type,
        "x_axis": x_axis,
        "y_axis": metric,
        "data": data_points,
    })

    if len(numeric_columns) > 1:
        second_metric = numeric_columns[1]
        suggestions.append({
            "title": f"{second_metric.title()} by {x_axis.title()}",
            "chart_type": chart_type,
            "x_axis": x_axis,
            "y_axis": second_metric,
            "data": aggregate_for_chart(df, x_axis, second_metric),
        })

    if category_candidates:
        bucket = category_candidates[0]
        counts = df[bucket].value_counts().head(10).reset_index()
        counts.columns = [bucket, "count"]
        suggestions.append({
            "title": f"{bucket.title()} breakdown",
            "chart_type": "doughnut",
            "x_axis": bucket,
            "y_axis": "count",
            "data": [{"label": str(row[bucket]), "value": int(row["count"])} for _, row in counts.iterrows()],
        })

    return suggestions


def build_prompt_chart(df: pd.DataFrame, prompt: str) -> Dict[str, Any]:
    x_axis, y_axis = infer_columns_for_prompt(df, prompt)
    chart_type = choose_chart_type(prompt, df, x_axis, y_axis)
    data_points = aggregate_for_chart(df, x_axis, y_axis) if x_axis and y_axis else []

    if not data_points:
        default_chart = generate_default_suggestions(df)[0]
        return {
            "title": default_chart["title"],
            "chart_type": default_chart["chart_type"],
            "x_axis": default_chart["x_axis"],
            "y_axis": default_chart["y_axis"],
            "data": default_chart["data"],
        }

    title = prompt.strip() or f"{y_axis} by {x_axis}"
    return {
        "title": title,
        "chart_type": chart_type,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "data": data_points,
    }


def analyze_uploaded_files(file_payloads: List[Tuple[str, bytes]], prompt: str = "", generate_all: bool = False) -> Dict[str, Any]:
    if not file_payloads:
        raise ValueError("At least one file is required")

    processed_dataframes = []
    table_metadata = []
    for filename, raw_bytes in file_payloads:
        df = read_uploaded_file(filename, raw_bytes)
        prepared = prepare_dataframe(df)
        processed_dataframes.append(prepared)
        table_metadata.append({
            "filename": filename,
            "profile": detect_dataframe_type(prepared),
            "preview": prepared.head(5).to_dict(orient="records"),
        })

    merged_df, join_history = merge_all_tables(processed_dataframes)
    suggestions = []

    if generate_all or not prompt.strip():
        if not merged_df.empty:
            suggestions = generate_default_suggestions(merged_df)
        else:
            suggestions = generate_default_suggestions(processed_dataframes[0])
    else:
        if not merged_df.empty:
            suggestions = [build_prompt_chart(merged_df, prompt)]
        else:
            suggestions = [build_prompt_chart(processed_dataframes[0], prompt)]

    summary = {
        "file_count": len(processed_dataframes),
        "table_summaries": [summarize_table(df) for df in processed_dataframes],
        "join_history": join_history,
        "row_count": int(len(merged_df)) if not merged_df.empty else sum(len(df) for df in processed_dataframes),
        "column_count": int(len(merged_df.columns)) if not merged_df.empty else sum(len(df.columns) for df in processed_dataframes),
    }

    return {
        "summary": summary,
        "tables": table_metadata,
        "charts": suggestions,
        "top_insights": [
            f"Loaded {len(processed_dataframes)} table(s) and merged {len(join_history)} logical join relationship(s).",
            f"The analysis engine detected {summary['column_count']} columns across the combined dataset.",
            f"The chart engine generated {len(suggestions)} recommendation(s) based on the current prompt and table structure.",
        ],
    }
