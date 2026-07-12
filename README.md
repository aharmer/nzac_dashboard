# NZAC Project Dashboard

A [Streamlit](https://nzac-dashboard.streamlit.app/) dashboard summarising digitisation progress and
related projects for the [New Zealand Arthropod Collection](https://www.landcareresearch.co.nz/tools-and-resources/collections/new-zealand-arthropod-collection-nzac/)
(NZAC), held at Manaaki Whenua – Landcare Research.


## Features

The app has four tabs:

- **Summary** — headline KPIs (specimens digitised, proportion of collection
  digitised, specimens imaged), a chart of cumulative digitisation progress by
  year, and a breakdown by material type (pinned / fluid / slide).
- **Projects** — an overview of the digitisation pipeline, covering the
  RAPIIDlite imaging system and the Chrysalis AI label-reading tool.
- **Digitisation progress by taxa** — a filterable table of holdings and
  digitisation progress, with cascading filters for order, family, origin, and
  material type.
- **Maps** — an interactive map (rendered with [pydeck](https://deckgl.readthedocs.io/))
  plotting all georeferenced specimen localities in the collection.

## Project structure

```
nzac_dashboard/
├── app.py                   # Streamlit app entry point
├── requirements.txt         # Python dependencies
├── .streamlit/
│   └── config.toml          # Theme configuration
├── assets/
│   ├── NZAC_pare.png        # Header logo
│   └── rapiid_lite.png      # RAPIIDlite image (Projects tab)
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

## Deployment

The app is a standard Streamlit app and can be deployed to
[Streamlit Community Cloud](https://streamlit.io/cloud) (point it at `app.py`
in this repo) or any host capable of running `streamlit run app.py`.

## Credits

Created and maintained by [Dr Aaron Harmer](https://www.landcareresearch.co.nz/about-us/our-people/aaron-harmer).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
