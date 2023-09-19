from typing import List
import argparse
import json
import os

import urllib.error
from urllib.request import Request, urlopen


token_env_key = "GITLAB_TOKEN"
default_ci_config_path = ".gitlab-ci.yml"

parser = argparse.ArgumentParser()
parser.add_argument("url", nargs="?", default="https://gitlab.com/api/v4")
parser.add_argument(
    "--token",
    default=os.getenv(token_env_key),
    help=(
        "GitLab personal access token. "
        "As default the value of {} environmental variable is used.".format(
            token_env_key
        )
    ),
)


def print_messages(messages: List[str]):
    print("=======")
    for msg in messages:
        print(msg)
    print("=======")


def urlerr(err, token):
    print("Error connecting to Gitlab: " + str(err))
    if not token and isinstance(err, urllib.error.HTTPError) and err.code == 401:
        print(
            "The lint endpoint requires authentication."
            "Please set {} environment variable".format(token_env_key)
        )


def main(argv=None):
    args = parser.parse_args(argv)
    url = args.url
    if url.endswith("/"):
        url = url.rstrip("/")
    lint_ext = "/ci/lint"
    if url.endswith(lint_ext):
        url = url.rstrip(lint_ext)
    token = args.token
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["PRIVATE-TOKEN"] = token

    rv = 0
    try:
        response = urlopen(Request(url, headers=headers))
        project_info = json.loads(response.read())
        if "ci_config_path" in project_info and project_info["ci_config_path"]:
            ci_config_path = project_info["ci_config_path"]
        else:
            # Use the default path for the gitlab-ci.yml file
            ci_config_path = default_ci_config_path
    except urllib.error.URLError:
        ci_config_path = default_ci_config_path

    try:
        with open(ci_config_path, "r") as f:
            data = json.dumps({"content": f.read()})
    except (FileNotFoundError, PermissionError):
        print(f"Cannot open {ci_config_path}")
        return 11

    url += lint_ext
    headers["Content-Length"] = len(data)
    msg_using_linter = "Using linter: " + url
    if token:
        msg_using_linter += " with token " + len(token) * "*"
    print(msg_using_linter)
    try:
        request = Request(
            url,
            data.encode("utf-8"),
            headers=headers,
        )
        response = urlopen(request)
        lint_output = json.loads(response.read())

        if "status" in lint_output:
            # Gitlab version < 15.7
            if not lint_output["status"] == "valid":
                print_messages(lint_output["errors"])
                rv = 1
            elif lint_output["warnings"]:
                print_messages(lint_output["warnings"])
        elif "valid" in lint_output:
            # Gitlab version > 15.7
            if not lint_output["valid"]:
                print_messages(lint_output["errors"])
                rv = 2
            elif lint_output["warnings"]:
                print_messages(lint_output["warnings"])
        else:
            # Gitlab changed its output again?
            print(
                "Unknown gitlab response. Did gitlab update the ci linter response again?"
            )
            rv = 3
    except urllib.error.URLError as err:
        urlerr(err, token)
        return 12
    return rv


if __name__ == "__main__":
    exit(main())
