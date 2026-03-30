import pytest
import pandas as pd
from datetime import datetime
from etl.transform import (
    clean_column_names,
    handle_nulls,
    deduplicate,
    cast_types,
    apply_scd_type2,
    validate_dataframe,
)


# --- clean_column_names ---

def test_clean_column_names_basic():
    df = pd.DataFrame({"First Name": [1], "LAST NAME": [2], "order_id": [3]})
    result = clean_column_names(df)
    assert list(result.columns) == ["first_name", "last_name", "order_id"]


def test_clean_column_names_strips_whitespace():
    df = pd.DataFrame({"  email  ": ["a@b.com"], " phone": ["123"]})
    result = clean_column_names(df)
    assert "email" in result.columns
    assert "phone" in result.columns


def test_clean_column_names_double_underscore():
    df = pd.DataFrame({"first  name": [1]})
    result = clean_column_names(df)
    # "first  name" -> "first__name" -> "first_name"
    assert "first_name" in result.columns


def test_clean_column_names_does_not_mutate():
    """Make sure we return a copy, not modify in place."""
    original = pd.DataFrame({"Hello World": [1]})
    result = clean_column_names(original)
    assert "Hello World" in original.columns
    assert "hello_world" in result.columns


# --- handle_nulls ---

def test_handle_nulls_drop():
    df = pd.DataFrame({"a": [1, None, 3], "b": ["x", "y", None]})
    result = handle_nulls(df, strategy="drop")
    assert len(result) == 1  # only first row has no nulls


def test_handle_nulls_fill_with_values():
    df = pd.DataFrame({"name": ["alice", None], "age": [25, None]})
    result = handle_nulls(df, strategy="fill", fill_values={"name": "UNKNOWN", "age": 0})
    assert result.iloc[1]["name"] == "UNKNOWN"
    assert result.iloc[1]["age"] == 0


def test_handle_nulls_default_fill():
    """Default fill: 0 for numeric, UNKNOWN for text."""
    df = pd.DataFrame({"score": [10.0, None], "label": ["a", None]})
    result = handle_nulls(df, strategy="fill")
    assert result.iloc[1]["score"] == 0
    assert result.iloc[1]["label"] == "UNKNOWN"


def test_handle_nulls_no_nulls():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    result = handle_nulls(df)
    assert len(result) == 2  # nothing changes


# --- deduplicate ---

def test_deduplicate_removes_dupes():
    df = pd.DataFrame({
        "id": [1, 2, 1, 3],
        "value": ["old", "b", "new", "c"],
    })
    result = deduplicate(df, ["id"])
    assert len(result) == 3
    # should keep last occurrence of id=1
    row = result[result["id"] == 1].iloc[0]
    assert row["value"] == "new"


def test_deduplicate_no_dupes():
    df = pd.DataFrame({"id": [1, 2, 3], "val": ["a", "b", "c"]})
    result = deduplicate(df, ["id"])
    assert len(result) == 3


def test_deduplicate_missing_key_column():
    df = pd.DataFrame({"id": [1, 2], "val": ["a", "b"]})
    with pytest.raises(ValueError, match="Key columns not found"):
        deduplicate(df, ["nonexistent_column"])


# --- cast_types ---

def test_cast_to_int():
    df = pd.DataFrame({"amount": ["100", "200", "300"]})
    result = cast_types(df, {"amount": "int"})
    assert result["amount"].dtype == int


def test_cast_to_datetime():
    df = pd.DataFrame({"date": ["2024-01-01", "2024-06-15"]})
    result = cast_types(df, {"date": "datetime"})
    assert pd.api.types.is_datetime64_any_dtype(result["date"])


def test_cast_missing_column_no_error():
    """Should warn but not crash if column doesn't exist."""
    df = pd.DataFrame({"a": [1]})
    result = cast_types(df, {"nonexistent": "int"})
    assert len(result) == 1  # just passes through


# --- apply_scd_type2 ---

def test_scd2_new_record():
    """Brand new customer should be added with is_current=True."""
    existing = pd.DataFrame({
        "customer_id": ["C001"],
        "email": ["old@test.com"],
        "effective_date": [datetime(2024, 1, 1)],
        "expiry_date": [pd.Timestamp("9999-12-31")],
        "is_current": [True],
    })
    incoming = pd.DataFrame({
        "customer_id": ["C002"],
        "email": ["new@test.com"],
    })
    result = apply_scd_type2(existing, incoming, ["customer_id"], ["email"])
    assert len(result) == 2
    new_row = result[result["customer_id"] == "C002"].iloc[0]
    assert new_row["is_current"] == True


def test_scd2_changed_record():
    """Changed email should close old record and open new one."""
    existing = pd.DataFrame({
        "customer_id": ["C001"],
        "email": ["old@test.com"],
        "effective_date": [datetime(2024, 1, 1)],
        "expiry_date": [pd.Timestamp("9999-12-31")],
        "is_current": [True],
    })
    incoming = pd.DataFrame({
        "customer_id": ["C001"],
        "email": ["updated@test.com"],
    })
    result = apply_scd_type2(existing, incoming, ["customer_id"], ["email"])
    # should have 2 rows: old (closed) and new (current)
    assert len(result) == 2
    old = result[result["email"] == "old@test.com"].iloc[0]
    new = result[result["email"] == "updated@test.com"].iloc[0]
    assert old["is_current"] == False
    assert new["is_current"] == True


def test_scd2_no_change():
    """Same data should not create a new record."""
    existing = pd.DataFrame({
        "customer_id": ["C001"],
        "email": ["same@test.com"],
        "effective_date": [datetime(2024, 1, 1)],
        "expiry_date": [pd.Timestamp("9999-12-31")],
        "is_current": [True],
    })
    incoming = pd.DataFrame({
        "customer_id": ["C001"],
        "email": ["same@test.com"],
    })
    result = apply_scd_type2(existing, incoming, ["customer_id"], ["email"])
    assert len(result) == 1
    assert result.iloc[0]["is_current"] == True


# --- validate_dataframe ---

def test_validate_passes():
    df = pd.DataFrame({"id": [1], "name": ["test"]})
    assert validate_dataframe(df, ["id", "name"]) == True


def test_validate_empty_df():
    df = pd.DataFrame()
    with pytest.raises(ValueError, match="is empty"):
        validate_dataframe(df, ["id"])


def test_validate_missing_columns():
    df = pd.DataFrame({"id": [1]})
    with pytest.raises(ValueError, match="missing required columns"):
        validate_dataframe(df, ["id", "email"])
