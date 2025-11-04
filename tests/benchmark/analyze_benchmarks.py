import json
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import requests

# Use environment variable for security reasons
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "YOUR_REPO_OWNER"
REPO_NAME = "YOUR_REPO_NAME"
WORKFLOW_NAME = "Benchmark"  # As specified in the .yml file
ARTIFACT_NAME = "benchmark-results"

headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def fetch_latest_artifacts() -> None:
    """Fetches the latest artifacts from the GitHub repository."""
    # Get workflow runs
    runs_endpoint = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/{WORKFLOW_NAME}/runs"
    runs = requests.get(runs_endpoint, headers=headers, timeout=10).json()[
        "workflow_runs"
    ]

    for run in runs:
        artifacts_endpoint = run["artifacts_url"]
        artifacts = requests.get(
            artifacts_endpoint, headers=headers, timeout=10
        ).json()["artifacts"]

        for artifact in artifacts:
            if artifact["name"] == ARTIFACT_NAME:
                download_url = artifact["archive_download_url"]
                download_artifact(download_url)


def download_artifact(url: str) -> None:
    """Download the artifact from the given URL."""
    response = requests.get(url, headers=headers, stream=True, timeout=10)
    with Path("artifact.zip").open("wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    with zipfile.ZipFile("artifact.zip", "r") as zip_ref:
        zip_ref.extractall("artifacts")


def load_benchmark_data(filepath: Path) -> List[Dict[str, Any]]:
    """Load benchmark data from a JSON file."""
    with Path(filepath).open("r") as f:
        data = json.load(f)
    return data["benchmarks"]


def main() -> None:
    """Fetches the latest artifacts, loads benchmark data, and plots the performance."""
    fetch_latest_artifacts()

    benchmark_files = [
        Path("artifacts") / f for f in os.listdir("artifacts") if f.endswith(".json")
    ]

    all_data: dict[str, List[float]] = {}

    for bf in benchmark_files:
        data = load_benchmark_data(bf)
        for benchmark in data:
            name = benchmark["name"]
            if name not in all_data:
                all_data[name] = []
            all_data[name].append(benchmark["stats"]["mean"])

    for name, values in all_data.items():
        plt.plot(values, label=name)

    plt.title("Benchmark Performance Over Time")
    plt.xlabel("Run #")
    plt.ylabel("Time (seconds)")
    plt.legend()
    plt.grid(True)
    plt.show()


if __name__ == "__main__":
    main()
