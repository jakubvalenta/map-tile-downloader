import argparse
import datetime
import math
import random
import time
from pathlib import Path
from string import Template
from typing import NamedTuple

from dotenv import dotenv_values
from requests import RequestException, Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class Point(NamedTuple):
    lat: float
    lon: float


class Tile(NamedTuple):
    z: int
    x: int
    y: int


def get_tile_for_point(point: Point, z: int) -> Tile:
    """See https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Common_programming_languages"""
    lat_rad = math.radians(point.lat)
    n = 1 << z
    x = int((point.lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return Tile(z, x, y)


def get_tiles_in_rect(min_x: int, max_x: int, min_y: int, max_y: int, z: int) -> list[Tile]:
    res: list[Tile] = []
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            res.append(Tile(z, x, y))
    return res


def get_session(
    user_agent: str,
    cookies: dict[str, str | None] | None = None,
    referer: str | None = None,
) -> Session:
    session = Session()
    retry = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods={"GET"},
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=1,
        pool_maxsize=1,
    )
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        }
    )
    if referer is not None:
        session.headers.update(
            {
                "Referer": referer,
                "Origin": referer,
            }
        )

    if cookies is not None:
        clean_cookies: dict[str, str] = {k: v for k, v in cookies.items() if v}
        print(f"Setting cookies {', '.join(clean_cookies.keys())}")
        session.cookies.update(clean_cookies)
    return session


def download_tile(
    tile: Tile,
    url: str,
    session: Session,
    output_dir: Path,
    dry_run: bool = False,
    connect_timeout_sec: int = 5,
    read_timeout_sec: int = 30,
    wait_sec: int = 3,
    wait_jitter: float = 0.5,
) -> bool:
    # Dry run
    if dry_run:
        print(f"{tile.z},{tile.x},{tile.y}: downloading {url} (dry run)")
        return True

    # Path
    output_path = output_dir / str(tile.z) / str(tile.x) / f"{tile.y}.png"
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"{tile.z},{tile.x},{tile.y}: already downloaded")
        return True
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".png.part")

    # Wait
    wait_sec_with_jitter = wait_sec * random.uniform(1 - wait_jitter, 1 + wait_jitter)
    print(f"{tile.z},{tile.x},{tile.y}: waiting for {wait_sec_with_jitter:.2f}s")
    time.sleep(wait_sec_with_jitter)

    # Download
    print(f"{tile.z},{tile.x},{tile.y}: downloading {url}")
    try:
        with session.get(url, timeout=(connect_timeout_sec, read_timeout_sec), stream=True) as res:
            res.raise_for_status()  # Raise on failure after HTTPAdapter's retries

            with open(temp_path, "wb") as f:
                for chunk in res.iter_content(64 * 1024):
                    if chunk:
                        f.write(chunk)

        if temp_path.stat().st_size == 0:
            raise ValueError("Downloaded empty file")

        with open(temp_path, "rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Downloaded file is not a PNG image")

        temp_path.replace(output_path)

    except (RequestException, OSError, ValueError) as e:
        print(f"{tile.z},{tile.x},{tile.y}: failed: {e}")
        temp_path.unlink(missing_ok=True)
        return False

    print(f"{tile.z},{tile.x},{tile.y}: finished")
    return True


DEFAULT_ZOOM = 10
DEFAULT_OUTPUT_DIR = "tiles"
DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:161.0) Gecko/20100101 Firefox/161.0"
DEFAULT_COOKIES_FILE = "cookies.env"


def main() -> None:
    # Parse arguments
    parser = argparse.ArgumentParser(description="Download map tiles.")
    parser.add_argument(
        "url_template",
        help="URL template (supports variables $x, $y, $z, $timestamp, example https://tile.openstreetmap.org/$z/$x/$y.png)",
    )
    parser.add_argument(
        "point",
        nargs="+",
        help="Geographic coordinates in format latitude,longitude (example 47.62051,-122.34931)",
    )
    parser.add_argument(
        "-z",
        "--zoom",
        type=int,
        default=DEFAULT_ZOOM,
        help=f"Zoom (default {DEFAULT_ZOOM})",
    )
    parser.add_argument(
        "-a",
        "--ancestors",
        action="store_true",
        default=False,
        help="Download lower zoom levels too",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for downloaded tiles, created if missing (default {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "-r",
        "--referer",
        help="Referer and Origin header",
    )
    parser.add_argument(
        "-u",
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help=f"User agent (default {DEFAULT_USER_AGENT})",
    )
    parser.add_argument(
        "-c",
        "--cookies-file",
        default=DEFAULT_COOKIES_FILE,
        help=f"Cookies file (default {DEFAULT_COOKIES_FILE})",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        default=False,
        help="Dry run",
    )
    args = parser.parse_args()

    # Generate tiles
    try:
        points = [
            Point(float(lat), float(lon))
            for lat, lon in (s.split(",", maxsplit=1) for s in args.point)
        ]
    except ValueError:
        parser.error(f"Failed to parse points {args.point!r}")
    tiles_by_zoom: list[list[Tile]] = []
    for z in range(args.zoom + 1):
        if z == args.zoom or args.ancestors:
            point_tiles = {get_tile_for_point(point, z) for point in points}
            tiles_by_zoom.append(
                get_tiles_in_rect(
                    min_x=min(tile.x for tile in point_tiles),
                    min_y=min(tile.y for tile in point_tiles),
                    max_x=max(tile.x for tile in point_tiles),
                    max_y=max(tile.y for tile in point_tiles),
                    z=z,
                )
            )
        else:
            tiles_by_zoom.append([])

    # Create output directory
    output_dir = Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        parser.error(f"Failed to create output directory {args.output_dir!r}: {e.strerror}")

    # Prepare session
    cookies = dotenv_values(args.cookies_file)
    session = get_session(user_agent=args.user_agent, cookies=cookies)

    # Download tiles
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%s")
    url_template = Template(args.url_template)
    for z, tiles in enumerate(tiles_by_zoom):
        print(f"Downloading {len(tiles)} tiles at zoom level {z}")
        random.shuffle(tiles)
        for tile in tiles:
            url = url_template.substitute(z=tile.z, x=tile.x, y=tile.y, timestamp=timestamp)
            download_tile(tile, url, session, output_dir, dry_run=args.dry_run)
    print("Done")


if __name__ == "__main__":
    main()
