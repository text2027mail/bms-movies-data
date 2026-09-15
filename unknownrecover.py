import asyncio
import aiohttp
import json
import os
import random
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

CONCURRENCY = 50
REQUEST_TIMEOUT = 30
MAX_PASSES = 3

UNKNOWN_FILE = "data/unknown.json"
ALREADY_FETCHED_FILE = "logs/alreadyfetched.txt"

MOVIE_API = (
    "https://bms-server-szkk.vercel.app/api/movie"
    "?eventCode={}"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) "
    "Gecko/20100101 Firefox/138.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
]

SEM = asyncio.Semaphore(CONCURRENCY)

FILE_LOCKS = {}
ALREADY_LOCK = asyncio.Lock()
UNKNOWN_LOCK = asyncio.Lock()

completed = 0
recovered = 0
still_unknown = 0
failed = 0


# ============================================================
# LOCKS
# ============================================================

def get_file_lock(year):
    if year not in FILE_LOCKS:
        FILE_LOCKS[year] = asyncio.Lock()
    return FILE_LOCKS[year]


# ============================================================
# PEOPLE
# ============================================================

def simplify_people(items):
    if not isinstance(items, list):
        return []

    return [
        [p.get("name"), p.get("image")]
        for p in items
        if isinstance(p, dict) and p.get("name")
    ]


# ============================================================
# MOVIE FORMAT
# ============================================================

def simplify_movie(data):
    crew = data.get("crew", {})

    if not isinstance(crew, dict):
        crew = {}

    rd = None

    release_date = data.get("releaseDate")

    if release_date:
        # Main expected format
        for fmt in (
            "%d %b, %Y",
            "%d %b %Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
        ):
            try:
                rd = datetime.strptime(
                    str(release_date).strip(),
                    fmt
                ).strftime("%Y-%m-%d")
                break
            except Exception:
                pass

    return {
        "ec": data.get("eventCode"),
        "t": data.get("title"),
        "img": data.get("poster"),
        "og": data.get("ogImage"),
        "d": data.get("description"),
        "rd": rd,
        "rt": data.get("runtimeMinutes"),
        "ct": data.get("certificate"),
        "g": data.get("genres", []),
        "l": data.get("languages", []),
        "f": data.get("formats", []),
        "i": data.get("interestedCount"),
        "cast": simplify_people(data.get("cast", [])),
        "crew": {
            "d": simplify_people(crew.get("directors", [])),
            "p": simplify_people(crew.get("producers", [])),
            "m": simplify_people(crew.get("music", [])),
            "c": simplify_people(crew.get("cinematography", [])),
            "e": simplify_people(crew.get("editors", [])),
        }
    }


# ============================================================
# READ UNKNOWN.JSON
# Supports:
#   1. NDJSON
#   2. JSON array
#   3. Single JSON object
# ============================================================

def load_unknown_movies():
    if not os.path.exists(UNKNOWN_FILE):
        return []

    try:
        with open(
            UNKNOWN_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            raw = f.read().strip()

        if not raw:
            return []

        # Try normal JSON first
        try:
            data = json.loads(raw)

            if isinstance(data, list):
                return [
                    x for x in data
                    if isinstance(x, dict)
                ]

            if isinstance(data, dict):
                return [data]

        except json.JSONDecodeError:
            pass

        # Fallback to NDJSON
        movies = []

        for line in raw.splitlines():
            line = line.strip()

            if not line:
                continue

            try:
                obj = json.loads(line)

                if isinstance(obj, dict):
                    movies.append(obj)

            except json.JSONDecodeError:
                continue

        return movies

    except Exception as e:
        print(f"ERROR reading {UNKNOWN_FILE}: {e}")
        return []


# ============================================================
# SAVE UNKNOWN.JSON
# Always normalize back to NDJSON
# ============================================================

async def save_unknown_movies(movies):
    async with UNKNOWN_LOCK:

        tmp_file = UNKNOWN_FILE + ".tmp"

        with open(
            tmp_file,
            "w",
            encoding="utf-8"
        ) as f:

            for movie in movies:
                f.write(
                    json.dumps(
                        movie,
                        ensure_ascii=False,
                        separators=(",", ":")
                    )
                    + "\n"
                )

        os.replace(
            tmp_file,
            UNKNOWN_FILE
        )


# ============================================================
# ALREADY FETCHED
# ============================================================

def load_already_fetched():
    if not os.path.exists(ALREADY_FETCHED_FILE):
        return set()

    try:
        with open(
            ALREADY_FETCHED_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return {
                line.strip()
                for line in f
                if line.strip()
            }

    except Exception:
        return set()


async def mark_already_fetched(event_code):
    async with ALREADY_LOCK:

        with open(
            ALREADY_FETCHED_FILE,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(event_code + "\n")


# ============================================================
# CHECK WHETHER CODE ALREADY EXISTS IN TARGET YEAR FILE
# Prevent duplicate recovery writes.
# ============================================================

def event_exists_in_year_file(year, event_code):
    filename = f"data/{year}.json"

    if not os.path.exists(filename):
        return False

    try:
        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                try:
                    movie = json.loads(line)

                    if str(movie.get("ec", "")).strip() == event_code:
                        return True

                except Exception:
                    continue

    except Exception:
        return False

    return False


# ============================================================
# SAVE RECOVERED MOVIE
# ============================================================

async def save_recovered_movie(movie):

    release_date = movie.get("rd")

    # Still no release date = keep in unknown
    if not release_date:
        return False

    try:
        year = release_date[:4]

        if (
            len(year) != 4
            or not year.isdigit()
        ):
            return False

    except Exception:
        return False

    event_code = str(
        movie.get("ec", "")
    ).strip()

    if not event_code:
        return False

    filename = f"data/{year}.json"

    async with get_file_lock(year):

        # Re-check inside lock
        if event_exists_in_year_file(
            year,
            event_code
        ):
            return True

        with open(
            filename,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                json.dumps(
                    movie,
                    ensure_ascii=False,
                    separators=(",", ":")
                )
                + "\n"
            )

    return True


# ============================================================
# FETCH MOVIE
#
# Return values:
#
#   "recovered"
#   "unknown"
#   "failed"
# ============================================================

async def fetch_movie(session, event_code):

    global completed
    global recovered
    global still_unknown
    global failed

    async with SEM:

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Referer": "https://in.bookmyshow.com/",
            "Origin": "https://in.bookmyshow.com"
        }

        url = MOVIE_API.format(event_code)

        try:

            async with session.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            ) as response:

                if response.status != 200:
                    failed += 1
                    return "failed", None

                data = await response.json()

                if not isinstance(data, dict):
                    failed += 1
                    return "failed", None

                if not data.get("success"):
                    failed += 1
                    return "failed", None

                movie = simplify_movie(data)

                # --------------------------------------------
                # Still unknown
                # --------------------------------------------

                if not movie.get("rd"):
                    still_unknown += 1
                    return "unknown", movie

                # --------------------------------------------
                # Release year recovered
                # --------------------------------------------

                saved = await save_recovered_movie(movie)

                if saved:

                    await mark_already_fetched(
                        event_code
                    )

                    recovered += 1

                    return "recovered", movie

                still_unknown += 1

                return "unknown", movie

        except Exception:
            failed += 1
            return "failed", None

        finally:

            completed += 1

            if completed % 50 == 0:

                print(
                    f"[{completed}] "
                    f"Recovered={recovered} "
                    f"StillUnknown={still_unknown} "
                    f"Failed={failed}"
                )


# ============================================================
# RUN ONE PASS
# ============================================================

async def run_pass(session, movies):

    tasks = []

    # Deduplicate by event code
    seen = set()

    unique_movies = []

    for movie in movies:

        event_code = str(
            movie.get("ec", "")
        ).strip()

        if not event_code:
            continue

        if event_code in seen:
            continue

        seen.add(event_code)
        unique_movies.append(movie)

        tasks.append(
            asyncio.create_task(
                fetch_movie(
                    session,
                    event_code
                )
            )
        )

    results = await asyncio.gather(
        *tasks
    )

    remaining = []

    recovered_now = 0

    for movie, result in zip(
        unique_movies,
        results
    ):

        status, fresh_movie = result

        if status == "recovered":
            recovered_now += 1
            continue

        # Keep unresolved entries.
        #
        # Use freshly fetched movie information when
        # available, otherwise preserve the original.
        if fresh_movie:
            remaining.append(
                fresh_movie
            )
        else:
            remaining.append(
                movie
            )

    return remaining, recovered_now


# ============================================================
# MAIN
# ============================================================

async def main():

    global completed
    global recovered
    global still_unknown
    global failed

    os.makedirs(
        "data",
        exist_ok=True
    )

    os.makedirs(
        "logs",
        exist_ok=True
    )

    movies = load_unknown_movies()

    if not movies:

        print("=" * 65)
        print("NO MOVIES FOUND IN data/unknown.json")
        print("=" * 65)
        return

    # --------------------------------------------
    # Deduplicate input
    # --------------------------------------------

    dedup = {}
    invalid = 0

    for movie in movies:

        if not isinstance(movie, dict):
            invalid += 1
            continue

        event_code = str(
            movie.get("ec", "")
        ).strip()

        if not event_code:
            invalid += 1
            continue

        dedup[event_code] = movie

    movies = list(
        dedup.values()
    )

    # --------------------------------------------
    # Header
    # --------------------------------------------

    print("=" * 65)
    print("BFILMY UNKNOWN MOVIE RECOVERY")
    print("=" * 65)
    print("Unknown File     :", UNKNOWN_FILE)
    print("Movies to Recover:", len(movies))
    print("Invalid Entries  :", invalid)
    print("Concurrency      :", CONCURRENCY)
    print("Max Passes       :", MAX_PASSES)
    print("=" * 65)

    connector = aiohttp.TCPConnector(
        limit=CONCURRENCY,
        ssl=False
    )

    timeout = aiohttp.ClientTimeout(
        total=REQUEST_TIMEOUT
    )

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout
    ) as session:

        remaining = movies

        for pass_no in range(
            1,
            MAX_PASSES + 1
        ):

            if not remaining:
                break

            print()
            print(
                f"PASS {pass_no} "
                f"→ {len(remaining)} movies"
            )
            print("-" * 65)

            remaining, recovered_now = (
                await run_pass(
                    session,
                    remaining
                )
            )

            # Save immediately after every pass.
            # This makes the process resumable.
            await save_unknown_movies(
                remaining
            )

            print(
                f"Recovered this pass : {recovered_now}"
            )

            print(
                f"Remaining unknown    : {len(remaining)}"
            )

    # --------------------------------------------
    # Final save
    # --------------------------------------------

    await save_unknown_movies(
        remaining
    )

    print()
    print("=" * 65)
    print("RECOVERY FINISHED")
    print("=" * 65)
    print("Initially Unknown :", len(movies))
    print("Recovered         :", recovered)
    print("Still Unknown     :", len(remaining))
    print("Failed Requests   :", failed)
    print("=" * 65)

    if remaining:

        print()
        print(
            f"{len(remaining)} movies remain in "
            f"{UNKNOWN_FILE}"
        )

    else:

        print()
        print(
            "data/unknown.json is now EMPTY."
        )


if __name__ == "__main__":
    asyncio.run(main())
