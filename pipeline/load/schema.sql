-- R3 draft for raw/reference data. R2 approval is required before applying this
-- to Supabase because backend/db/schema.sql and ORM ownership belong to R2.
-- All longitude/latitude values are EPSG:4326 (WGS84).

CREATE TABLE IF NOT EXISTS bus_stops (
    stop_id text PRIMARY KEY, source_stop_id text UNIQUE NOT NULL, name text NOT NULL,
    name_en text, longitude double precision NOT NULL, latitude double precision NOT NULL,
    source_date date
);

CREATE TABLE IF NOT EXISTS stop_routes (
    route_id text NOT NULL, route_no text NOT NULL, stop_id text NOT NULL,
    sequence integer NOT NULL, stop_name text NOT NULL, longitude double precision NOT NULL,
    latitude double precision NOT NULL, source_date date, PRIMARY KEY (route_id, stop_id, sequence)
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id text PRIMARY KEY, source_event_id text NOT NULL, name text NOT NULL, type text NOT NULL,
    status text, genre text, start_date date NOT NULL, end_date date NOT NULL, schedule_text text,
    runtime_text text, price_krw integer, price_unknown boolean NOT NULL, interest_tags text, audience_text text,
    venue_name text NOT NULL, longitude double precision, latitude double precision,
    needs_geocode boolean NOT NULL, source_url text NOT NULL, poster_url text
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id text PRIMARY KEY, source_merchant_id text UNIQUE NOT NULL, name text NOT NULL,
    category text NOT NULL, category_detail text, address text, zone_code text, zone_name text,
    longitude double precision NOT NULL, latitude double precision NOT NULL, inflow_status text NOT NULL
);

CREATE TABLE IF NOT EXISTS floating_population (
    zone_code text NOT NULL, zone_name text NOT NULL, month date NOT NULL,
    daily_average_floating_population integer NOT NULL, PRIMARY KEY (zone_code, month)
);

CREATE TABLE IF NOT EXISTS resident_population (
    zone_code text PRIMARY KEY, zone_name text NOT NULL, reference_date date NOT NULL,
    resident_population integer NOT NULL
);
