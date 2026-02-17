import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
import logging

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

# Create a logger
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Local cache of remote NAAN registry data
naan_registry_cache = {}

# Derived data structure from NAAN registry cache
ark_root_resolver_map = {}


# Configuration
DATA_DIR = Path("naan_registry_cache")
DATA_DIR.mkdir(exist_ok=True)


def get_latest_naan_registry_cache_file() -> Path | None:
    """Find the most recent cached JSON file of the NAAN Registry."""
    cache_files = list(DATA_DIR.glob("data_*.json"))
    return max(cache_files, key=lambda p: p.stat().st_mtime) if cache_files else None


def is_cache_valid(cache_file: Path, interval_seconds: int) -> bool:
    """Check if the cache file was written less than `interval_seconds` seconds ago."""
    if not cache_file.exists():
        return False
    file_age = datetime.now(timezone.utc).timestamp() - cache_file.stat().st_mtime
    return file_age < interval_seconds


def load_from_cache(cache_file: Path) -> dict:
    """Load data from the cache file"""
    with open(cache_file, "r") as f:
        return json.load(f)


def save_data_to_cache(data: dict) -> Path:
    """Save data dict to a timestamped JSON file"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    cache_file = DATA_DIR / f"data_{timestamp}.json"
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)
    return cache_file


async def download_json_data_from_url_to_dict(url: str) -> dict:
    """Download JSON from URL"""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def ensure_up_to_date_naan_registry_cache(
    url: str = "https://cdluc3.github.io/naan_reg_priv/naan_records.json",
    interval_seconds: int = (60 * 60 * 24),
    force_download: bool = False,
):
    """Download NAAN Registry JSON from URL and update `naan_registry_cache` closure."""
    cache_file = get_latest_naan_registry_cache_file()
    try:
        # Use cache if valid and not forcing download
        if (
            not force_download
            and cache_file
            and is_cache_valid(cache_file, interval_seconds)
        ):
            data = load_from_cache(cache_file)
            logger.info(f"Loaded NAAN Registry from file cache: {cache_file.name}")
        else:
            # Download fresh data and save to cache
            data = await download_json_data_from_url_to_dict(url)
            cache_file = save_data_to_cache(data)
            logger.info(
                f"Downloaded NAAN Registry and saved to file cache: {cache_file.name}"
            )

        naan_registry_cache.update(data)
        logger.info(f"NAAN Registry in-memory cache updated")
        update_ark_root_resolver_map()

    except Exception as e:
        logger.error(f"Error updating NAAN Registry cache: {e}")
        # Fallback to cache if download fails
        if cache_file and cache_file.exists():
            naan_registry_cache.update(load_from_cache(cache_file))
            print(f"Fallback to (stale) file cache: {cache_file.name}")


async def periodically_download_and_update_naan_registry_cache(
    interval_seconds: int = (60 * 60 * 24),
):
    """Run download task periodically (default: every 24 hours)"""
    while True:
        await asyncio.sleep(interval_seconds)
        await ensure_up_to_date_naan_registry_cache()


def update_ark_root_resolver_map():
    """Produced an (ordered) dict mapping ark(/shoulder) "what"s to their "target"s."""
    ark_root_resolver_map.update(
        {
            record["what"]: record["target"]
            for record in sorted(
                naan_registry_cache["data"],
                key=lambda record: len(record["what"]),
                reverse=True,
            )
        }
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Exit the application if this fails.
    await ensure_up_to_date_naan_registry_cache()

    # Start a periodic background task to refresh the local cache.
    task = asyncio.create_task(periodically_download_and_update_naan_registry_cache())

    yield  # Let the application run.

    # On application shutdown: cancel the background task.
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)


@app.get("/naan_registry_cache")
async def get_naan_registry_cache():
    """Present the NAAN Registry cache."""
    return naan_registry_cache


@app.get("/ark_root_resolver_map")
async def get_ark_root_resolver_map():
    """Present the ARK root resolver map, derived from the NAAN Registry cache."""
    return ark_root_resolver_map


@app.get("/ark:{identifier:path}")
async def handle_ark(identifier: str):
    logging.debug(f"Handling ARK identifier: {identifier}")
    if identifier.startswith("/"):
        identifier = identifier.removeprefix("/")
        logging.debug(f"Stripped leading slash from ARK identifier: {identifier}")
    what, target = match_prefix(identifier, ark_root_resolver_map)
    redirect_url = target["url"].removesuffix("${content}") + identifier
    logger.info(f"Matched {identifier} to {what} -> {target} -> {redirect_url}")
    return RedirectResponse(
        redirect_url,
        status_code=target["http_code"],
    )


def match_prefix(input_string: str, dictionary: dict):
    """
    Matches dictionary keys to the prefix of the input string.
    Returns the longest matching key and its value, or None if no match.
    """
    matches = [
        (key, value)
        for key, value in dictionary.items()
        if input_string.startswith(key)
    ]

    if not matches:
        return None

    # Return the longest-key (most-specific) match
    return max(matches, key=lambda x: len(x[0]))
