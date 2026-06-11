import pandas as pd
from datetime import datetime


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] TRANSFORM | {msg}")


def clean_column_names(df):
    """Lowercase, strip whitespace, replace spaces with underscores.
    You'd be surprised how many source systems have columns like
    '  Customer Name  ' or 'ORDER ID' - learned this the hard way at Nagarro.
    """
    df = df.copy()
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
    # also get rid of any double underscores that sneak in
    df.columns = [col.replace("__", "_") for col in df.columns]
    return df


def handle_nulls(df, strategy="drop", fill_values=None):
    """Handle null values.
    strategy: 'drop' removes rows, 'fill' uses fill_values dict
    """
    df = df.copy()
    null_counts = df.isnull().sum()
    total_nulls = null_counts.sum()

    if total_nulls == 0:
        log("No nulls found")
        return df

    log(f"Found {total_nulls} null values across {(null_counts > 0).sum()} columns")

    if strategy == "drop":
        before = len(df)
        df = df.dropna()
        log(f"Dropped {before - len(df)} rows with nulls")
    elif strategy == "fill" and fill_values:
        for col, val in fill_values.items():
            if col in df.columns:
                df[col] = df[col].fillna(val)
        log(f"Filled nulls using provided values")
    else:
        # default - fill numeric with 0, strings with 'UNKNOWN'
        for col in df.columns:
            if df[col].dtype in ["float64", "int64"]:
                df[col] = df[col].fillna(0)
            else:
                df[col] = df[col].fillna("UNKNOWN")
        log("Filled nulls with defaults (0 for numeric, UNKNOWN for text)")

    return df


def deduplicate(df, key_columns):
    """Remove duplicates based on key columns, keeping last occurrence.
    In most of our pipelines we get the same record multiple times
    from upstream CDC feeds, so we keep the latest one.
    """
    df = df.copy()
    before = len(df)

    if not all(col in df.columns for col in key_columns):
        missing = [c for c in key_columns if c not in df.columns]
        raise ValueError(f"Key columns not found in dataframe: {missing}")

    df = df.drop_duplicates(subset=key_columns, keep="last")
    removed = before - len(df)

    if removed > 0:
        log(f"Removed {removed} duplicates (keys: {key_columns})")
    else:
        log("No duplicates found")

    return df


def cast_types(df, type_map):
    """Cast columns to specified types.
    type_map example: {'order_id': 'int', 'amount': 'float', 'order_date': 'datetime'}
    """
    df = df.copy()
    for col, dtype in type_map.items():
        if col not in df.columns:
            log(f"Warning: column '{col}' not in dataframe, skipping cast")
            continue
        try:
            if dtype == "datetime":
                df[col] = pd.to_datetime(df[col])
            elif dtype == "int":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            elif dtype == "float":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif dtype == "str":
                df[col] = df[col].astype(str)
            else:
                df[col] = df[col].astype(dtype)
            log(f"Cast {col} -> {dtype}")
        except Exception as e:
            log(f"Failed to cast {col} to {dtype}: {e}")

    return df


def apply_scd_type2(existing_df, incoming_df, key_columns, tracked_columns):
    """Apply SCD Type 2 logic.
    This was the trickiest part of our pipeline at Nagarro.
    Basically: if a tracked column changes, we close the old record
    and open a new one.

    existing_df: current dimension table data (with effective_date, expiry_date, is_current)
    incoming_df: new incoming data
    key_columns: business keys (e.g., ['customer_id'])
    tracked_columns: columns to track for changes (e.g., ['email', 'address'])
    """
    now = datetime.now()
    new_records = []
    updates = []

    # make sure we have the SCD columns
    if "is_current" not in existing_df.columns:
        existing_df = existing_df.copy()
        existing_df["effective_date"] = now
        existing_df["expiry_date"] = pd.Timestamp("9999-12-31")
        existing_df["is_current"] = True

    current = existing_df[existing_df["is_current"] == True].copy()

    for _, incoming_row in incoming_df.iterrows():
        # find matching existing record
        mask = pd.Series([True] * len(current))
        for kc in key_columns:
            mask = mask & (current[kc] == incoming_row[kc])

        match = current[mask]

        if len(match) == 0:
            # brand new record
            new_row = incoming_row.to_dict()
            new_row["effective_date"] = now
            new_row["expiry_date"] = pd.Timestamp("9999-12-31")
            new_row["is_current"] = True
            new_records.append(new_row)
        else:
            # check if anything changed
            existing_row = match.iloc[0]
            changed = False
            for tc in tracked_columns:
                if str(existing_row.get(tc, "")) != str(incoming_row.get(tc, "")):
                    changed = True
                    break

            if changed:
                # close old record
                idx = match.index[0]
                updates.append({
                    "index": idx,
                    "expiry_date": now,
                    "is_current": False,
                })

                # open new record
                new_row = incoming_row.to_dict()
                new_row["effective_date"] = now
                new_row["expiry_date"] = pd.Timestamp("9999-12-31")
                new_row["is_current"] = True
                new_records.append(new_row)

    # apply updates to existing
    result = existing_df.copy()
    for upd in updates:
        result.at[upd["index"], "expiry_date"] = upd["expiry_date"]
        result.at[upd["index"], "is_current"] = upd["is_current"]

    # append new records
    if new_records:
        new_df = pd.DataFrame(new_records)
        result = pd.concat([result, new_df], ignore_index=True)

    log(f"SCD Type 2: {len(new_records)} new/changed records, {len(updates)} closed records")
    return result


def validate_dataframe(df, required_columns, name="dataframe"):
    """Basic validation - check required columns exist and df isn't empty."""
    if df is None or len(df) == 0:
        raise ValueError(f"{name} is empty")

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")

    log(f"Validated {name}: {len(df)} rows, all required columns present")
    return True
