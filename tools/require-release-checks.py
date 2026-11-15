#!/usr/bin/env python3
"""Do not publish an OS image until its exact source passed general and desktop CI."""
import json
import os
import re
import subprocess
import time
import urllib.request


def check_runs(runs, jobs):
    pending = not runs
    for run in runs:
        results = {job["name"]: job["conclusion"] for job in jobs(run["id"])}
        if all(results.get(name) == "success" for name in ("test", "desktop")):
            return True
        pending |= run["status"] != "completed"
    if not pending:
        raise RuntimeError("No successful general and desktop checks for this source commit")
    return False


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Invalid release source")
    base = os.environ.get("GITHUB_API_URL", "https://api.github.com") + "/repos/" + repository

    def get(path):
        request = urllib.request.Request(base + path, headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Accept": "application/vnd.github+json",
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    deadline = time.monotonic() + 1800
    while True:
        runs = get("/actions/workflows/build.yml/runs?per_page=30&head_sha=" + revision)["workflow_runs"]
        runs = [run for run in runs if run["head_sha"] == revision]
        if check_runs(runs, lambda ident: get(f"/actions/runs/{ident}/jobs?per_page=100")["jobs"]):
            print("General and desktop checks passed for " + revision, flush=True)
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("Timed out waiting for release checks; no image was published")
        print("Waiting for general and desktop checks for " + revision, flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
