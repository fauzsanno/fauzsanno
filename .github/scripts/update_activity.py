import json
import os
import urllib.request
from datetime import datetime, timezone

USERNAME = os.environ["GH_USERNAME"]
TOKEN = os.environ["GITHUB_TOKEN"]
MAX_LINES = int(os.environ.get("MAX_LINES", "5"))

README_PATH = "README.md"
START_MARKER = "<!--START_SECTION:activity-->"
END_MARKER = "<!--END_SECTION:activity-->"

API_URL = (
    f"https://api.github.com/users/{USERNAME}/events/public?per_page=100"
)


def fetch_events():
    request = urllib.request.Request(
        API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-activity-readme",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def describe_event(event):
    event_type = event.get("type", "")
    repo = event.get("repo", {}).get("name", "")
    payload = event.get("payload", {})
    repo_url = f"https://github.com/{repo}"

    if event_type == "PushEvent":
        commits = payload.get("commits", [])
        count = payload.get("size", len(commits))

        if commits:
            sha = commits[-1].get("sha", "")
            commit_url = f"{repo_url}/commit/{sha}"
            return (
                f"pushed {count} commit(s) to "
                f"[{repo}]({repo_url}) · "
                f"[view commit]({commit_url})"
            )

        return f"pushed code to [{repo}]({repo_url})"

    if event_type == "CreateEvent":
        ref_type = payload.get("ref_type", "resource")
        ref = payload.get("ref")
        detail = f" `{ref}`" if ref else ""
        return f"created {ref_type}{detail} in [{repo}]({repo_url})"

    if event_type == "PullRequestEvent":
        action = payload.get("action", "updated")
        pr = payload.get("pull_request", {})
        number = pr.get("number")
        url = pr.get("html_url", repo_url)
        return (
            f"{action} a pull request in [{repo}]({repo_url}) · "
            f"[#{number}]({url})"
            if number
            else f"{action} a pull request in [{repo}]({repo_url})"
        )

    if event_type == "IssuesEvent":
        action = payload.get("action", "updated")
        issue = payload.get("issue", {})
        number = issue.get("number")
        url = issue.get("html_url", repo_url)
        return (
            f"{action} an issue in [{repo}]({repo_url}) · "
            f"[#{number}]({url})"
            if number
            else f"{action} an issue in [{repo}]({repo_url})"
        )

    if event_type == "IssueCommentEvent":
        return f"commented on an issue or pull request in [{repo}]({repo_url})"

    if event_type == "WatchEvent":
        return f"starred [{repo}]({repo_url})"

    if event_type == "ForkEvent":
        fork = payload.get("forkee", {}).get("html_url", repo_url)
        return f"forked [{repo}]({repo_url}) · [view fork]({fork})"

    if event_type == "ReleaseEvent":
        release = payload.get("release", {})
        url = release.get("html_url", repo_url)
        return f"published a release in [{repo}]({repo_url}) · [view release]({url})"

    if event_type == "PublicEvent":
        return f"made [{repo}]({repo_url}) public"

    return None


def main():
    with open(README_PATH, "r", encoding="utf-8") as file:
        readme = file.read()

    if START_MARKER not in readme or END_MARKER not in readme:
        raise ValueError(
            "Activity markers were not found in README.md."
        )

    events = fetch_events()
    lines = []

    for event in events:
        description = describe_event(event)

        if not description:
            continue

        created_at = datetime.strptime(
            event["created_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)

        date = created_at.strftime("%d %b %Y")
        lines.append(f"- **{date}** — {description}")

        if len(lines) >= MAX_LINES:
            break

    if not lines:
        lines.append(
            "_No recent public GitHub activity was found._"
        )

    section = (
        START_MARKER
        + "\n"
        + "\n".join(lines)
        + "\n"
        + END_MARKER
    )

    start = readme.index(START_MARKER)
    end = readme.index(END_MARKER) + len(END_MARKER)

    updated_readme = readme[:start] + section + readme[end:]

    if updated_readme != readme:
        with open(README_PATH, "w", encoding="utf-8") as file:
            file.write(updated_readme)

        print("README activity section updated.")
    else:
        print("README activity section is already up to date.")


if __name__ == "__main__":
    main()
