import os
import json
from datetime import datetime

DATA_DIR = "data"
OUTPUT_DIR = "otherdata"

CURRENT_YEAR = datetime.now().year

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

# Only current & future years
ALLOWED_FILES = {
    f"{CURRENT_YEAR}.json",
    f"{CURRENT_YEAR + 1}.json",
    f"{CURRENT_YEAR + 2}.json",
    "unknown.json"
}

actors = {}
directors = {}
producers = {}
music = {}
editors = {}
cinematography = {}

movierelease = {}


def add_person(store, person):

    if (
        not isinstance(person, list)
        or len(person) < 1
    ):
        return

    name = (
        str(person[0]).strip()
        if person[0]
        else ""
    )

    if not name:
        return

    image = ""

    if len(person) > 1 and person[1]:
        image = str(person[1]).strip()

    key = name.lower()

    if key not in store:
        store[key] = [name, image]

    elif (
        not store[key][1]
        and image
    ):
        store[key][1] = image


def process_movie(movie):

    ec = movie.get("ec")
    rd = movie.get("rd")
    title = movie.get("t")

    if ec:
        movierelease[ec] = [
            rd or "",
            title or ""
        ]

    for actor in movie.get(
        "cast",
        []
    ):
        add_person(
            actors,
            actor
        )

    crew = movie.get(
        "crew",
        {}
    )

    for item in crew.get(
        "d",
        []
    ):
        add_person(
            directors,
            item
        )

    for item in crew.get(
        "p",
        []
    ):
        add_person(
            producers,
            item
        )

    for item in crew.get(
        "m",
        []
    ):
        add_person(
            music,
            item
        )

    for item in crew.get(
        "e",
        []
    ):
        add_person(
            editors,
            item
        )

    for item in crew.get(
        "c",
        []
    ):
        add_person(
            cinematography,
            item
        )


def process_file(filepath):

    count = 0

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

                movie = json.loads(
                    line
                )

                process_movie(
                    movie
                )

                count += 1

            except Exception:
                pass

    return count


print(
    "\nScanning files..."
)

movie_count = 0

for filename in sorted(
    os.listdir(DATA_DIR)
):

    if filename not in ALLOWED_FILES:
        continue

    filepath = os.path.join(
        DATA_DIR,
        filename
    )

    if not os.path.isfile(
        filepath
    ):
        continue

    print(
        f"Processing {filename}"
    )

    movie_count += process_file(
        filepath
    )


def save_json(
    filename,
    data
):

    path = os.path.join(
        OUTPUT_DIR,
        filename
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            separators=(",", ":")
        )

    print(
        f"Saved {filename} "
        f"({len(data)} entries)"
    )


save_json(
    "actors.json",
    sorted(
        actors.values(),
        key=lambda x: x[0]
    )
)

save_json(
    "directors.json",
    sorted(
        directors.values(),
        key=lambda x: x[0]
    )
)

save_json(
    "producers.json",
    sorted(
        producers.values(),
        key=lambda x: x[0]
    )
)

save_json(
    "music.json",
    sorted(
        music.values(),
        key=lambda x: x[0]
    )
)

save_json(
    "editors.json",
    sorted(
        editors.values(),
        key=lambda x: x[0]
    )
)

save_json(
    "cinematography.json",
    sorted(
        cinematography.values(),
        key=lambda x: x[0]
    )
)

save_json(
    "movierelease.json",
    movierelease
)

print("\nDone")
print(
    f"Movies Processed: "
    f"{movie_count}"
)
print(
    f"Actors: "
    f"{len(actors)}"
)
print(
    f"Directors: "
    f"{len(directors)}"
)
print(
    f"Music: "
    f"{len(music)}"
)
print(
    f"Editors: "
    f"{len(editors)}"
)
print(
    f"Producers: "
    f"{len(producers)}"
)
print(
    f"Cinematography: "
    f"{len(cinematography)}"
)
print(
    f"Movie Releases: "
    f"{len(movierelease)}"
)
