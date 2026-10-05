"""Export the Supabase `names` table to CSV.

Run on a schedule by .github/workflows/names-backup.yml, which commits the CSV to
the `backups` branch. Querying the table also counts as activity, which stops the
free-tier Supabase project being paused after 7 idle days.

    SUPABASE_URL=... SUPABASE_KEY=... python scripts/backup_names.py names.csv
"""

import os
import sys

import pandas as pd
from supabase import create_client

PAGE_SIZE = 1000  # Supabase's default per-request row cap


def fetch_all_names(client) -> list[dict]:
    rows, start = [], 0
    while True:
        page = (
            client.table("names").select("*").order("id")
            .range(start, start + PAGE_SIZE - 1).execute().data
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/backup_names.py <output.csv>")
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    rows = fetch_all_names(client)
    pd.DataFrame(rows).to_csv(sys.argv[1], index=False)
    print(f"Exported {len(rows)} rows to {sys.argv[1]}")
