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
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_URL = os.environ.get("NAVIREC_API_URL", "https://api.navirec.com/")
API_TOKEN = os.environ.get("NAVIREC_API_TOKEN", "")
API_VERSION = "1.45.0"
USER_AGENT = "hass-navirec/fixtures-downloader"

# Output directory
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"

# Endpoints to download (paginated)
ENDPOINTS = {
    "accounts.json": "/accounts/",
    "vehicles.json": "/vehicles/",
    "sensors.json": "/sensors/",
    "drivers.json": "/drivers/",
}

# Endpoints that require per-account fetching (no pagination)
PER_ACCOUNT_ENDPOINTS = {
    "last_vehicle_states.json": "/last_vehicle_states/",
}


def get_headers() -> dict[str, str]:
    """Get common headers for API requests."""
    return {
        "Authorization": f"Token {API_TOKEN}",
        "Accept": f"application/json; version={API_VERSION}",
        "User-Agent": USER_AGENT,
    }


def parse_link_header(link_header: str) -> dict[str, str]:
    """Parse Link header into a dict of rel -> url."""
    links = {}
    if not link_header:
        return links

    for part in link_header.split(","):
        match = re.match(r'<([^>]+)>;\s*rel="([^"]+)"', part.strip())
        if match:
            url, rel = match.groups()
            links[rel] = url

    return links


async def fetch_all_pages(
    session: aiohttp.ClientSession,
    url: str,
) -> list[dict]:
    """Fetch all pages of a paginated endpoint and concatenate results."""
    all_results = []
    current_url = url
    page = 1

    while current_url:
        async with session.get(current_url, headers=get_headers()) as response:
            if response.status == 401:
                raise ValueError("Authentication failed. Check your API token.")
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                print(f"  Rate limited. Waiting {retry_after} seconds...")
                await asyncio.sleep(retry_after)
                continue

            response.raise_for_status()
            data = await response.json()

            # Concatenate results from this page
            if isinstance(data, list):
                all_results.extend(data)
                print(f"  Page {page}: fetched {len(data)} items (total: {len(all_results)})")
            else:
                # Some endpoints return a single object or dict
                all_results.append(data)
                print(f"  Page {page}: fetched 1 item")

            # Check for next page via Link header
            link_header = response.headers.get("Link", "")
            links = parse_link_header(link_header)
            current_url = links.get("next")
            page += 1

    return all_results


async def download_endpoint(
    session: aiohttp.ClientSession,
    filename: str,
    endpoint: str,
) -> None:
    """Download data from an endpoint and save to file."""
    url = f"{API_URL.rstrip('/')}{endpoint}"
    print(f"Downloading {filename} from {endpoint}...")

    try:
        data = await fetch_all_pages(session, url)
        output_path = FIXTURES_DIR / filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")  # Ensure file ends with newline

        print(f"  Saved {len(data)} items to {filename}")

    except aiohttp.ClientError as e:
        print(f"  Error downloading {endpoint}: {e}")
    except ValueError as e:
        print(f"  Error: {e}")


async def fetch_single_page(
    session: aiohttp.ClientSession,
    url: str,
) -> list[dict]:
    """Fetch a single page (no pagination)."""
    async with session.get(url, headers=get_headers()) as response:
        if response.status == 401:
            raise ValueError("Authentication failed. Check your API token.")
        if response.status == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            print(f"  Rate limited. Waiting {retry_after} seconds...")
            await asyncio.sleep(retry_after)
            return await fetch_single_page(session, url)

        response.raise_for_status()
        data = await response.json()

        if isinstance(data, list):
            return data
        return [data]


async def download_per_account_endpoint(
    session: aiohttp.ClientSession,
    filename: str,
    endpoint: str,
    account_ids: list[str],
) -> None:
    """Download data from an endpoint that requires per-account fetching."""
    print(f"Downloading {filename} from {endpoint} (per account)...")

    all_results = []
    for account_id in account_ids:
        url = f"{API_URL.rstrip('/')}{endpoint}?account={account_id}"
        try:
            data = await fetch_single_page(session, url)
            all_results.extend(data)
            print(f"  Account {account_id}: fetched {len(data)} items")
        except aiohttp.ClientError as e:
            print(f"  Error fetching account {account_id}: {e}")

    if all_results:
        output_path = FIXTURES_DIR / filename
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Saved {len(all_results)} items to {filename}")


async def main() -> int:
    """Download all fixtures."""
    if not API_TOKEN:
        print("Error: NAVIREC_API_TOKEN environment variable not set.")
        print("Create a .env file with:")
        print("  NAVIREC_API_URL=https://api.navirec.com/")
        print("  NAVIREC_API_TOKEN=your-api-token")
        return 1

    print(f"Using API URL: {API_URL}")
    print(f"Saving fixtures to: {FIXTURES_DIR}")
    print()

    # Ensure fixtures directory exists
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        # First download paginated endpoints (including accounts)
        for filename, endpoint in ENDPOINTS.items():
            await download_endpoint(session, filename, endpoint)

        # Load accounts to get account IDs for per-account endpoints
        accounts_file = FIXTURES_DIR / "accounts.json"
        if accounts_file.exists() and PER_ACCOUNT_ENDPOINTS:
            with open(accounts_file, encoding="utf-8") as f:
                accounts = json.load(f)
            account_ids = [acc["id"] for acc in accounts if "id" in acc]
            print(f"\nFound {len(account_ids)} accounts for per-account endpoints\n")

            # Download per-account endpoints
            for filename, endpoint in PER_ACCOUNT_ENDPOINTS.items():
                await download_per_account_endpoint(
                    session, filename, endpoint, account_ids
                )

    print()
    print("Done!")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
