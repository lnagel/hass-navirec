#!/usr/bin/env python3
"""Download fresh fixture data from the Navirec API.

Usage:
    1. Create a .env file with:
       NAVIREC_API_URL=https://api.navirec.com/
       NAVIREC_API_TOKEN=your-api-token

    2. Run:
       uv run python scripts/download_fixtures.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_URL = os.environ.get("NAVIREC_API_URL", "https://api.navirec.com/")
API_TOKEN = os.environ.get("NAVIREC_API_TOKEN", "")
API_VERSION = "1.45.0"
USER_AGENT = "hass-navirec/fixtures-downloader"
STREAM_DURATION_SECONDS = 10
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


@dataclass
class Endpoint:
    """Configuration for an API endpoint."""

    filename: str
    path: str
    per_account: bool = False
    paginated: bool = True


ENDPOINTS = [
    Endpoint("accounts.json", "/accounts/"),
    Endpoint("interpretations.json", "/interpretations/"),
    Endpoint("vehicles.json", "/vehicles/", per_account=True),
    Endpoint("actions.json", "/actions/", per_account=True),
    Endpoint("sensors.json", "/sensors/", per_account=True),
    Endpoint("drivers.json", "/drivers/", per_account=True),
    Endpoint(
        "last_vehicle_states.json",
        "/last_vehicle_states/",
        per_account=True,
        paginated=False,
    ),
]


def get_headers(stream: bool = False) -> dict[str, str]:
    """Get headers for API requests."""
    accept = "application/x-ndjson" if stream else "application/json"
    return {
        "Authorization": f"Token {API_TOKEN}",
        "Accept": f"{accept}; version={API_VERSION}",
        "User-Agent": USER_AGENT,
    }


def parse_link_header(link_header: str) -> dict[str, str]:
    """Parse Link header into a dict of rel -> url."""
    links = {}
    for part in link_header.split(","):
        if match := re.match(r'<([^>]+)>;\s*rel="([^"]+)"', part.strip()):
            url, rel = match.groups()
            links[rel] = url
    return links


async def fetch_json(
    session: aiohttp.ClientSession,
    url: str,
    paginated: bool = True,
) -> list[dict]:
    """Fetch JSON data from a URL, handling pagination and rate limits."""
    all_results = []
    current_url: str | None = url
    page = 1

    while current_url:
        async with session.get(current_url, headers=get_headers()) as response:
            if response.status == 401:
                raise ValueError("Authentication failed. Check your API token.")
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                print(f"  Rate limited. Waiting {retry_after}s...")
                await asyncio.sleep(retry_after)
                continue

            response.raise_for_status()
            data = await response.json()

            if isinstance(data, list):
                all_results.extend(data)
                print(f"  Page {page}: {len(data)} items (total: {len(all_results)})")
            else:
                all_results.append(data)
                print(f"  Page {page}: 1 item")

            if not paginated:
                break

            link_header = response.headers.get("Link", "")
            current_url = parse_link_header(link_header).get("next")
            page += 1

    return all_results


def save_json(path: Path, data: list[dict]) -> None:
    """Save data as JSON to a file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


async def download_endpoint(
    session: aiohttp.ClientSession,
    endpoint: Endpoint,
    account_ids: list[str] | None = None,
) -> None:
    """Download data from an endpoint and save to file."""
    print(f"Downloading {endpoint.filename} from {endpoint.path}...")

    try:
        all_results = []

        if endpoint.per_account and account_ids:
            for account_id in account_ids:
                url = f"{API_URL.rstrip('/')}{endpoint.path}?account={account_id}"
                data = await fetch_json(session, url, endpoint.paginated)
                all_results.extend(data)
                print(f"  Account {account_id}: {len(data)} items")
        else:
            url = f"{API_URL.rstrip('/')}{endpoint.path}"
            all_results = await fetch_json(session, url, endpoint.paginated)

        if all_results:
            save_json(FIXTURES_DIR / endpoint.filename, all_results)
            print(f"  Saved {len(all_results)} items to {endpoint.filename}")

    except aiohttp.ClientError as e:
        print(f"  Error: {e}")
    except ValueError as e:
        print(f"  Error: {e}")


async def download_stream_events(
    session: aiohttp.ClientSession,
    account_ids: list[str],
    duration: int = STREAM_DURATION_SECONDS,
) -> None:
    """Download stream events for a specified duration."""
    filename = "stream_events.ndjson"
    print(f"Downloading {filename} from stream ({duration}s)...")

    all_events: list[str] = []

    for account_id in account_ids:
        url = f"{API_URL.rstrip('/')}/streams/vehicle_states/?account={account_id}"
        print(f"  Connecting to stream for account {account_id}...")

        try:
            timeout = aiohttp.ClientTimeout(total=None, sock_read=duration + 5)
            async with session.get(
                url, headers=get_headers(stream=True), timeout=timeout
            ) as response:
                if response.status == 401:
                    print(f"  Authentication failed for account {account_id}")
                    continue
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    print(f"  Rate limited. Waiting {retry_after}s...")
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                start_time = asyncio.get_event_loop().time()
                event_count = 0

                async for line in response.content:
                    if asyncio.get_event_loop().time() - start_time >= duration:
                        print(f"  Duration reached ({duration}s), stopping...")
                        break

                    if line_text := line.decode("utf-8").strip():
                        all_events.append(line_text)
                        event_count += 1
                        try:
                            event_type = json.loads(line_text).get("event", "unknown")
                            print(f"    Event {event_count}: {event_type}")
                        except json.JSONDecodeError:
                            print(f"    Event {event_count}: (invalid JSON)")

                print(f"  Account {account_id}: {event_count} events")

        except TimeoutError:
            print(f"  Stream timeout for account {account_id}")
        except aiohttp.ClientError as e:
            print(f"  Error streaming account {account_id}: {e}")

    if all_events:
        with open(FIXTURES_DIR / filename, "w", encoding="utf-8") as f:
            f.writelines(event + "\n" for event in all_events)
        print(f"  Saved {len(all_events)} events to {filename}")
    else:
        print("  No events collected")


async def main() -> int:
    """Download all fixtures."""
    if not API_TOKEN:
        print("Error: NAVIREC_API_TOKEN not set. Create a .env file with:")
        print("  NAVIREC_API_URL=https://api.navirec.com/")
        print("  NAVIREC_API_TOKEN=your-api-token")
        return 1

    print(f"API: {API_URL}")
    print(f"Output: {FIXTURES_DIR}\n")
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        # Download endpoints without account filter first (to get account IDs)
        for endpoint in ENDPOINTS:
            if not endpoint.per_account:
                await download_endpoint(session, endpoint)

        # Load account IDs
        accounts_file = FIXTURES_DIR / "accounts.json"
        if not accounts_file.exists():
            print("No accounts.json found, skipping per-account endpoints")
            return 0

        with open(accounts_file, encoding="utf-8") as f:
            accounts = json.load(f)
        account_ids = [acc["id"] for acc in accounts if "id" in acc]
        print(f"\nFound {len(account_ids)} accounts\n")

        # Download per-account endpoints
        for endpoint in ENDPOINTS:
            if endpoint.per_account:
                await download_endpoint(session, endpoint, account_ids)

        # Download stream events
        print()
        await download_stream_events(session, account_ids)

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
