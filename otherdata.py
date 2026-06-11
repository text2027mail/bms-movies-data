import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

DATA_DIR = "data"
OUTPUT_DIR = "otherdata"

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)

IST_YEAR = datetime.now(
    ZoneInfo("Asia/Kolkata")
).year

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

    if (
        len(person) > 1
        and person[1]
    ):
        image = str(
            person[1]
        ).strip()

    key = name.lower()

    if key not in store:

        store[key] = [
            name,
            image
        ]

    elif (
        not store[key][1]
        and image
    ):

        store[key][1] = image

def add_filmography(
    store,
    person_name,
    event_code
):

    if (
        not person_name
        or not event_code
    ):
        return

    key = (
        person_name
        .strip()
        .lower()
    )

    store.setdefault(
        key,
        set()
    ).add(
        event_code
    )

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
    
    
    if ec and rd:

        try:

            release_year = int(
                rd[:4]
            )

            if (
                release_year
                >= IST_YEAR
            ):

                movierelease[
                    ec
                ] = [
                    rd,
                    title or ""
                ]

        except Exception:
            pass
        
    for actor in movie.get(
        "cast",
        []
    ):

        add_person(
            actors,
            actor
        )

        if (
            actor
            and len(actor)
            and actor[0]
        ):

            add_filmography(
                actorfilmography,
                actor[0],
                ec
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

        if (
            item
            and len(item)
            and item[0]
        ):

            add_filmography(
                directorfilmography,
                item[0],
                ec
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

    try:

        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as f:

            content = f.read().strip()

        if not content:
            return 0

        # JSON Array
        if content.startswith("["):

            movies = json.loads(
                content
            )

            count = 0

            for movie in movies:

                if isinstance(
                    movie,
                    dict
                ):

                    process_movie(
                        movie
                    )

                    count += 1

            return count

        # NDJSON fallback

        count = 0

        for line in content.splitlines():

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

    except Exception as e:

        print(
            f"ERROR {filepath}: {e}"
        )

        return 0


print(
    "\nScanning all data files..."
)

movie_count = 0

for filename in sorted(
    os.listdir(DATA_DIR)
):

    if not filename.endswith(
        ".json"
    ):
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
        f"\nProcessing {filename}"
    )

    count = process_file(
        filepath
    )

    print(
        f"{filename}: "
        f"{count} movies"
    )

    movie_count += count


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

    size = round(
        os.path.getsize(path)
        / 1024,
        2
    )

    print(
        f"Saved {filename} "
        f"({size} KB)"
    )


save_json(
    "actors.json",
    sorted(
        actors.values(),
        key=lambda x:
        x[0].lower()
    )
)

save_json(
    "directors.json",
    sorted(
        directors.values(),
        key=lambda x:
        x[0].lower()
    )
)

save_json(
    "producers.json",
    sorted(
        producers.values(),
        key=lambda x:
        x[0].lower()
    )
)

save_json(
    "music.json",
    sorted(
        music.values(),
        key=lambda x:
        x[0].lower()
    )
)

save_json(
    "editors.json",
    sorted(
        editors.values(),
        key=lambda x:
        x[0].lower()
    )
)

save_json(
    "cinematography.json",
    sorted(
        cinematography.values(),
        key=lambda x:
        x[0].lower()
    )
)

save_json(
    "movierelease.json",
    movierelease
)

save_json(
    "actorfilmography.json",
    {
        k: sorted(v)
        for k, v
        in actorfilmography.items()
    }
)

save_json(
    "directorfilmography.json",
    {
        k: sorted(v)
        for k, v
        in directorfilmography.items()
    }
)

save_json(
    "moviemeta.json",
    moviemeta
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
    f"Producers: "
    f"{len(producers)}"
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
    f"Cinematography: "
    f"{len(cinematography)}"
)
print(
    f"Upcoming Releases: "
    f"{len(movierelease)}"
)
