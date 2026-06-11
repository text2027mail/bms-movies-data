import asyncio
import aiohttp
import json
import os
import random
from datetime import datetime

FIRST_SOURCE = (
    "https://cdn.jsdelivr.net/gh/unknownman2024/bms-movies@main/output/movies.json"
)

SECOND_SOURCE = (
    "https://cdn.jsdelivr.net/gh/unknownman2024/bms-interest-track@main/Bookmyshow%20Data/moviesdb.json"
)

CONCURRENCY = 50
REQUEST_TIMEOUT = 30
MAX_PASSES = 3

USER_AGENTS = [
    "Mozilla/5.2 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.2 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.2 (X11; Linux x86_64)",
    "Mozilla/5.2 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Mozilla/5.2 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
]

SEM = asyncio.Semaphore(CONCURRENCY)
SUCCESS_LOCK = asyncio.Lock()
FILE_LOCKS = {}

completed = 0
added = 0


def get_file_lock(year):
    if year not in FILE_LOCKS:
        FILE_LOCKS[year] = asyncio.Lock()
    return FILE_LOCKS[year]


async def fetch_json(session, url):
    try:
        async with session.get(url, timeout=60) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception:
        return None


async def get_codes_from_movies_json(session):
    data = await fetch_json(session, FIRST_SOURCE)

    if not isinstance(data, list):
        return set()

    return {
        str(movie.get("DefaultEventCode")).strip()
        for movie in data
        if movie.get("DefaultEventCode")
    }


async def get_codes_from_moviesdb(session):
    data = await fetch_json(session, SECOND_SOURCE)

    if not isinstance(data, dict):
        return set()

    return {
        str(code).strip()
        for code in data.keys()
        if code
    }


def simplify_people(items):
    return [
        [p.get("name"), p.get("image")]
        for p in items
        if p.get("name")
    ]


def simplify_movie(data):
    crew = data.get("crew", {})

    rd = None
    try:
        rd = datetime.strptime(
            data.get("releaseDate"),
            "%d %b, %Y"
        ).strftime("%Y-%m-%d")
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
            "e": simplify_people(crew.get("editors", []))
        }
    }


async def save_success(event_code):
    async with SUCCESS_LOCK:
        with open("logs/alreadyfetched.txt", "a", encoding="utf-8") as f:
            f.write(event_code + "\\n")


async def save_movie(movie):
    year = "unknown"

    if movie.get("rd"):
        year = movie["rd"][:4]

    filename = f"data/{year}.json"

    async with get_file_lock(year):
        with open(filename, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    movie,
                    ensure_ascii=False,
                    separators=(",", ":")
                ) + "\\n"
            )


async def fetch_movie(session, event_code):
    global completed, added

    async with SEM:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Referer": "https://in.bookmyshow.com/",
            "Origin": "https://in.bookmyshow.com"
        }

        url = (
            "https://bms-server-szkk.vercel.app/api/movie"
            f"?eventCode={event_code}"
        )

        try:
            async with session.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            ) as r:

                if r.status != 200:
                    return False

                data = await r.json()

                if not data.get("success"):
                    return False

                movie = simplify_movie(data)

                await save_movie(movie)
                await save_success(event_code)

                added += 1
                return True

        except Exception:
            return False

        finally:
            completed += 1

            if completed % 50 == 0:
                print(
                    f"[{completed}] Added={added}"
                )


async def run_pass(session, codes):
    tasks = [
        asyncio.create_task(
            fetch_movie(session, code)
        )
        for code in codes
    ]

    results = await asyncio.gather(*tasks)

    failed_codes = [
        code
        for code, ok in zip(codes, results)
        if not ok
    ]

    return failed_codes


async def main():

    os.makedirs(
        "data",
        exist_ok=True
    )

    os.makedirs(
        "logs",
        exist_ok=True
    )
    async with aiohttp.ClientSession() as session:

        movies_codes, moviesdb_codes = await asyncio.gather(
            get_codes_from_movies_json(session),
            get_codes_from_moviesdb(session)
        )

        all_codes = movies_codes | moviesdb_codes

    already = set()

    if os.path.exists("logs/alreadyfetched.txt"):
        with open(
            "logs/alreadyfetched.txt",
            encoding="utf-8"
        ) as f:
            already = {
                x.strip()
                for x in f
                if x.strip()
            }

    remaining = sorted(all_codes - already)

    print("=" * 60)
    print("Total Codes     :", len(all_codes))
    print("Already Fetched :", len(already))
    print("Remaining       :", len(remaining))
    print("=" * 60)

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

        failed_codes = remaining

        for pass_no in range(1, MAX_PASSES + 1):

            if not failed_codes:
                break

            print(
                f"\\nPASS {pass_no} "
                f"({len(failed_codes)} codes)"
            )

            failed_codes = await run_pass(
                session,
                failed_codes
            )

            print(
                f"Remaining after pass {pass_no}: "
                f"{len(failed_codes)}"
            )

    with open(
        "logs/failed.txt",
        "w",
        encoding="utf-8"
    ) as f:
        f.write("\\n".join(failed_codes))

    print("\\nFinished")
    print("Added :", added)
    print("Failed:", len(failed_codes))


if __name__ == "__main__":
    asyncio.run(main())
