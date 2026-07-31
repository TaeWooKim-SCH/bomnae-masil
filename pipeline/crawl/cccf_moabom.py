"""Collect Moabom culture-event cards and merge them with the CCCF snapshot."""

from __future__ import annotations

import argparse
import csv
import html
import re
import time
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


MOABOM_URL = "https://cccf.or.kr/moa"
DEFAULT_DELAY_SECONDS = 0.5


@dataclass(frozen=True)
class Event:
    source: str
    source_id: str
    title: str
    period: str
    address: str
    regions: str
    target_age: str
    category: str
    price: str
    status: str
    image_url: str


class EventCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[Event] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        if "event-item" not in values.get("class", ""):
            return
        self.events.append(Event(
            source="moabom", source_id=values.get("data-id", ""), title=values.get("data-title", ""),
            period=values.get("data-period", ""), address=values.get("data-address", ""),
            regions=values.get("data-regions", ""), target_age=values.get("data-target", ""),
            category=values.get("data-category", ""), price=values.get("data-price", ""),
            status=values.get("data-status", ""), image_url=urljoin(MOABOM_URL, values.get("data-image", "")),
        ))


def post_page(page_index: int, start: str, end: str) -> str:
    body = urlencode({
        "pageIndex": page_index, "searchFromDate": start, "searchToDate": end, "eventStatus": "",
        "searchCategoryCode": "", "searchGenreCode": "", "searchRegionCd": "", "searchPriceTypeCode": "", "searchKeyword": "",
    }).encode("utf-8")
    request = Request(MOABOM_URL, data=body, method="POST", headers={"User-Agent": "bomnae-masil-data-collector/1.0"})
    with urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8", errors="replace")


def page_count(page: str) -> int:
    pages = [int(number) for number in re.findall(r"linkPage\((\d+)\)", page)]
    return max(pages, default=1)


def parse_page(page: str) -> list[Event]:
    parser = EventCardParser()
    parser.feed(page)
    return parser.events


def title_key(value: str) -> str:
    value = re.sub(r"\[[^\]]*\]", "", html.unescape(value))
    return re.sub(r"[^0-9a-z가-힣]", "", value.lower())


def period_dates(value: str) -> tuple[date, date] | None:
    found = re.findall(r"\d{4}-\d{2}-\d{2}", value)
    if not found:
        return None
    start = date.fromisoformat(found[0])
    return start, date.fromisoformat(found[-1])


def overlaps(left: str, right: str) -> bool:
    left_dates, right_dates = period_dates(left), period_dates(right)
    return bool(left_dates and right_dates and left_dates[0] <= right_dates[1] and right_dates[0] <= left_dates[1])


def duplicate(candidate: Event, existing: Event) -> bool:
    candidate_key, existing_key = title_key(candidate.title), title_key(existing.title)
    if not candidate_key or not existing_key or not overlaps(candidate.period, existing.period):
        return False
    return candidate_key in existing_key or existing_key in candidate_key or SequenceMatcher(None, candidate_key, existing_key).ratio() >= 0.88


def read_existing(path: Path) -> list[Event]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [Event(
            source="cccf_home", source_id=row.get("event_id", ""), title=row.get("event_name", ""),
            period=row.get("event_period", ""), address=row.get("event_venue", ""), regions="", target_age="",
            category="", price="", status="", image_url=row.get("poster_image_url", ""),
        ) for row in csv.DictReader(stream)]


def event_row(event: Event, snapshot_date: str) -> dict[str, str]:
    return {
        "snapshot_date": snapshot_date, "source": event.source, "source_event_id": event.source_id, "title": event.title,
        "period": event.period, "address": event.address, "regions": event.regions, "target_age": event.target_age,
        "category": event.category, "price": event.price, "status": event.status, "image_url": event.image_url,
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = list(rows[0]) if rows else list(event_row(Event("", "", "", "", "", "", "", "", "", "", ""), ""))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Moabom culture events and remove existing CCCF duplicates.")
    parser.add_argument("--existing", type=Path, required=True, help="existing ongoing_events.csv from cccf.or.kr/home")
    parser.add_argument("--start", default="2026-08-01")
    parser.add_argument("--end", default="2026-12-31")
    parser.add_argument("--snapshot-date", required=True, help="fixed collection date, YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path, default=Path("snapshots/cccf_moabom"))
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.start) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.end):
        raise SystemExit("--start and --end must use YYYY-MM-DD")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.snapshot_date):
        raise SystemExit("--snapshot-date must use YYYY-MM-DD")

    output_dir = args.output_dir
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    first_page = post_page(1, args.start, args.end)
    pages = page_count(first_page)
    events = parse_page(first_page)
    (raw_dir / "page_1.html").write_text(first_page, encoding="utf-8")
    for page_index in range(2, pages + 1):
        time.sleep(max(args.delay, 0))
        page = post_page(page_index, args.start, args.end)
        (raw_dir / f"page_{page_index}.html").write_text(page, encoding="utf-8")
        events.extend(parse_page(page))

    unique_moabom: list[Event] = []
    for event in events:
        if not any(duplicate(event, prior) for prior in unique_moabom):
            unique_moabom.append(event)
    existing = read_existing(args.existing)
    new_events = [event for event in unique_moabom if not any(duplicate(event, prior) for prior in existing)]
    # The original CCCF CSV has no category column.  Its duplicated Moabom
    # card is the same public event, so use that card only to enrich fields
    # absent from the original snapshot while retaining its source/event ID.
    enriched_existing: list[Event] = []
    for event in existing:
        match = next((candidate for candidate in unique_moabom if duplicate(candidate, event)), None)
        if match is None:
            enriched_existing.append(event)
            continue
        enriched_existing.append(Event(
            source=event.source, source_id=event.source_id, title=event.title, period=event.period,
            address=event.address or match.address, regions=match.regions, target_age=match.target_age,
            category=match.category, price=match.price, status=match.status, image_url=event.image_url or match.image_url,
        ))
    write_csv(output_dir / "moabom_events_all.csv", [event_row(event, args.snapshot_date) for event in unique_moabom])
    write_csv(output_dir / "moabom_events_new_excluding_existing.csv", [event_row(event, args.snapshot_date) for event in new_events])
    write_csv(output_dir / "events_merged_deduplicated.csv", [event_row(event, args.snapshot_date) for event in [*enriched_existing, *new_events]])
    print(f"pages={pages} moabom_unique={len(unique_moabom)} duplicates_removed={len(unique_moabom) - len(new_events)} merged={len(existing) + len(new_events)}")


if __name__ == "__main__":
    main()
