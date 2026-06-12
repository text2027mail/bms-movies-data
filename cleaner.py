import os
import json
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

DATA_DIR = "data"
OUTPUT_DIR = "otherdata"

os.makedirs(OUTPUT_DIR, exist_ok=True)

IST_NOW = datetime.now(ZoneInfo("Asia/Kolkata"))
TODAY = IST_NOW.strftime("%Y-%m-%d")

movies_by_ec = {}
movies_without_ec = []

files_read = 0
movies_read = 0
duplicates_removed = 0

actors = {}
directors = {}
producers = {}
music = {}
editors = {}
cinematography = {}

movierelease = {}
actorfilmography = {}
directorfilmography = {}
moviemeta = {}


def json_size(obj):
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def add_movie(movie):
    global movies_read, duplicates_removed

    if not isinstance(movie, dict):
        return

    movies_read += 1

    ec = str(movie.get("ec", "")).strip()

    if not ec:
        movies_without_ec.append(movie)
        return

    existing = movies_by_ec.get(ec)

    if existing is None:
        movies_by_ec[ec] = movie
        return

    if json_size(movie) > json_size(existing):
        movies_by_ec[ec] = movie

    duplicates_removed += 1


def read_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            return

        try:
            parsed = json.loads(content)

            if isinstance(parsed, list):
                for item in parsed:
                    add_movie(item)
                return

            if isinstance(parsed, dict):
                add_movie(parsed)
                return

        except Exception:
            pass

        for line in content.splitlines():
            line = line.strip()

            if not line:
                continue

            try:
                parsed = json.loads(line)
            except Exception:
                continue

            if isinstance(parsed, list):
                for item in parsed:
                    add_movie(item)
            else:
                add_movie(parsed)

    except Exception as e:
        print(f"ERROR {filepath}: {e}")


def add_person(store, person):
    if not isinstance(person, list) or not person:
        return

    name = str(person[0]).strip() if person[0] else ""
    if not name:
        return

    image = ""
    if len(person) > 1 and person[1]:
        image = str(person[1]).strip()

    key = name.lower()

    if key not in store:
        store[key] = [name, image]
    elif not store[key][1] and image:
        store[key][1] = image


def add_filmography(store, person_name, event_code):
    if not person_name or not event_code:
        return

    store.setdefault(person_name.strip().lower(), set()).add(event_code)


def process_movie(movie):
    ec = movie.get("ec")
    rd = movie.get("rd")
    title = movie.get("t")

    if ec:
        moviemeta[ec] = [
            title or "",
            rd or "",
            movie.get("img") or ""
        ]

    if ec and rd and isinstance(rd, str) and rd >= TODAY:
        movierelease[ec] = [rd, title or ""]

    for actor in movie.get("cast", []):
        add_person(actors, actor)

        if actor and len(actor) and actor[0]:
            add_filmography(
                actorfilmography,
                actor[0],
                ec
            )

    crew = movie.get("crew", {})

    for item in crew.get("d", []):
        add_person(directors, item)

        if item and len(item) and item[0]:
            add_filmography(
                directorfilmography,
                item[0],
                ec
            )

    for item in crew.get("p", []):
        add_person(producers, item)

    for item in crew.get("m", []):
        add_person(music, item)

    for item in crew.get("e", []):
        add_person(editors, item)

    for item in crew.get("c", []):
        add_person(cinematography, item)


def save_json(filename, data):
    path = os.path.join(OUTPUT_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            separators=(",", ":")
        )

    size = round(os.path.getsize(path) / 1024, 2)
    print(f"Saved {filename} ({size} KB)")


print("Reading files...")

for filename in sorted(os.listdir(DATA_DIR)):
    if not filename.endswith(".json"):
        continue

    filepath = os.path.join(DATA_DIR, filename)

    if not os.path.isfile(filepath):
        continue

    files_read += 1
    read_file(filepath)

all_movies = list(movies_by_ec.values()) + movies_without_ec

print(f"Loaded {movies_read} movies")
print(f"Unique movies: {len(all_movies)}")

for movie in all_movies:
    process_movie(movie)

year_data = defaultdict(list)

for movie in all_movies:
    rd = movie.get("rd")

    year = "unknown"

    if isinstance(rd, str):
        try:
            year = str(datetime.strptime(rd, "%Y-%m-%d").year)
        except Exception:
            pass

    year_data[year].append(movie)

for movies in year_data.values():
    movies.sort(
        key=lambda x: x.get("rd")
        if isinstance(x.get("rd"), str)
        else "9999-99-99"
    )

print("Rebuilding year files...")

for filename in os.listdir(DATA_DIR):
    if filename.endswith(".json"):
        os.remove(os.path.join(DATA_DIR, filename))

for year in sorted(year_data.keys()):
    output_file = os.path.join(DATA_DIR, f"{year}.json")

    with open(output_file, "w", encoding="utf-8") as f:
        for movie in year_data[year]:
            f.write(
                json.dumps(
                    movie,
                    ensure_ascii=False,
                    separators=(",", ":")
                ) + "\\n"
            )

print("Writing metadata...")

save_json("actors.json",
          sorted(actors.values(), key=lambda x: x[0].lower()))
save_json("directors.json",
          sorted(directors.values(), key=lambda x: x[0].lower()))
save_json("producers.json",
          sorted(producers.values(), key=lambda x: x[0].lower()))
save_json("music.json",
          sorted(music.values(), key=lambda x: x[0].lower()))
save_json("editors.json",
          sorted(editors.values(), key=lambda x: x[0].lower()))
save_json("cinematography.json",
          sorted(cinematography.values(), key=lambda x: x[0].lower()))
save_json("movierelease.json", movierelease)
save_json("moviemeta.json", moviemeta)

save_json(
    "actorfilmography.json",
    {k: sorted(v) for k, v in actorfilmography.items()}
)

save_json(
    "directorfilmography.json",
    {k: sorted(v) for k, v in directorfilmography.items()}
)

print("\\n" + "=" * 60)
print("Files Read         :", files_read)
print("Movies Read        :", movies_read)
print("Unique EC Movies   :", len(movies_by_ec))
print("No EC Movies       :", len(movies_without_ec))
print("Duplicates Removed :", duplicates_removed)
print("=" * 60)

for year in sorted(year_data):
    print(f"{year}.json -> {len(year_data[year])}")

print("\\nDone")
