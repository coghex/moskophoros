#!/usr/bin/env python3
"""The registry transport ``image.py`` decides with.

``image.py`` owns every decision; this answers its four requests against the
GitHub Container Registry and the Docker CLI. See ``image.py`` for the
protocol. A lookup authenticates with ``REGISTRY_USER`` and ``REGISTRY_TOKEN``
when both are set, and anonymously otherwise.

Exit status: 0 on success, 3 when a lookup is answered with a confirmed
absence, and 2 for anything else. A registry response that is not a plain
answer is an error, never an absence.
"""

import base64
import importlib.util
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True

_spec = importlib.util.spec_from_file_location(
    "image", os.path.join(os.path.dirname(os.path.abspath(__file__)), "image.py")
)
image = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(image)

ABSENT_CODES = ("MANIFEST_UNKNOWN", "NAME_UNKNOWN")
MANIFEST_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)
INDEX_TYPES = MANIFEST_TYPES[:2]
PLATFORM = "linux/amd64"

# Runs inside the image and reports what it actually contains.
INSPECTION = f"""
import importlib.util, json, platform, shutil, subprocess

def run(*command):
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()

print(json.dumps({{
    "embedded": json.load(open({image.EMBEDDED_PATH!r})),
    "python": platform.python_version(),
    "python_path": shutil.which("python3"),
    "pytest": run("pytest", "--version"),
    "ruff": run("ruff", "--version"),
    "git": run("git", "--version"),
    "bash": run("bash", "-c", "echo $BASH_VERSION"),
    "blender": shutil.which("blender"),
    "moskophoros": importlib.util.find_spec("moskophoros") is not None,
}}))
"""


class TransportError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def request(url: str, headers: dict[str, str]) -> tuple[int, dict, bytes]:
    """One GET, following redirects without forwarding credentials.

    Blob downloads redirect to object storage, which refuses a request carrying
    the registry's bearer token beside its own signature.
    """
    for _ in range(5):
        try:
            with OPENER.open(
                urllib.request.Request(url, headers=headers), timeout=60
            ) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as error:
            if error.code in (301, 302, 303, 307, 308) and error.headers.get(
                "Location"
            ):
                url = urllib.parse.urljoin(url, error.headers["Location"])
                headers = {
                    name: value
                    for name, value in headers.items()
                    if name.lower() != "authorization"
                }
                continue
            return error.code, dict(error.headers), error.read()
        except OSError as error:
            raise TransportError(f"GET {url} did not answer: {error}") from error
    raise TransportError(f"GET {url} redirected too many times")


def split_reference(reference: str) -> tuple[str, str, str]:
    registry, _, rest = reference.partition("/")
    repository, separator, tag = rest.rpartition(":")
    if not registry or not separator or not repository or not tag or "@" in rest:
        raise TransportError(f"{reference!r} is not REGISTRY/REPOSITORY:TAG")
    return registry, repository, tag


def bearer(registry: str, repository: str) -> str:
    url = f"https://{registry}/token?service={registry}&scope=repository:{repository}:pull"
    headers = {}
    user, token = os.environ.get("REGISTRY_USER"), os.environ.get("REGISTRY_TOKEN")
    if user and token:
        headers["Authorization"] = (
            "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode()
        )
    status, _, body = request(url, headers)
    if status != 200:
        raise TransportError(f"the token endpoint answered {status}: {body[:200]!r}")
    value = json.loads(body).get("token") or json.loads(body).get("access_token")
    if not value:
        raise TransportError("the token endpoint returned no token")
    return value


def error_codes(body: bytes) -> list[str]:
    try:
        errors = json.loads(body).get("errors") or []
    except (ValueError, AttributeError):
        return []
    return [entry.get("code") for entry in errors if isinstance(entry, dict)]


def lookup(reference: str) -> int:
    registry, repository, tag = split_reference(reference)
    authorization = {"Authorization": "Bearer " + bearer(registry, repository)}
    base = f"https://{registry}/v2/{repository}"
    accept = {**authorization, "Accept": ", ".join(MANIFEST_TYPES)}
    status, headers, body = request(f"{base}/manifests/{tag}", accept)
    if status == 404:
        codes = error_codes(body)
        if codes and all(code in ABSENT_CODES for code in codes):
            return image.ABSENT
        raise TransportError(
            f"the manifest request answered 404 without a confirmed absence: {body[:300]!r}"
        )
    if status != 200:
        raise TransportError(f"the manifest request answered {status}: {body[:300]!r}")
    digest = {name.lower(): value for name, value in headers.items()}.get(
        "docker-content-digest"
    )
    if not digest:
        raise TransportError("the manifest response names no Docker-Content-Digest")
    manifest = json.loads(body)
    if manifest.get("mediaType") in INDEX_TYPES or "manifests" in manifest:
        chosen = [
            entry
            for entry in manifest.get("manifests", [])
            if f"{entry.get('platform', {}).get('os')}/{entry.get('platform', {}).get('architecture')}"
            == PLATFORM
        ]
        if len(chosen) != 1:
            raise TransportError(
                f"the image index does not name exactly one {PLATFORM} manifest"
            )
        status, _, body = request(f"{base}/manifests/{chosen[0]['digest']}", accept)
        if status != 200:
            raise TransportError(f"the platform manifest request answered {status}")
        manifest = json.loads(body)
    config = manifest.get("config", {}).get("digest")
    if not config:
        raise TransportError("the manifest names no config blob")
    status, _, body = request(f"{base}/blobs/{config}", authorization)
    if status != 200:
        raise TransportError(f"the config blob request answered {status}")
    labels = (json.loads(body).get("config") or {}).get("Labels") or {}
    print(json.dumps({"digest": digest, "labels": labels}, sort_keys=True))
    return 0


def docker(*arguments: str, capture: bool = False) -> str:
    """Run Docker, its diagnostics and any uncaptured output going to standard error."""
    process = subprocess.run(
        ["docker", *arguments],
        stdout=subprocess.PIPE if capture else sys.stderr,
        check=False,
    )
    if process.returncode != 0:
        raise TransportError(f"docker {arguments[0]} exited {process.returncode}")
    return process.stdout.decode("utf-8", errors="replace") if capture else ""


def build(context: str, local: str, fingerprint: str) -> int:
    arguments = [
        "build",
        "--platform", PLATFORM,
        "--build-arg", f"RECIPE_FINGERPRINT={fingerprint}",
        "--file", os.path.join(context, "tools", "ci-image", "Dockerfile"),
        "--tag", local,
    ]  # fmt: skip
    docker(*arguments, context)
    embedded = json.loads(
        docker(
            "run",
            "--rm",
            "--platform",
            PLATFORM,
            local,
            "cat",
            image.EMBEDDED_PATH,
            capture=True,
        )
    )
    # The versions exist only once the image does, so the labels a lookup reads
    # are applied by a second build that every layer of the first satisfies.
    labelled = list(arguments)
    for name in image.RECORDED:
        labelled += ["--label", f"{image.label(name)}={embedded[name]}"]
    docker(*labelled, context)
    print(json.dumps(embedded, sort_keys=True))
    return 0


def inspect(reference: str) -> int:
    report = json.loads(
        docker(
            "run",
            "--rm",
            "--platform",
            PLATFORM,
            reference,
            "python3",
            "-c",
            INSPECTION,
            capture=True,
        )
    )
    report["labels"] = (
        json.loads(
            docker(
                "image",
                "inspect",
                "--format",
                "{{json .Config.Labels}}",
                reference,
                capture=True,
            )
        )
        or {}
    )
    print(json.dumps(report, sort_keys=True))
    return 0


def push(local: str, reference: str) -> int:
    docker("tag", local, reference)
    docker("push", reference)
    return 0


def main(argv: list[str]) -> int:
    handlers = {
        "lookup": (lookup, 1),
        "build": (build, 3),
        "inspect": (inspect, 1),
        "push": (push, 2),
    }
    if not argv or argv[0] not in handlers or len(argv) - 1 != handlers[argv[0]][1]:
        raise TransportError(f"unknown or malformed registry request: {' '.join(argv)}")
    return handlers[argv[0]][0](*argv[1:])


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (TransportError, ValueError, KeyError) as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(2)
