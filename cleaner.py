import os
import json
from collections import defaultdict
from datetime import datetime

DATA_DIR = "data"

movies_by_ec = {}
movies_without_ec = []

files_read = 0
movies_read = 0
duplicates_removed = 0


def add_movie(movie):
    global movies_read
    global duplicates_removed

    if not isinstance(movie, dict):
        return

    movies_read += 1

    ec = str(
        movie.get("ec", "")
    ).strip()

    if not ec:
        movies_without_ec.append(movie)
        return

    existing = movies_by_ec.get(ec)

    if existing is None:
        movies_by_ec[ec] = movie
        return

    old_size = len(
        json.dumps(
            existing,
            ensure_ascii=False
        )
    )

    new_size = len(
        json.dumps(
            movie,
            ensure_ascii=False
        )
    )

    if new_size > old_size:
        movies_by_ec[ec] = movie

    duplicates_removed += 1


print("Reading files...")

for filename in os.listdir(DATA_DIR):

    if not filename.endswith(".json"):
        continue

    filepath = os.path.join(
        DATA_DIR,
        filename
    )

    files_read += 1

    try:

        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as f:

            content = f.read().strip()

        if not content:
            continue

        # Full JSON file
        try:

            parsed = json.loads(content)

            if isinstance(parsed, list):

                for movie in parsed:
                    add_movie(movie)

                continue

            if isinstance(parsed, dict):

                add_movie(parsed)
                continue

        except Exception:
            pass

        # JSONL fallback
        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                try:
                    movie = json.loads(line)
                except Exception:
                    continue

                if isinstance(movie, list):

                    for item in movie:
                        add_movie(item)

                else:
                    add_movie(movie)

    except Exception as e:

        print(
            f"Failed reading {filename}: {e}"
        )

print(
    f"Loaded {movies_read} movies"
)

year_data = defaultdict(list)

all_movies = (
    list(movies_by_ec.values())
    + movies_without_ec
)

print("Grouping by year...")

for movie in all_movies:

    rd = movie.get("rd")

    year = "unknown"

    if isinstance(rd, str):

        try:

            year = str(
                datetime.strptime(
                    rd,
                    "%Y-%m-%d"
                ).year
            )

        except Exception:
            pass

    year_data[year].append(movie)

print("Sorting...")

for movies in year_data.values():

    def sort_key(movie):

        rd = movie.get("rd")

        if not isinstance(rd, str):
            return "9999-99-99"

        return rd

    movies.sort(
        key=sort_key
    )

print("Removing old files...")

for filename in os.listdir(DATA_DIR):

    if filename.endswith(".json"):

        os.remove(
            os.path.join(
                DATA_DIR,
                filename
            )
        )

print("Writing cleaned files...")

for year in sorted(year_data.keys()):

    output_file = os.path.join(
        DATA_DIR,
        f"{year}.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        for movie in year_data[year]:

            f.write(
                json.dumps(
                    movie,
                    ensure_ascii=False,
                    separators=(",", ":")
                )
                + "\n"
            )

print("\n" + "=" * 60)
print("Files Read         :", files_read)
print("Movies Read        :", movies_read)
print("Unique EC Movies   :", len(movies_by_ec))
print("No EC Movies       :", len(movies_without_ec))
print("Duplicates Removed :", duplicates_removed)
print("=" * 60)

for year in sorted(year_data):

    print(
        f"{year}.json -> "
        f"{len(year_data[year])}"
    )

print("\nFinished.")
