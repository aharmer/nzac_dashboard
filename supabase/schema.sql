-- NZAC Names Database schema.
--
-- Run this once in the Supabase SQL Editor (Project -> SQL Editor -> New query)
-- for the project backing this app. Nothing here needs IT / admin involvement --
-- it's your own Supabase project.
--
-- The app talks to this table using the Supabase *service role* (secret) key,
-- which bypasses Row Level Security entirely. RLS is enabled below anyway, with
-- no policies defined, purely as a safety net: if the project's anon/public key
-- ever leaked, it still could not read or write this table.

create table if not exists names (
    id                  bigint generated always as identity primary key,

    -- Identity / nomenclature
    part_name           text not null,          -- auto-generated: Genus + Species (+ subspecies epithet)
    is_accepted         boolean not null,
    accepted_name       text,                   -- required when is_accepted = false
    is_original         boolean not null,
    original_name       text,                   -- required when is_original = false
    authors             text not null,
    year_of_publication smallint not null,
    authority_and_year  text not null,          -- auto-generated: "Authors, Year", parens if is_original = false
    taxon_rank          text not null check (taxon_rank in ('genus', 'species', 'subspecies')),

    -- Taxonomic hierarchy
    phylum              text not null default 'Animalia',  -- auto-generated
    class               text not null,
    order_name          text not null,          -- "order" is a reserved word, hence order_name
    superfamily         text,
    family              text not null,
    subfamily           text,
    tribe               text,
    genus               text not null,
    subgenus            text,
    species             text,                   -- required when taxon_rank in (species, subspecies)
    full_name           text not null,          -- auto-generated: PartName + " " + AuthorityAndYear

    -- Other attributes
    common_name         text,                   -- semicolon-separated if multiple
    origin              text not null check (origin in ('Endemic', 'Exotic', 'Indigenous', 'Uncertain')),
    occurrence          text not null check (occurrence in
                             ('Absent', 'Captive', 'Eradicated', 'Extinct',
                              'Recorded in error', 'Uncertain', 'Vagrant', 'Wild')),
    doc_threat_status   text,
    nomenclatural_code  text not null default 'ICZN',  -- auto-generated
    taxonomic_notes     text,
    name_variation      text,
    page                text,
    primary_reference   text,

    -- Audit trail
    created_by          text not null,
    created_at          timestamptz not null default now(),
    updated_by          text not null,
    updated_at          timestamptz not null default now()
);

-- PartName is how editors look up an existing record to update (the "LinkedName"
-- field in the old entry-form workflow), so it needs to be unique.
create unique index if not exists names_part_name_key on names (part_name);

alter table names enable row level security;
-- No policies defined: only the service-role key (used server-side by the app)
-- can read/write. The anon/public key gets nothing.
