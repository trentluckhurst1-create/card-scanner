from __future__ import annotations

import re

from .models import CardIdentity


YEAR_RE = re.compile(
    r"\b((?:19|20)\d{2})(?:-(\d{2}))?\b"
)

SERIAL_RE = re.compile(
    r"(?<![#\d])(\d{1,4})\s*/\s*(\d{1,4})(?!\d)"
)

SERIAL_TOTAL_ONLY_RE = re.compile(
    r"(?<![#\d])#?\s*/\s*(\d{1,4})(?!\d)"
)

CARD_NUMBER_RE = re.compile(
    r"#([A-Z0-9][A-Z0-9\-\.]*)\b",
    re.I,
)

GRADE_RE = re.compile(
    r"\b(PSA|BGS|SGC|CGC)\s*(\d+(?:\.\d+)?)\b",
    re.I,
)


BRANDS = [
    "Bowman Chrome",
    "Bowman Draft",
    "Bowman",
    "Panini Phoenix",
    "Panini One and One",
    "Panini Mosaic",
    "Panini Chronicles",
    "Panini Hoops",
    "Panini Revolution",
    "Panini Donruss Optic",
    "One and One",
    "Topps Chrome",
    "Topps Finest",
    "Topps",
    "Panini Prizm",
    "Panini",
    "Fleer Retro",
    "Prizm",
    "Select",
    "Donruss Optic",
    "Donruss",
    "SP Authentic",
    "Flawless",
    "National Treasures",
    "Immaculate",
    "Impeccable",
    "Contenders",
    "Mosaic",
    "Obsidian",
    "Spectra",
    "Origins",
    "Chronicles",
    "Absolute",
    "Certified",
    "Limited",
    "Score",
]


PARALLEL_TERMS = [
    "Superfractor",
    "Gold Vinyl",
    "Gold Wave",
    "Gold Power",
    "Gold Shimmer",
    "Gold Refractor",
    "Gold",
    "Ruby",
    "Emerald",
    "Sapphire",
    "Orange Wave",
    "Orange Refractor",
    "Orange",
    "Red Wave",
    "Red Refractor",
    "Red",
    "Green Wave",
    "Green Refractor",
    "Green",
    "Purple Wave",
    "Purple Refractor",
    "Purple",
    "Blue Wave",
    "Blue Refractor",
    "Blue",
    "Fuchsia",
    "Pink Laser",
    "Pink Wave",
    "Lazer Prizm",
    "Lazer",
    "Stained Glass",
    "Fire Burst",
    "Press Proof Red",
    "Reactive Orange",
    "Silver Wave",
    "Pulsar",
    "X-Fractor",
    "Orange Fireworks",
    "Mercury Green",
    "Refractor",
    "Silver",
    "Black",
    "Cracked Ice",
    "Sparkle",
    "Sunflower Seeds",
    "Team Multi-Patch Booklet",
    "Rookie Badge Signature",
    "AFL Badge Signature",
    "Solo Double Patch",
    "Dual Patch",
    "Jumbo Patch",
    "Aqua Reptilian",
    "Steel Metal",
    "Bowman Spotlights",
    "Prized Prospects",
    "All Kings",
    "Comic Court",
    "Class of '25",
    "Axis",
    "SSP",
    "Mojo",
    "Shimmer",
    "Scope",
    "Disco",
    "Holo",
]


SPORT_HINTS = {
    "NFL": [
        "football",
        "nfl",
        "flawless football",
        "prizm football",
        "select football",
    ],
    "NBA": [
        "basketball",
        "nba",
        "nbl",
        "wnba",
        "prizm basketball",
        "select basketball",
    ],
    "MLB": [
        "baseball",
        "mlb",
        "bowman",
        "topps",
    ],
    "AFL": [
        "afl",
        "footy stars",
        "select afl",
        "supremacy",
        "brilliance",
    ],
}


NON_PLAYER_UPPER = {
    "ROOKIE",
    "AUTO",
    "AUTOGRAPH",
    "AUTOGRAPHS",
    "SIGNATURE",
    "SIGNATURES",
    "PATCH",
    "RELIC",
    "MEMORABILIA",
    "JERSEY",
    "CHROME",
    "PROSPECT",
    "BOWMAN",
    "DRAFT",
    "PRIZM",
    "SELECT",
    "DONRUSS",
    "FLAWLESS",
    "REFRACTOR",
    "GOLD",
    "WAVE",
    "PURPLE",
    "GREEN",
    "RED",
    "BLUE",
    "ORANGE",
    "SILVER",
    "BLACK",
    "PINK",
    "SPARKLE",
    "BASE",
    "RISING",
    "STAR",
    "PREDICTOR",
    "ISO",
    "SSP",
    "AXIS",
}


LEAGUE_PREFIX_TOKENS = {
    "AFL",
    "MLB",
    "NBA",
    "NBL",
    "NFL",
    "WNBA",
}


def infer_sport(
    title: str,
    fallback: str | None = None,
) -> str:
    if fallback:
        return fallback.upper()

    lower = title.lower()

    for sport, hints in SPORT_HINTS.items():
        if any(hint in lower for hint in hints):
            return sport

    return "UNKNOWN"


def _extract_brand(title: str) -> str | None:
    lower = title.lower()

    for brand in sorted(
        BRANDS,
        key=len,
        reverse=True,
    ):
        if brand.lower() in lower:
            if brand == "One and One":
                return "Panini One and One"
            return brand

    return None


def _extract_set_name(
    title: str,
    brand: str | None,
) -> str | None:
    if not brand:
        return None

    # For these families the branded phrase is effectively
    # the set family used for comp matching.
    preferred = [
        "Bowman Draft",
        "Bowman Chrome",
        "Topps Chrome",
        "Panini Mosaic",
        "Panini Chronicles",
        "Panini Hoops",
        "Panini Revolution",
        "Panini Donruss Optic",
        "Donruss Optic",
        "National Treasures",
    ]

    lower = title.lower()

    for item in preferred:
        if item.lower() in lower:
            return item

    # Cherry AFL titles commonly begin "2026 Select AFL Footy Stars".
    m = re.search(
        r"\bSelect\s+AFL\s+Footy\s+Stars\b",
        title,
        flags=re.I,
    )
    if m:
        return "Select AFL Footy Stars"

    m = re.search(
        r"\bSelect\s+AFL\s+Seamless\b",
        title,
        flags=re.I,
    )
    if m:
        return "Select AFL Seamless"

    # Keep the identified brand as the conservative fallback.
    return brand


def _extract_parallel(title: str) -> str | None:
    lower = title.lower()

    for parallel in sorted(
        PARALLEL_TERMS,
        key=len,
        reverse=True,
    ):
        if parallel.lower() in lower:
            return parallel

    return None


def _strip_league_tokens(words: list[str]) -> list[str]:
    cleaned = list(words)

    while cleaned and cleaned[0].rstrip(".") in LEAGUE_PREFIX_TOKENS:
        cleaned.pop(0)

    while cleaned and cleaned[-1].rstrip(".") in LEAGUE_PREFIX_TOKENS:
        cleaned.pop()

    while cleaned and cleaned[-1].rstrip(".") in NON_PLAYER_UPPER:
        cleaned.pop()

    while cleaned and cleaned[0].rstrip(".") in NON_PLAYER_UPPER:
        cleaned.pop(0)

    return cleaned


def _extract_uppercase_player(title: str) -> str | None:
    """
    Cherry singles titles reliably capitalise the subject name.
    We use runs of 2-4 uppercase name-like tokens and reject
    known product/card terminology.

    Examples:
      KYSON WITHERSPOON
      FERNANDO TATIS JR.
      JASON HORNE-FRANCIS
    """

    # Strip leading year so it cannot interfere with token groups.
    text = YEAR_RE.sub(" ", title, count=1)

    candidates = re.findall(
        r"\b(?:[A-Z][A-Z'\-\.]*)(?:\s+[A-Z][A-Z'\-\.]*){1,3}\b",
        text,
    )
    cleaned: list[str] = []

    for candidate in candidates:
        words = _strip_league_tokens(candidate.split())

        if len(words) < 2:
            continue

        # Reject groups dominated by card/set vocabulary.
        if all(
            word.rstrip(".") in NON_PLAYER_UPPER
            for word in words
        ):
            continue

        # A real player group should contain at least two tokens
        # that are not card terminology.
        meaningful = [
            word
            for word in words
            if word.rstrip(".") not in NON_PLAYER_UPPER
        ]

        if len(meaningful) < 2:
            continue

        # Reject some obvious uppercase set/product phrases.
        phrase = " ".join(words)

        rejects = [
            "BOWMAN DRAFT",
            "BOWMAN CHROME",
            "FOOTY STARS",
            "RISING STAR",
            "GAME USED",
            "DRAFT NIGHT",
            "HALL OF FAME",
            "PRIZED PROSPECTS",
            "IN ACTION",
        ]

        if any(r in phrase for r in rejects):
            continue

        cleaned.append(" ".join(words))

    if not cleaned:
        return None

    # Cherry normally places player immediately after set/year.
    player = cleaned[0]

    # Convert display form while preserving suffixes.
    parts = []

    for token in player.split():
        upper = token.rstrip(".")

        if upper == "JR":
            parts.append("Jr.")
        elif upper == "SR":
            parts.append("Sr.")
        elif upper in {"II", "III", "IV"}:
            parts.append(upper)
        elif token.isupper() and len(upper) <= 2 and not set(upper).intersection({"A", "E", "I", "O", "U"}):
            parts.append(upper)
        else:
            parts.append(
                "-".join(
                    sub.capitalize()
                    for sub in token.split("-")
                )
            )

    return " ".join(parts)



PLAYER_STOP_WORDS = {
    "auto",
    "autograph",
    "autographs",
    "baseball",
    "basketball",
    "bgs",
    "bowman",
    "card",
    "chiefs",
    "chrome",
    "cosmic",
    "donruss",
    "draft",
    "football",
    "gem",
    "graded",
    "grizzlies",
    "jersey",
    "kc",
    "memphis",
    "mint",
    "mosaic",
    "nfl",
    "nba",
    "panini",
    "patch",
    "prizm",
    "psa",
    "refractor",
    "relic",
    "rookie",
    "sgc",
    "signature",
    "signed",
    "topps",
}


def _normalise_player_display(words: list[str]) -> str | None:
    cleaned: list[str] = []

    for token in words:
        token = token.strip(" -_,:;()[]{}")

        if not token:
            continue

        upper = token.rstrip(".").upper()

        if upper == "JR":
            cleaned.append("Jr.")
        elif upper == "SR":
            cleaned.append("Sr.")
        elif upper in {"II", "III", "IV"}:
            cleaned.append(upper)
        elif (
            token.isupper()
            and len(upper) <= 2
            and upper.isalpha()
        ):
            cleaned.append(upper)
        else:
            cleaned.append(
                "-".join(
                    part.capitalize()
                    for part in token.split("-")
                )
            )

    if len(cleaned) < 2:
        return None

    return " ".join(cleaned)



PLAYER_EDGE_NOISE = {
    "PSA",
    "BGS",
    "SGC",
    "CGC",
    "LAZER",
    "PRIZM",
    "REFRACTOR",
    "CHROME",
    "MOSAIC",
    "DONRUSS",
    "PANINI",
    "TOPPS",
    "BOWMAN",
    "CLEARLY",
    "RETRO",
    "GEM",
    "MT",
    "MINT",
}


def _clean_extracted_player(
    player: str | None,
) -> str | None:
    """
    Remove marketplace/card terminology accidentally captured at
    the edges of an otherwise valid player name.
    """

    if not player:
        return None

    words = player.split()

    while words:
        token = words[0].rstrip(".").upper()

        if token in PLAYER_EDGE_NOISE:
            words.pop(0)
            continue

        break

    while words:
        token = words[-1].rstrip(".").upper()

        if token in PLAYER_EDGE_NOISE:
            words.pop()
            continue

        break

    if len(words) < 2:
        return None

    return _normalise_player_display(words)


def _extract_mixed_case_player(
    title: str,
    brand: str | None,
    parallel: str | None,
) -> str | None:
    """
    Fallback player extraction for marketplace titles where the
    player is not written in Cherry's uppercase convention.

    This deliberately favours precision over recall.
    """

    work = title

    # Remove year.
    work = YEAR_RE.sub(" ", work)

    # Remove grades before name extraction so "JA MORANT PSA"
    # cannot become the player.
    work = GRADE_RE.sub(" ", work)

    # Remove serial numbering and card numbers.
    work = SERIAL_RE.sub(" ", work)
    work = SERIAL_TOTAL_ONLY_RE.sub(" ", work)
    work = CARD_NUMBER_RE.sub(" ", work)

    # Common grading suffix language.
    work = re.sub(
        r"\b(?:GEM\s+MT|GEM\s+MINT|MINT|NM-MT|NM|EX-MT)\b",
        " ",
        work,
        flags=re.I,
    )

    # Remove identified brand/set phrase.
    if brand:
        work = re.sub(
            re.escape(brand),
            " ",
            work,
            flags=re.I,
        )

        if brand.startswith("Panini "):
            short = brand[len("Panini "):]
            work = re.sub(
                re.escape(short),
                " ",
                work,
                flags=re.I,
            )

    # Remove identified parallel phrase.
    if parallel:
        work = re.sub(
            re.escape(parallel),
            " ",
            work,
            flags=re.I,
        )

    # Remove known card terminology.
    terminology = sorted(
        {
            *PARALLEL_TERMS,
            "Panini",
            "Topps",
            "Bowman",
            "Chrome",
            "Prizm",
            "Mosaic",
            "Football",
            "Basketball",
            "Baseball",
            "NFL",
            "NBA",
            "MLB",
            "WNBA",
            "Chiefs",
            "Grizzlies",
            "Memphis",
            "Kansas City",
            "KC",
            "Card",
            "Insert",
            "SP",
            "SSP",
            "RC",
            "Rookie",
            "Auto",
            "Autograph",
            "Autographs",
            "Signature",
            "Signatures",
            "Patch",
            "Relic",
            "Jersey",
            "PSA",
            "BGS",
            "SGC",
            "CGC",
        },
        key=len,
        reverse=True,
    )

    for term in terminology:
        work = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
            " ",
            work,
            flags=re.I,
        )

    # Remove remaining obvious product/card identifiers.
    work = re.sub(
        r"\b(?:B-\d+|SE-\d+|SC-\d+|LS-\d+|RS-[A-Z0-9]+)\b",
        " ",
        work,
        flags=re.I,
    )

    work = re.sub(
        r"[^A-Za-z?-??-??-?'\-\. ]+",
        " ",
        work,
    )

    work = " ".join(work.split())

    if not work:
        return None

    tokens = work.split()

    # Search contiguous 2-4 token runs. Prefer runs containing
    # recognisable name-like tokens and reject card vocabulary.
    candidates: list[tuple[int, int, list[str]]] = []

    for start in range(len(tokens)):
        for length in range(2, 5):
            end = start + length

            if end > len(tokens):
                continue

            words = tokens[start:end]

            lowered = [
                word.rstrip(".").lower()
                for word in words
            ]

            if any(word in PLAYER_STOP_WORDS for word in lowered):
                continue

            if any(
                not re.fullmatch(
                    r"[A-Za-z?-??-??-?][A-Za-z?-??-??-?'\-\.]*",
                    word,
                )
                for word in words
            ):
                continue

            # Suffixes are allowed only at the end.
            suffixes = {"jr", "sr", "ii", "iii", "iv"}

            if any(
                word in suffixes
                for word in lowered[:-1]
            ):
                continue

            # Avoid obvious product phrases that survived stripping.
            phrase = " ".join(lowered)

            reject_phrases = {
                "shadow etch",
                "light speed",
                "star cast",
                "press proof",
                "retro all",
                "all stars",
                "own the",
                "dual jersey",
                "premium stock",
            }

            if any(
                reject in phrase
                for reject in reject_phrases
            ):
                continue

            # Names with a suffix receive a useful preference.
            score = length

            if lowered[-1] in suffixes:
                score += 3

            # Marketplace player names are often title-cased or uppercase.
            score += sum(
                1
                for word in words
                if word[:1].isupper()
            )

            candidates.append(
                (score, -start, words)
            )

    if not candidates:
        return None

    candidates.sort(reverse=True)

    return _normalise_player_display(
        candidates[0][2]
    )


def parse_identity(
    title: str,
    sport: str | None = None,
) -> CardIdentity:

    text = " ".join(title.split())
    lower = text.lower()

    year_match = YEAR_RE.search(text)
    serial_match = SERIAL_RE.search(text)
    serial_total_only_match = (
        None
        if serial_match
        else SERIAL_TOTAL_ONLY_RE.search(text)
    )
    grade_match = GRADE_RE.search(text)
    card_number_match = CARD_NUMBER_RE.search(text)

    brand = _extract_brand(text)
    set_name = _extract_set_name(
        text,
        brand,
    )

    parallel = _extract_parallel(text)

    player = _clean_extracted_player(
        _extract_uppercase_player(text)
    )

    if not player:
        player = _extract_mixed_case_player(
            text,
            brand,
            parallel,
        )

    player = _clean_extracted_player(player)

    rookie = bool(
        re.search(
            r"\b(rc|rookie|1st\s+bowman|1st)\b",
            lower,
        )
    )

    autograph = (
        bool(
            re.search(
                r"\b(auto|autograph|autographs|signature|signatures|signed)\b",
                lower,
            )
        )
        and not bool(
            re.search(
                r"\b(no|non|missing)\s*-?\s*(auto|autograph|signature)\b",
                lower,
            )
        )
    )

    memorabilia = bool(
        re.search(
            r"\b(patch|relic|jersey|memorabilia|material)\b",
            lower,
        )
    )

    return CardIdentity(
        sport=infer_sport(
            text,
            sport,
        ),
        year=year_match.group(0)
        if year_match
        else None,
        brand=brand,
        set_name=set_name,
        player=player,
        card_number=card_number_match.group(1)
        if card_number_match
        else None,
        parallel=parallel,
        serial_current=int(serial_match.group(1))
        if serial_match
        else None,
        serial_total=(
            int(serial_match.group(2))
            if serial_match
            else (
                int(serial_total_only_match.group(1))
                if serial_total_only_match
                else None
            )
        ),
        rookie=rookie,
        autograph=autograph,
        memorabilia=memorabilia,
        grader=grade_match.group(1).upper()
        if grade_match
        else None,
        grade=float(grade_match.group(2))
        if grade_match
        else None,
    )
