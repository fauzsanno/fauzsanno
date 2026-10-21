
import json
import os
import urllib.error
import urllib.parse
import urllib.request

USERNAME = os.getenv("GH_USERNAME", "fauzsanno")
TOKEN = os.getenv("GH_API_TOKEN") or os.getenv("GITHUB_TOKEN")

README_PATH = "README.md"
START_MARKER = "<!--START_SECTION:languages-->"
END_MARKER = "<!--END_SECTION:languages-->"

API_URL = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def github_get(url):
    request = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API error {error.code}: {detail}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Cannot connect to GitHub API: {error.reason}"
        ) from error


def get_owned_repositories():
    repositories = []
    page = 1

    while True:
        query = urllib.parse.urlencode({
            "visibility": "all",
            "affiliation": "owner",
            "per_page": 100,
            "page": page,
            "sort": "full_name",
        })

        url = f"{API_URL}/user/repos?{query}"
        batch = github_get(url)

        if not batch:
            break

        for repo in batch:
            owner = repo.get("owner", {}).get("login", "")

            if owner.lower() == USERNAME.lower():
                repositories.append(repo)

        if len(batch) < 100:
            break

        page += 1

    return repositories


def collect_languages(repositories):
    totals = {}
    analyzed_repositories = 0

    for repo in repositories:
        repo_name = repo["full_name"]
        encoded_name = urllib.parse.quote(repo_name, safe="/")

        url = f"{API_URL}/repos/{encoded_name}/languages"
        languages = github_get(url)

        if languages:
            analyzed_repositories += 1

        for language, byte_count in languages.items():
            totals[language] = totals.get(language, 0) + byte_count

    return totals, analyzed_repositories


def build_language_section(totals, repositories, analyzed):
    total_bytes = sum(totals.values())
    private_count = sum(1 for repo in repositories if repo.get("private"))

    lines = [
        "### Programming Languages Across Repositories",
        "",
        (
            f"Repositories: **{len(repositories)}** "
            f"| Private repositories: **{private_count}** "
            f"| Repositories with language data: **{analyzed}**"
        ),
        "",
    ]

    if total_bytes == 0:
        lines.extend([
            "No programming language data was returned by GitHub.",
            "",
            "Check the token permissions and repository access.",
        ])
        return "\n".join(lines)

    lines.extend([
        "| Language | Usage | Percentage |",
        "|---|---|---:|",
    ])

    sorted_languages = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    for language, byte_count in sorted_languages:
        percentage = byte_count / total_bytes * 100
        filled = round(percentage / 5)
        bar = "█" * filled + "░" * (20 - filled)

        lines.append(
            f"| {language} | `{bar}` | {percentage:.2f}% |"
        )

    lines.extend([
        "",
        "_Automatically updated using GitHub repository language data._",
    ])

    return "\n".join(lines)


def update_readme(content):
    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if START_MARKER not in readme or END_MARKER not in readme:
        raise RuntimeError(
            "Language markers are missing from README.md."
        )

    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER, start)

    updated = (
        readme[:start]
        + "\n"
        + content
        + "\n"
        + readme[end:]
    )

    if updated != readme:
        with open(README_PATH, "w", encoding="utf-8") as file:
            file.write(updated)
        print("README language statistics updated.")
    else:
        print("Language statistics are already up to date.")


def main():
    if not TOKEN:
        raise RuntimeError(
            "Missing GH_API_TOKEN or GITHUB_TOKEN."
        )

    print(f"Loading repositories for {USERNAME}...")

    repositories = get_owned_repositories()
    print(f"Found {len(repositories)} owned repositories.")

    totals, analyzed = collect_languages(repositories)

    print(f"Collected {len(totals)} programming languages.")

    content = build_language_section(
        totals,
        repositories,
        analyzed,
    )

    update_readme(content)


if __name__ == "__main__":
    main()
