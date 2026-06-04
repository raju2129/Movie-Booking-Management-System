"""
load_excel.py
─────────────
Loads the BookMyShow_Dataset.xlsx into PostgreSQL.
Run AFTER flask db upgrade (tables must exist).

Usage:
  python load_excel.py --file BookMyShow_Dataset.xlsx
"""

import os
import sys
import argparse
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ── Config ────────────────────────────────────────────────────
DB_URI = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:Rajukullayappa@localhost:5432/movie_booking_db0"
)

# Mapping: Excel sheet name → DB table name
SHEET_TABLE_MAP = {
    "Users":    "dataset_users",
    "Movies":   "movies",
    "Theaters": "theaters",
    "Screens":  "screens",
    "Shows":    "shows",
    "Seats":    "seats",
    "Bookings": "bookings",
    "Payments": "payments",
    "Reviews":  "reviews",
}

# Load order respects foreign keys
LOAD_ORDER = [
    "Users", "Movies", "Theaters", "Screens",
    "Shows", "Seats", "Bookings", "Payments", "Reviews"
]

# ── Helpers ───────────────────────────────────────────────────

def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from string columns and normalize column names."""
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "NaT": None, "None": None})
    return df


def load_sheet(engine, df: pd.DataFrame, table: str, truncate: bool = False):
    df = clean_df(df)
    with engine.begin() as conn:
        if truncate:
            conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            print(f"  ✂️  Truncated '{table}'")
        df.to_sql(table, con=conn, if_exists="append", index=False, method="multi")
    print(f"  ✅ Loaded {len(df):,} rows → '{table}'")


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Load BookMyShow Excel data into PostgreSQL")
    parser.add_argument("--file", default="BookMyShow_Dataset.xlsx", help="Path to Excel file")
    parser.add_argument("--truncate", action="store_true", help="Truncate tables before loading")
    parser.add_argument("--sheet", help="Load only one sheet (e.g. Movies)")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"❌ File not found: {args.file}")
        sys.exit(1)

    print(f"📂 Reading Excel: {args.file}")
    try:
        all_sheets = pd.read_excel(args.file, sheet_name=None, engine="openpyxl")
    except Exception as e:
        print(f"❌ Failed to read Excel: {e}")
        sys.exit(1)

    print(f"   Found sheets: {list(all_sheets.keys())}")

    engine = create_engine(DB_URI)
    print(f"🔌 Connected to database.\n")

    sheets_to_load = [args.sheet] if args.sheet else LOAD_ORDER

    for sheet_name in sheets_to_load:
        # Try exact name, then case-insensitive match
        df = all_sheets.get(sheet_name)
        if df is None:
            for k in all_sheets:
                if k.lower() == sheet_name.lower():
                    df = all_sheets[k]
                    break

        if df is None:
            print(f"  ⚠️  Sheet '{sheet_name}' not found – skipping")
            continue

        table = SHEET_TABLE_MAP.get(sheet_name, sheet_name.lower())
        print(f"📥 Loading sheet '{sheet_name}' → table '{table}'")

        try:
            load_sheet(engine, df, table, truncate=args.truncate)
        except SQLAlchemyError as e:
            print(f"  ❌ Error loading '{table}': {e}")

    print("\n🎉 Data loading complete!")


if __name__ == "__main__":
    main()
