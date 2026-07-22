#!/usr/bin/env python3
"""Extract a Loom transcript and optional timestamped frames."""

from __future__ import annotations

import argparse
import html
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Collection


USER_AGENT = "Mozilla/5.0 (compatible; LoomMediaSkill/1.0)"
LOOM_HOSTS = frozenset({"loom.com", "www.loom.com"})
VIDEO_PATH = re.compile(r"^/(?:share|embed)/([A-Za-z0-9_-]+)/?$")
# HLS needs encrypted-data and HTTPS transport protocols; local-file and broad
# network protocols are intentionally excluded from ffmpeg's input allowlist.
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
FFMPEG_PROTOCOLS = "crypto,data,https,tcp,tls"


class LoomError(RuntimeError):
    """An expected, user-actionable Loom extraction error."""


def parsed_https_url(url: str, label: str) -> urllib.parse.SplitResult:
    if not isinstance(url, str) or not url.strip():
        raise LoomError(f"{label} must be a non-empty HTTPS URL.")
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise LoomError(f"{label} is not a valid HTTPS URL.") from error
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise LoomError(f"{label} must be an HTTPS URL.")
    if parsed.username is not None or parsed.password is not None:
        raise LoomError(f"{label} must not contain embedded credentials.")
    if port not in (None, 443):
        raise LoomError(f"{label} must use the default HTTPS port.")
    return parsed


def validate_remote_https_url(
    url: str, label: str, allowed_hosts: Collection[str] | None = None
) -> urllib.parse.SplitResult:
    parsed = parsed_https_url(url, label)
    host = (parsed.hostname or "").lower().rstrip(".")
    if allowed_hosts is not None and host not in allowed_hosts:
        raise LoomError(f"{label} must use an approved Loom host.")
    if host == "localhost" or host.endswith(".localhost"):
        raise LoomError(f"{label} must not target a local host.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise LoomError(f"{label} must not target a non-public address.")
    return parsed


def validate_resolved_remote_url(
    url: str, label: str, allowed_hosts: Collection[str] | None = None
) -> urllib.parse.SplitResult:
    parsed = validate_remote_https_url(url, label, allowed_hosts)
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    if literal is not None:
        addresses = {literal}
    else:
        try:
            answers = socket.getaddrinfo(
                host,
                443,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
        except socket.gaierror as error:
            raise LoomError(f"Could not resolve {label.lower()} host: {error}") from error
        addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
        for family, _type, _proto, _canonical, sockaddr in answers:
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue
            try:
                addresses.add(ipaddress.ip_address(sockaddr[0].split("%", 1)[0]))
            except ValueError as error:
                raise LoomError(f"{label} resolved to an invalid address.") from error

    if not addresses:
        raise LoomError(f"{label} host resolved to no A or AAAA addresses.")
    non_global = sorted(str(address) for address in addresses if not address.is_global)
    if non_global:
        raise LoomError(
            f"{label} host resolved to a non-public address; refusing network access."
        )
    return parsed


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: Collection[str] | None) -> None:
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        validate_resolved_remote_url(newurl, "Redirect URL", self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def redact_sensitive(text: str, secrets: Collection[str] = ()) -> str:
    redacted = text
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        redacted = redacted.replace(secret, "<redacted>")
    redacted = re.sub(
        r"(?i)(CloudFront-(?:Policy|Signature|Key-Pair-Id)=)[^;\s]+",
        r"\1<redacted>",
        redacted,
    )
    redacted = re.sub(r"(?i)(Cookie:\s*)[^\r\n]+", r"\1<redacted>", redacted)
    redacted = re.sub(r"https://[^\s\"']+", "<redacted-url>", redacted)
    return redacted[:4000]


def fetch_bytes(
    url: str, label: str, allowed_hosts: Collection[str] | None = None
) -> bytes:
    validate_resolved_remote_url(url, label, allowed_hosts)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(SafeRedirectHandler(allowed_hosts))
    try:
        with opener.open(request, timeout=45) as response:
            validate_resolved_remote_url(response.geturl(), label, allowed_hosts)
            length = response.headers.get("Content-Length")
            if length and length.isdigit() and int(length) > MAX_DOWNLOAD_BYTES:
                raise LoomError(f"{label} exceeds the 50 MiB download limit.")
            body = response.read(MAX_DOWNLOAD_BYTES + 1)
    except LoomError:
        raise
    except (OSError, urllib.error.URLError) as error:
        detail = redact_sensitive(str(error), (url,))
        raise LoomError(f"Could not fetch {label.lower()}: {detail}") from error
    if len(body) > MAX_DOWNLOAD_BYTES:
        raise LoomError(f"{label} exceeds the 50 MiB download limit.")
    return body


def video_id_from_url(url: str) -> str:
    parsed = validate_remote_https_url(url, "Loom URL", LOOM_HOSTS)
    match = VIDEO_PATH.fullmatch(parsed.path)
    if not match:
        raise LoomError("Expected an HTTPS Loom /share/<id> or /embed/<id> URL.")
    return match.group(1)


def public_source_url(url: str) -> str:
    parsed = parsed_https_url(url, "Loom URL")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def extract_apollo_state(page: str) -> dict[str, Any]:
    match = re.search(
        r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\});\s*</script>",
        page,
        flags=re.DOTALL,
    )
    if not match:
        raise LoomError(
            "Loom did not expose page metadata to this session; the video may require authentication."
        )
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise LoomError(f"Loom page metadata was not valid JSON: {error}") from error


def find_video(state: dict[str, Any], video_id: str) -> dict[str, Any]:
    video = state.get(f"RegularUserVideo:{video_id}")
    if not isinstance(video, dict):
        raise LoomError("Video metadata was unavailable to this session.")
    if video.get("needs_password"):
        raise LoomError("This Loom requires a password or authenticated access.")
    return video


def find_transcript_details(state: dict[str, Any], video_id: str) -> dict[str, Any]:
    for key, value in state.items():
        if (
            key.startswith("VideoTranscriptDetails:")
            and isinstance(value, dict)
            and value.get("video_id") == video_id
        ):
            return value
    raise LoomError("No transcript is exposed for this Loom video.")


def parse_transcript(details: dict[str, Any]) -> list[dict[str, Any]]:
    source_url = details.get("source_url")
    if not isinstance(source_url, str) or not source_url:
        raise LoomError("The Loom transcript has no accessible source URL.")
    try:
        payload = json.loads(fetch_bytes(source_url, "Transcript URL"))
    except json.JSONDecodeError as error:
        raise LoomError(f"Loom transcript was not valid JSON: {error}") from error

    phrases = payload.get("phrases") if isinstance(payload, dict) else None
    if not isinstance(phrases, list) or not phrases:
        raise LoomError("The Loom transcript contains no phrases.")

    parsed: list[dict[str, Any]] = []
    previous = -1.0
    for index, phrase in enumerate(phrases):
        if not isinstance(phrase, dict):
            raise LoomError(f"Transcript phrase {index} is malformed.")
        timestamp = phrase.get("ts")
        value = phrase.get("value")
        if (
            not isinstance(timestamp, (int, float))
            or isinstance(timestamp, bool)
            or not math.isfinite(timestamp)
            or timestamp < 0
            or timestamp < previous
            or not isinstance(value, str)
        ):
            raise LoomError(f"Transcript phrase {index} has invalid fields.")
        parsed.append({"timestamp": float(timestamp), "text": value.rstrip()})
        previous = float(timestamp)
    return parsed


def display_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def parse_timestamp(value: str) -> float:
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise LoomError(f"Invalid timestamp: {value}")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as error:
        raise LoomError(f"Invalid timestamp: {value}") from error
    if any(not math.isfinite(number) or number < 0 for number in numbers):
        raise LoomError(f"Invalid timestamp: {value}")
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
    elif len(numbers) == 2:
        hours, minutes, seconds = 0.0, numbers[0], numbers[1]
    else:
        hours, minutes, seconds = 0.0, 0.0, numbers[0]
    if minutes >= 60 or seconds >= 60:
        raise LoomError(f"Invalid timestamp: {value}")
    return hours * 3600 + minutes * 60 + seconds


def output_directory(requested: str | None, video_id: str) -> Path:
    if requested is None:
        return Path(tempfile.mkdtemp(prefix=f"loom-{video_id[:8]}-")).resolve()

    output = Path(requested).expanduser().resolve()
    try:
        output.mkdir(parents=True, exist_ok=True)
        if not output.is_dir():
            raise LoomError(f"Output path is not a directory: {output}")
        with tempfile.NamedTemporaryFile(prefix=".loom-write-test-", dir=output):
            pass
    except LoomError:
        raise
    except OSError as error:
        raise LoomError(f"Output directory is not writable: {output}: {error}") from error
    return output


def hls_access(video: dict[str, Any]) -> tuple[str, str]:
    payload = None
    for key, value in video.items():
        if "nullableRawCdnUrl" in key and "M3U8" in key and isinstance(value, dict):
            payload = value
            break
    if payload is None:
        raise LoomError("This Loom does not expose an HLS video stream.")

    signed_url = payload.get("url")
    credentials = payload.get("credentials")
    if not isinstance(signed_url, str) or not isinstance(credentials, dict):
        raise LoomError("The Loom HLS stream is missing access credentials.")

    policy = credentials.get("Policy")
    signature = credentials.get("Signature")
    key_pair = credentials.get("KeyPairId")
    if not all(isinstance(item, str) and item for item in (policy, signature, key_pair)):
        raise LoomError("The Loom HLS credentials are incomplete.")
    if any("\r" in item or "\n" in item for item in (policy, signature, key_pair)):
        raise LoomError("The Loom HLS credentials contain invalid characters.")

    parsed = validate_resolved_remote_url(html.unescape(signed_url), "HLS stream URL")
    unsigned_url = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, "", "")
    )
    cookie = (
        f"CloudFront-Policy={policy}; "
        f"CloudFront-Signature={signature}; "
        f"CloudFront-Key-Pair-Id={key_pair}"
    )
    return unsigned_url, cookie


def atomic_write_text(path: Path, content: str) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)
        temporary = None
    except OSError as error:
        raise LoomError(f"Could not write artifact {path.name}: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}-",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)
        temporary = None
    except OSError as error:
        raise LoomError(f"Could not write artifact {path.name}: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_transcript(path: Path, title: str, phrases: list[dict[str, Any]]) -> None:
    lines = [f"# {title}", ""]
    for phrase in phrases:
        lines.append(f"[{display_timestamp(phrase['timestamp'])}] {phrase['text']}")
        lines.append("")
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n")


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise LoomError(
            "ffmpeg is required to extract frames; install it only with user approval."
        )
    return ffmpeg


def extract_frame(
    ffmpeg: str,
    stream_url: str,
    cookie: str,
    seconds: float,
    destination: Path,
) -> None:
    validate_resolved_remote_url(stream_url, "HLS stream URL")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-headers",
        f"Cookie: {cookie}\r\nUser-Agent: {USER_AGENT}\r\n",
        "-ss",
        display_timestamp(seconds),
        "-protocol_whitelist",
        FFMPEG_PROTOCOLS,
        "-i",
        stream_url,
        "-map",
        "0:v:0",
        "-frames:v",
        "1",
        "-c:v",
        "png",
        "-f",
        "image2pipe",
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=False, timeout=180
        )
        if not result.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
            raise LoomError(f"Frame extraction produced no image at {seconds:g}s.")
        atomic_write_bytes(destination, result.stdout)
    except subprocess.CalledProcessError as error:
        raw_stderr = error.stderr if isinstance(error.stderr, bytes) else b""
        stderr = raw_stderr.decode("utf-8", errors="replace").strip()
        detail = redact_sensitive(stderr or "unknown ffmpeg error", (cookie, stream_url))
        raise LoomError(f"Could not extract frame at {seconds:g}s: {detail}") from error
    except subprocess.TimeoutExpired as error:
        raise LoomError(f"Frame extraction timed out at {seconds:g}s.") from error
    except OSError as error:
        raise LoomError(f"Could not save frame at {seconds:g}s: {error}") from error


def normalized_duration(video: dict[str, Any]) -> float | None:
    properties = video.get("video_properties")
    duration = properties.get("duration") if isinstance(properties, dict) else None
    if (
        not isinstance(duration, (int, float))
        or isinstance(duration, bool)
        or not math.isfinite(duration)
        or duration < 0
    ):
        return None
    return float(duration)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="HTTPS Loom /share/ or /embed/ URL")
    parser.add_argument(
        "--timestamp",
        action="append",
        default=[],
        help="Frame timestamp in seconds, MM:SS, or HH:MM:SS; repeat as needed",
    )
    parser.add_argument(
        "--output-dir",
        help="Writable artifact directory; defaults to a new OS temporary directory",
    )
    args = parser.parse_args()

    video_id = video_id_from_url(args.url)
    timestamps = [(value, parse_timestamp(value)) for value in args.timestamp]
    page = fetch_bytes(args.url, "Loom URL", LOOM_HOSTS).decode(
        "utf-8", errors="replace"
    )
    state = extract_apollo_state(page)
    video = find_video(state, video_id)
    details = find_transcript_details(state, video_id)
    phrases = parse_transcript(details)

    raw_title = video.get("name") if isinstance(video.get("name"), str) else video_id
    title = " ".join(raw_title.split()) or video_id
    duration = normalized_duration(video)
    if duration is not None:
        for original, seconds in timestamps:
            if seconds > duration:
                raise LoomError(
                    f"Timestamp {original} exceeds the {duration:g}s video duration."
                )

    stream_url: str | None = None
    cookie: str | None = None
    ffmpeg: str | None = None
    if timestamps:
        stream_url, cookie = hls_access(video)
        ffmpeg = find_ffmpeg()

    output_dir = output_directory(args.output_dir, video_id)
    transcript_path = output_dir / "transcript.md"
    metadata_path = output_dir / "metadata.json"
    write_transcript(transcript_path, title, phrases)

    frames: list[dict[str, Any]] = []
    if timestamps:
        assert stream_url is not None and cookie is not None and ffmpeg is not None
        for original, seconds in timestamps:
            filename_time = display_timestamp(seconds).replace(":", "-").replace(".", "-")
            frame_path = output_dir / f"frame-{filename_time}.png"
            extract_frame(ffmpeg, stream_url, cookie, seconds, frame_path)
            frames.append(
                {
                    "requested_timestamp": original,
                    "timestamp_seconds": seconds,
                    "path": str(frame_path),
                }
            )

    metadata = {
        "video_id": video_id,
        "title": title,
        "duration_seconds": duration,
        "transcript_language": details.get("language"),
        "phrase_count": len(phrases),
        "last_phrase_seconds": phrases[-1]["timestamp"],
        "source_url": public_source_url(args.url),
    }
    atomic_write_text(metadata_path, json.dumps(metadata, indent=2) + "\n")

    result = {
        **metadata,
        "output_dir": str(output_dir),
        "transcript_path": str(transcript_path),
        "metadata_path": str(metadata_path),
        "frames": frames,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LoomError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        raise SystemExit(1)
