
import os
import json
import html
import urllib.request
import urllib.error

from pathlib import Path


# ==========================================================
# CONFIGURATION
# ==========================================================

USERNAME = os.environ.get("GH_USERNAME", "fauzsanno")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

API_URL = "https://api.github.com"

OUTPUT_FILE = Path("assets/top-langs.svg")

MAX_LANGUAGES = 8

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "GitHub-Profile-Languages-Updater",
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


# ==========================================================
# GITHUB API
# ==========================================================

def github_get(url):

    request = urllib.request.Request(
        url,
        headers=HEADERS
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        message = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"GitHub API error {error.code}: {message}"
        ) from error


# ==========================================================
# FETCH REPOSITORIES
# ==========================================================

def get_repositories():

    print("Fetching GitHub repositories...")

    repositories = []

    page = 1

    while True:

        url = (
            f"{API_URL}/users/{USERNAME}/repos"
            f"?type=owner&per_page=100&page={page}"
        )

        batch = github_get(url)

        if not batch:
            break

        repositories.extend(batch)

        print(
            f"Fetched page {page}: "
            f"{len(batch)} repositories"
        )

        page += 1

    return repositories


# ==========================================================
# CALCULATE LANGUAGE STATISTICS
# ==========================================================

def calculate_languages(repositories):

    print("Calculating programming languages...")

    language_totals = {}

    processed = 0

    for repo in repositories:

        # Skip forked and archived repositories
        if repo.get("fork") or repo.get("archived"):
            continue

        languages_url = repo.get("languages_url")

        if not languages_url:
            continue

        language_data = github_get(languages_url)

        if not language_data:
            continue

        processed += 1

        for language, size in language_data.items():

            language_totals[language] = (
                language_totals.get(language, 0) + size
            )

    print(f"Processed repositories: {processed}")

    if not language_totals:

        raise ValueError(
            "No programming language data found."
        )

    return sorted(
        language_totals.items(),
        key=lambda item: item[1],
        reverse=True
    )


# ==========================================================
# GENERATE SVG CARD
# ==========================================================

def generate_svg(language_totals):

    print("Generating Most Used Languages SVG...")

    top_languages = language_totals[:MAX_LANGUAGES]

    # Use all detected languages as percentage denominator
    total_bytes = sum(
        size for _, size in language_totals
    )

    colors = {
        "Python": "#3572A5",
        "JavaScript": "#f1e05a",
        "TypeScript": "#3178c6",
        "HTML": "#e34c26",
        "CSS": "#563d7c",
        "PHP": "#4F5D95",
        "Java": "#b07219",
        "C": "#555555",
        "C++": "#f34b7d",
        "C#": "#178600",
        "Go": "#00ADD8",
        "Ruby": "#701516",
        "Swift": "#F05138",
        "Kotlin": "#A97BFF",
        "Dart": "#00B4AB",
        "Shell": "#89e051",
        "Jupyter Notebook": "#DA5B0B",
    }

    default_colors = [
        "#8b949e",
        "#bc8cff",
        "#2edac3",
        "#ffa657",
        "#79c0ff",
    ]

    width = 495
    height = 230
    bar_width = 455

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',

        '<rect width="100%" height="100%" '
        'rx="8" fill="#1a1b27"/>',

        '<text x="20" y="30" fill="#70a5fd" '
        'font-size="16" font-weight="bold" '
        'font-family="Arial, sans-serif">'
        'Most Used Languages</text>',
    ]

    # Language distribution bar
    current_x = 20

    for index, (language, size) in enumerate(top_languages):

        percentage = size / total_bytes

        segment_width = bar_width * percentage

        color = colors.get(
            language,
            default_colors[index % len(default_colors)]
        )

        if segment_width > 0:

            svg.append(
                f'<rect x="{current_x:.2f}" y="48" '
                f'width="{segment_width:.2f}" '
                f'height="9" fill="{color}"/>'
            )

        current_x += segment_width

    # Language labels
    for index, (language, size) in enumerate(top_languages):

        percentage = size / total_bytes * 100

        color = colors.get(
            language,
            default_colors[index % len(default_colors)]
        )

        y = 83 + index * 18

        svg.append(
            f'<circle cx="25" cy="{y - 4}" '
            f'r="4" fill="{color}"/>'
        )

        svg.append(
            f'<text x="38" y="{y}" '
            f'font-size="11" fill="#c9d1d9" '
            f'font-family="Arial, sans-serif">'
            f'{html.escape(language)}</text>'
        )

        svg.append(
            f'<text x="465" y="{y}" '
            f'text-anchor="end" '
            f'font-size="11" fill="#8b949e" '
            f'font-family="Arial, sans-serif">'
            f'{percentage:.1f}%</text>'
        )

    svg.append('</svg>')

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        "\n".join(svg),
        encoding="utf-8"
    )

    print(f"SVG generated successfully: {OUTPUT_FILE}")


# ==========================================================
# MAIN
# ==========================================================

def main():

    print("=" * 50)
    print("GITHUB MOST USED LANGUAGES UPDATER")
    print("=" * 50)

    print(f"GitHub username: {USERNAME}")

    repositories = get_repositories()

    if not repositories:

        raise ValueError(
            "No repositories found for this account."
        )

    # Only repositories owned by the account are counted
    owned_repositories = [
        repo for repo in repositories
        if repo.get("owner", {}).get("login", "").lower()
        == USERNAME.lower()
    ]

    print(
        f"Total owned repositories: "
        f"{len(owned_repositories)}"
    )

    language_totals = calculate_languages(
        owned_repositories
    )

    generate_svg(language_totals)

    print("\nTop programming languages:")

    total_bytes = sum(
        size for _, size in language_totals
    )

    for language, size in language_totals[:MAX_LANGUAGES]:

        percentage = size / total_bytes * 100

        print(
            f"{language}: {percentage:.2f}%"
        )

    print("\nLanguage statistics updated successfully!")


if __name__ == "__main__":
    main()

