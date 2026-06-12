import os
import json
from collections import defaultdict
from datetime import datetime

DATA_DIR = "data"

movies_by_ec = {}

files_read = 0
movies_read = 0
duplicates_removed = 0

print("Reading files...")

for filename in os.listdir(DATA_DIR):

    if not filename.endswith(".json"):
        continue

    filepath = os.path.join(
        DATA_DIR,
        filename
    )

    files_read += 1

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

            movies_read += 1

            ec = str(
                movie.get("ec", "")
            ).strip()

            if not ec:
                continue

            existing = movies_by_ec.get(ec)

            if existing is None:
                movies_by_ec[ec] = movie
                continue

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

print("Grouping by release year...")

year_data = defaultdict(list)

for movie in movies_by_ec.values():

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

print("Sorting movies...")

for movies in year_data.values():

    movies.sort(
        key=lambda x: (
            x.get("rd")
            if isinstance(
                x.get("rd"),
                str
            )
            else "9999-99-99"
        )
    )

print("Removing old json files...")

for filename in os.listdir(DATA_DIR):

    if filename.endswith(".json"):

        os.remove(
            os.path.join(
                DATA_DIR,
                filename
            )
        )

print("Writing new files...")

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
print("Unique Movies      :", len(movies_by_ec))
print("Duplicates Removed :", duplicates_removed)
print("=" * 60)

for year in sorted(year_data):

    print(
        f"{year}.json -> "
        f"{len(year_data[year])} movies"
    )

print("\nFinished.")
