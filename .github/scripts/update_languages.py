
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict


# ==================================================
# CONFIGURATION
# ==================================================
USERNAME = os.environ.get("GH_USERNAME", "fauzsanno")

# Dedicated token for reading repositories, including private ones.
# Falls back to GITHUB_TOKEN, but that token may not access other repos.
TOKEN = os.environ.get("GH_API_TOKEN") or os.environ.get("GITHUB_TOKEN")

README_PATH = "README.md"

START_MARKER = "<!--START_SECTION:languages-->"
END_MARKER = "<!--END_SECTION:languages-->"

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"

# Safety: never expose private repository names in a public README.
SHOW_PRIVATE_REPO_NAMES = False

# Number of language bars shown in the summary.
MAX_LANGUAGES = 10


# ==================================================
# GITHUB API
# ==================================================
def api_get(url):
    """Send an authenticated GET request to GitHub REST API."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "github-language-readme",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError(
                "GitHub token is invalid or expired."
            ) from exc
        if exc.code == 403:
            raise RuntimeError(
                "GitHub API access denied. Check token permissions "
                "and API rate limits."
            ) from exc
        if exc.code == 404:
            raise RuntimeError(
                "GitHub resource not found or not accessible. "
                "Check repository access permissions."
            ) from exc
        raise RuntimeError(
            f"GitHub API returned HTTP {exc.code}."
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not connect to GitHub API: {exc.reason}"
        ) from exc


def fetch_repositories():
    """
    Fetch all repositories owned by the authenticated account.
    Includes public and private repositories accessible to TOKEN.
    """
    if not TOKEN:
        raise RuntimeError(
            "Missing GH_API_TOKEN or GITHUB_TOKEN."
        )

    repositories = []
    page = 1

    while True:
        params = urllib.parse.urlencode({
            "visibility": "all",
            "affiliation": "owner",
            "sort": "full_name",
            "direction": "asc",
            "per_page": 100,
            "page": page,
        })

        url = f"{API_BASE}/user/repos?{params}"
        batch = api_get(url)

        if not isinstance(batch, list):
            raise RuntimeError(
                "Unexpected response when listing repositories."
            )

        repositories.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return repositories


def fetch_repository_languages(owner, repo):
    """Return language-to-byte-count mapping for one repository."""
    owner = urllib.parse.quote(owner, safe="")
    repo = urllib.parse.quote(repo, safe="")

    url = f"{API_BASE}/repos/{owner}/{repo}/languages"
    result = api_get(url)

    if not isinstance(result, dict):
        raise RuntimeError(
            f"Unexpected language response for {owner}/{repo}."
        )

    return result


# ==================================================
# LANGUAGE STATISTICS
# ==================================================
def calculate_statistics(repositories):
    total_bytes = defaultdict(int)
    repository_results = []

    private_count = 0
    public_count = 0

    for repository in repositories:
        owner = repository["owner"]["login"]
        name = repository["name"]
        full_name = repository["full_name"]
        is_private = repository["private"]

        if is_private:
            private_count += 1
        else:
            public_count += 1

        languages = fetch_repository_languages(owner, name)

        # Aggregate all accessible repositories, including private.
        for language, byte_count in languages.items():
            total_bytes[language] += int(byte_count)

        repository_results.append({
            "name": name,
            "full_name": full_name,
            "url": repository["html_url"],
            "private": is_private,
            "languages": languages,
            "primary_language": max(
                languages, key=languages.get
            ) if languages else "Not detected",
        })

    return (
        dict(total_bytes),
        repository_results,
        public_count,
        private_count,
    )


# ==================================================
# MARKDOWN GENERATION
# ==================================================
def make_language_bar(percentage, width=20):
    """Generate a text-based bar that renders in GitHub Markdown."""
    filled = round(percentage / 100 * width)
    return "█" * filled + "░" * (width - filled)


def build_markdown(
    total_bytes,
    repositories,
    public_count,
    private_count,
):
    lines = [
        "### Programming Languages Across Repositories",
        "",
        (
            f"> Analysis covers **{len(repositories)} repositories**: "
            f"{public_count} public and {private_count} private."
        ),
        (
            "> Private repositories contribute to aggregate language "
            "statistics, but their names are hidden."
        ),
        "",
    ]

    total = sum(total_bytes.values())

    if total == 0:
        lines.append(
            "_No detectable programming language statistics found._"
        )
    else:
        lines.extend([
            "#### Language Distribution",
            "",
            "| Language | Percentage | Distribution | Code size |",
            "|---|---:|---|---:|",
        ])

        sorted_languages = sorted(
            total_bytes.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        for language, byte_count in sorted_languages[:MAX_LANGUAGES]:
            percentage = byte_count / total * 100
            bar = make_language_bar(percentage)

            lines.append(
                f"| {language} | {percentage:.2f}% "
                f"| `{bar}` | {byte_count:,} bytes |"
            )

        lines.extend([
            "",
            (
                f"_Percentages are calculated across all detected "
                f"language bytes ({total:,} bytes)._"
            ),
        ])

    # Public repositories are listed by name.
    # Private repository names are hidden by default.
    visible_repositories = [
        repo for repo in repositories
        if not repo["private"] or SHOW_PRIVATE_REPO_NAMES
    ]

    lines.extend([
        "",
        "#### Repository Breakdown",
        "",
        "| Repository | Visibility | Primary Language | Languages Detected |",
        "|---|---|---|---|",
    ])

    for repo in visible_repositories:
        if repo["private"]:
            display_name = repo["full_name"]
            visibility = "Private"
        else:
            display_name = (
                f"[{repo['full_name']}]({repo['url']})"
            )
            visibility = "Public"

        languages = ", ".join(
            sorted(
                repo["languages"],
                key=repo["languages"].get,
                reverse=True,
            )
        ) or "Not detected"

        # Escape table delimiters in repository metadata.
        display_name = display_name.replace("|", r"\|")
        languages = languages.replace("|", r"\|")

        lines.append(
            f"| {display_name} | {visibility} "
            f"| {repo['primary_language']} | {languages} |"
        )

    hidden_count = len(repositories) - len(visible_repositories)

    if hidden_count:
        lines.extend([
            "",
            (
                f"_Names of {hidden_count} private repository/repositories "
                "are hidden for privacy._"
            ),
        ])

    return "\n".join(lines)


def update_readme(section_content):
    """Replace only the section between language markers."""
    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if START_MARKER not in readme or END_MARKER not in readme:
        raise ValueError(
            "Language markers are missing from README.md."
        )

    start = readme.index(START_MARKER)
    end = readme.index(END_MARKER) + len(END_MARKER)

    section = (
        START_MARKER
        + "\n"
        + section_content
        + "\n"
        + END_MARKER
    )

    updated_readme = readme[:start] + section + readme[end:]

    if updated_readme != readme:
        with open(README_PATH, "w", encoding="utf-8") as file:
            file.write(updated_readme)

        print("README language statistics updated.")
    else:
        print("README language statistics are already up to date.")


# ==================================================
# MAIN
# ==================================================
def main():
    print(f"Fetching repositories for {USERNAME}...")

    repositories = fetch_repositories()

    # /user/repos lists repositories accessible to the token.
    # Keep only repositories owned by the configured account.
    repositories = [
        repo for repo in repositories
        if repo.get("owner", {}).get("login", "").lower()
        == USERNAME.lower()
    ]

    print(f"Found {len(repositories)} owned repositories.")

    (
        total_bytes,
        repository_results,
        public_count,
        private_count,
    ) = calculate_statistics(repositories)

    section_content = build_markdown(
        total_bytes,
        repository_results,
        public_count,
        private_count,
    )

    update_readme(section_content)


if __name__ == "__main__":
    main()

