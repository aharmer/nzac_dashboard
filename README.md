# NZAC Project Dashboard

A [Streamlit](https://nzac-dashboard.streamlit.app/) dashboard summarising digitisation progress and
related projects for the [New Zealand Arthropod Collection](https://www.landcareresearch.co.nz/tools-and-resources/collections/new-zealand-arthropod-collection-nzac/)
(NZAC), held at Manaaki Whenua – Landcare Research.


## Features

The app has five tabs:

- **Summary** — headline KPIs (specimens digitised, proportion of collection
  digitised, specimens imaged), a chart of cumulative digitisation progress by
  year, and a breakdown by material type (pinned / fluid / slide).
- **Projects** — an overview of the digitisation pipeline, covering the
  RAPIIDlite imaging system and the Chrysalis AI label-reading tool.
- **Digitisation progress by taxa** — a filterable table of holdings and
  digitisation progress, with cascading filters for order, family, origin, and
  material type.
- **Names database** — a publicly viewable, filterable table of accepted names
  and synonymy for NZ arthropod taxa. A small group of logged-in curators can
  add or correct names one at a time or in bulk, and record nomenclatural
  changes (transfers to another genus, synonymies) with "Transfer /
  synonymise", which keeps the old name as a synonym rather than overwriting it.
  See [Names database setup](#names-database-setup) below.
- **Maps** — an interactive map (rendered with [pydeck](https://deckgl.readthedocs.io/))
  plotting all georeferenced specimen localities in the collection.

## Project structure

```
nzac_dashboard/
├── app.py                   # Streamlit app entry point
├── requirements.txt         # Python dependencies
├── .streamlit/
│   ├── config.toml          # Theme configuration
│   └── secrets.toml         # Supabase + editor credentials (gitignored, not in repo)
├── supabase/
│   └── schema.sql           # One-off DDL for the Names database table (Supabase SQL Editor)
├── scripts/
│   ├── hash_password.py     # Generates a bcrypt hash for a new editor's password
│   └── check_password.py    # Diagnostic: checks a password against a stored hash directly
├── assets/
│   ├── NZAC_pare.png        # Header logo
│   └── rapiid.png           # RAPIID image (Projects tab)
└── data/
    ├── mass_digi.csv        # Holdings/digitised counts by order, family, origin, material type
    ├── summary_table.csv    # Headline KPI and material-type summary figures
    ├── annual_progress.csv  # Cumulative specimens digitised by year
    └── georefs.csv          # Georeferenced specimen localities (lat/long)
```

## Running locally

Requires Python 3.11+.

```bash
# Create and activate an environment (conda example)
conda create -n nzac_dashboard python=3.11
conda activate nzac_dashboard

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

You'll also need a `.streamlit/secrets.toml` (gitignored — never committed) for
the Names database tab to work; see [Names database setup](#names-database-setup).

## Updating the data

Each tab reads directly from the CSV files in `data/` — there's no database or
build step. To update the figures shown in the app, edit the relevant CSV and
reload the app (data is cached with `st.cache_data`, so a browser refresh is
enough to pick up changes during local development; restart the app after
deploying updated files in production):

- Headline KPIs and the material-type table on the **Summary** tab →
  `summary_table.csv`
- The digitisation-progress chart on the **Summary** tab → `annual_progress.csv`
- The filterable taxa table → `mass_digi.csv`
- The specimen locality map → `georefs.csv`

## Names database setup

The Names database tab is backed by a [Supabase](https://supabase.com) (hosted
Postgres) project rather than a CSV, since it needs multiple named editors to
be able to add/update records with an audit trail. No IT/admin involvement is
needed — it's a free-tier project under your own account.

**One-off setup:**

1. Create a Supabase project (or use an existing one) and open its
   **SQL Editor**. Paste in and run [`supabase/schema.sql`](supabase/schema.sql)
   to create the `names` table.
2. In **Project Settings → API Keys**, copy the project URL and the **secret**
   (`service_role`) key — not the publishable/anon key, since the app relies on
   its own login rather than Supabase Row Level Security policies.
3. Add them to `.streamlit/secrets.toml`:

   ```toml
   [supabase]
   url = "https://your-project.supabase.co"
   key = "sb_secret_..."
   ```

**Adding an editor:**

1. Run `python scripts/hash_password.py` locally and choose a password for
   them — this prints a bcrypt hash without ever putting the plaintext
   password in a file.
2. Add a block to `.streamlit/secrets.toml`:

   ```toml
   [auth.usernames.jsmith]
   name = "Jane Smith"
   password = "$2b$12$....."   # the hash printed above, not the plaintext
   ```
3. Share the username/password with them out of band (never via this repo).

> **Note (Windows/Git Bash):** `hash_password.py` reads the password with a
> plain, visible `input()` rather than a hidden prompt. Hidden-input prompts
> (`getpass`) don't accept a clipboard paste in some Windows terminals like
> Git Bash/MinTTY — they silently insert the raw Ctrl+V keystroke instead of
> the pasted text, producing a hash of the wrong value with no error. If a
> login ever fails despite a correct password, run
> `python scripts/check_password.py <username>` to check a password directly
> against the stored hash and rule this out.

When deploying, the same `[supabase]` and `[auth]` keys go into that host's
secrets manager (e.g. Streamlit Community Cloud's **Secrets** settings) instead
of a committed file.

Editors log in from within the Names database tab; every add/update is stamped
with `updated_by` (and `created_by` for new rows) plus a timestamp. Updates
overwrite the existing record — there's no version history beyond who/when.

## Deployment

The app is a standard Streamlit app and can be deployed to
[Streamlit Community Cloud](https://streamlit.io/cloud) (point it at `app.py`
in this repo) or any host capable of running `streamlit run app.py`.

## Credits

Created and maintained by [Dr Aaron Harmer](https://www.landcareresearch.co.nz/about-us/our-people/aaron-harmer).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
