#!/usr/bin/env python3
"""Extract a Fathom transcript and optional timestamped frames."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


USER_AGENT = "Mozilla/5.0 (compatible; FathomMediaSkill/1.0)"
DIRECT_FRAME_LIMIT_SECONDS = 300.0
APPROVED_FATHOM_HOSTS = frozenset({"fathom.video"})


class FathomError(RuntimeError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


class AppDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.data_page: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "div" or self.data_page is not None:
            return
        values = dict(attrs)
        if values.get("id") == "app" and values.get("data-page"):
            self.data_page = values["data-page"]


class TranscriptHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[dict[str, Any]] = []
        self.heading_parts: list[str] = []
        self._in_heading = False
        self._paragraph: dict[str, Any] | None = None
        self._in_bold = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "h1":
            self._in_heading = True
        elif tag == "p":
            self._paragraph = {"text": [], "bold": [], "hrefs": []}
        elif self._paragraph is not None and tag == "b":
            self._in_bold = True
        elif self._paragraph is not None and tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._paragraph["hrefs"].append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self._in_heading = False
        elif tag == "b":
            self._in_bold = False
        elif tag == "p" and self._paragraph is not None:
            text = " ".join("".join(self._paragraph["text"]).split())
            bold = " ".join("".join(self._paragraph["bold"]).split())
            self.paragraphs.append(
                {"text": text, "bold": bold, "hrefs": self._paragraph["hrefs"]}
            )
            self._paragraph = None
            self._in_bold = False

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self.heading_parts.append(data)
        if self._paragraph is not None:
            self._paragraph["text"].append(data)
            if self._in_bold:
                self._paragraph["bold"].append(data)

    @property
    def heading(self) -> str | None:
        value = " ".join("".join(self.heading_parts).split())
        return value or None


def validate_fathom_url(value: Any, field: str, status: str = "page_changed") -> str:
    if not isinstance(value, str) or not value:
        raise FathomError(status, f"Fathom did not expose {field}.")
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise FathomError(status, f"Fathom exposed an invalid {field}.") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname not in APPROVED_FATHOM_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise FathomError(status, f"Fathom exposed an unapproved {field} origin.")
    return value


class FathomRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, resource: str) -> None:
        super().__init__()
        self.resource = resource

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        redirect_url = urllib.parse.urljoin(req.full_url, newurl)
        validate_fathom_url(redirect_url, f"redirect for {self.resource}")
        return super().redirect_request(req, fp, code, msg, headers, redirect_url)


def fetch_bytes(url: str, resource: str) -> bytes:
    validate_fathom_url(url, f"URL for {resource}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(FathomRedirectHandler(resource))
    try:
        with opener.open(request, timeout=60) as response:
            validate_fathom_url(response.geturl(), f"final URL for {resource}")
            return response.read()
    except FathomError:
        raise
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise FathomError("access_denied", f"Access denied for {resource}.") from error
        if error.code == 404:
            raise FathomError("not_found", f"Fathom {resource} was not found.") from error
        raise FathomError(
            "fetch_failed", f"Fathom returned HTTP {error.code} for {resource}."
        ) from error
    except Exception as error:
        raise FathomError(
            "fetch_failed", f"Could not fetch Fathom {resource}: {error}"
        ) from error


def parse_share_url(url: str) -> tuple[str, str]:
    validate_fathom_url(url, "share URL", "invalid_url")
    parsed = urllib.parse.urlsplit(url)
    match = re.fullmatch(r"/share/([A-Za-z0-9_-]+)/?", parsed.path)
    if not match:
        raise FathomError("invalid_url", "Expected a fathom.video/share/<token> URL.")
    token = match.group(1)
    return f"https://fathom.video/share/{token}", token


def parse_page(page: str) -> dict[str, Any]:
    parser = AppDataParser()
    parser.feed(page)
    if parser.data_page is None:
        raise FathomError("page_changed", "Fathom page metadata was not found.")
    try:
        data = json.loads(html.unescape(parser.data_page))
    except json.JSONDecodeError as error:
        raise FathomError("page_changed", "Fathom page metadata was invalid JSON.") from error
    component = data.get("component") if isinstance(data, dict) else None
    if component != "page-call-detail":
        if component in {"page-share-locked", "page-call-request-access"}:
            raise FathomError("access_denied", "This Fathom recording requires access.")
        raise FathomError("media_unavailable", f"Unsupported Fathom page: {component!r}.")
    return data


def same_origin_url(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise FathomError("media_unavailable", f"Fathom did not expose {field}.")
    return validate_fathom_url(value, field)


def timestamp_from_href(href: str) -> float | None:
    values = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query).get("timestamp")
    if not values:
        return None
    try:
        timestamp = float(values[0])
    except ValueError:
        return None
    return timestamp if math.isfinite(timestamp) and timestamp >= 0 else None


def parse_transcript(payload: bytes) -> tuple[str | None, list[dict[str, Any]]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise FathomError(
            "transcript_unavailable", "Transcript response was invalid JSON."
        ) from error
    transcript_html = data.get("html") if isinstance(data, dict) else None
    if not isinstance(transcript_html, str) or not transcript_html:
        raise FathomError("transcript_unavailable", "Transcript HTML was unavailable.")

    parser = TranscriptHTMLParser()
    parser.feed(transcript_html)
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for paragraph in parser.paragraphs:
        timestamp = next(
            (
                parsed
                for href in paragraph["hrefs"]
                if (parsed := timestamp_from_href(href)) is not None
            ),
            None,
        )
        if timestamp is not None and not paragraph["text"].lstrip().startswith("@"):
            # Ignore Fathom's timestamped action-item and screen-sharing cards.
            continue
        if timestamp is not None:
            if current is not None:
                current["text"] = "\n\n".join(current.pop("paragraphs"))
                entries.append(current)
            current = {
                "timestamp": timestamp,
                "speaker": paragraph["bold"] or "Unknown speaker",
                "paragraphs": [],
            }
        elif current is not None and paragraph["text"]:
            current["paragraphs"].append(paragraph["text"])

    if current is not None:
        current["text"] = "\n\n".join(current.pop("paragraphs"))
        entries.append(current)
    if not entries:
        raise FathomError("transcript_unavailable", "Transcript contained no entries.")
    if any(
        entries[index]["timestamp"] < entries[index - 1]["timestamp"]
        for index in range(1, len(entries))
    ):
        raise FathomError(
            "transcript_unavailable", "Transcript timestamps were out of order."
        )
    return parser.heading, entries


def parse_timestamp(value: str) -> float:
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise FathomError("invalid_timestamp", f"Invalid timestamp: {value}")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as error:
        raise FathomError("invalid_timestamp", f"Invalid timestamp: {value}") from error
    if any(not math.isfinite(number) or number < 0 for number in numbers):
        raise FathomError("invalid_timestamp", f"Invalid timestamp: {value}")
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
    elif len(numbers) == 2:
        hours, minutes, seconds = 0.0, numbers[0], numbers[1]
    else:
        hours, minutes, seconds = 0.0, 0.0, numbers[0]
    if minutes >= 60 or seconds >= 60:
        raise FathomError("invalid_timestamp", f"Invalid timestamp: {value}")
    return hours * 3600 + minutes * 60 + seconds


def display_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def prepare_output_dir(requested: str | None, token: str) -> Path:
    if requested is None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:8]
        return Path(tempfile.mkdtemp(prefix=f"fathom-{token_hash}-")).resolve()

    requested_output = Path(requested).expanduser()
    if requested_output.is_symlink():
        raise FathomError("invalid_output", "Output directory must not be a symlink.")
    output = requested_output.resolve()
    try:
        output.mkdir(parents=True, exist_ok=True)
        if not output.is_dir():
            raise NotADirectoryError(output)
        with tempfile.NamedTemporaryFile(prefix=".fathom-write-", dir=output):
            pass
    except OSError as error:
        raise FathomError(
            "invalid_output", f"Output directory is not writable: {output}"
        ) from error
    return output


def ensure_artifact_directory(path: Path, output_dir: Path) -> None:
    try:
        path.relative_to(output_dir)
    except ValueError as error:
        raise FathomError("invalid_output", "Artifact directory escapes output directory.") from error
    if path.is_symlink():
        raise FathomError("invalid_output", f"Artifact directory must not be a symlink: {path}")
    try:
        path.mkdir(exist_ok=True)
        if not path.is_dir() or path.resolve() != path:
            raise NotADirectoryError(path)
    except OSError as error:
        raise FathomError("invalid_output", f"Invalid artifact directory: {path}") from error


def ensure_artifact_target(path: Path, output_dir: Path) -> None:
    try:
        path.relative_to(output_dir)
        parent = path.parent.resolve(strict=True)
        parent.relative_to(output_dir)
    except (OSError, ValueError) as error:
        raise FathomError("invalid_output", f"Artifact target escapes output directory: {path}") from error
    if path.is_symlink():
        raise FathomError("invalid_output", f"Artifact target must not be a symlink: {path}")
    if path.exists() and not path.is_file():
        raise FathomError("invalid_output", f"Artifact target is not a regular file: {path}")


def atomic_write_text(path: Path, content: str, output_dir: Path) -> None:
    ensure_artifact_target(path, output_dir)
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        ensure_artifact_target(path, output_dir)
        os.replace(temporary_path, path)
        temporary_path = None
    except OSError as error:
        raise FathomError("invalid_output", f"Could not write artifact: {path}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def temporary_artifact(directory: Path, suffix: str, output_dir: Path) -> Path:
    ensure_artifact_directory(directory, output_dir)
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".fathom-processing-", suffix=suffix, dir=directory, delete=False
        ) as temporary:
            return Path(temporary.name)
    except OSError as error:
        raise FathomError(
            "invalid_output", f"Could not create processing artifact in {directory}."
        ) from error


def publish_artifact(source: Path, destination: Path, output_dir: Path) -> None:
    ensure_artifact_target(destination, output_dir)
    try:
        os.replace(source, destination)
    except OSError as error:
        raise FathomError(
            "invalid_output", f"Could not publish artifact: {destination}"
        ) from error


def write_transcript(
    path: Path, title: str, entries: list[dict[str, Any]], output_dir: Path
) -> None:
    lines = [f"# {title}", ""]
    for entry in entries:
        lines.extend(
            [
                f"[{display_timestamp(entry['timestamp'])}] **{entry['speaker']}**",
                "",
                entry["text"],
                "",
            ]
        )
    atomic_write_text(path, "\n".join(lines).rstrip() + "\n", output_dir)


def require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FathomError(
            "ffmpeg_missing", "ffmpeg is required for video download and frame extraction."
        )
    return ffmpeg


def run_ffmpeg(command: list[str], action: str, secret: str) -> str:
    try:
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=900
        )
        return result.stderr
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "unknown ffmpeg error").strip()
        detail = detail.replace(secret, "<share-token>")
        detail = re.sub(r"https?://\S+", "<url>", detail)
        raise FathomError(
            "ffmpeg_failed", f"Could not {action}: {detail[-1000:]}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise FathomError(
            "ffmpeg_failed", f"Timed out while attempting to {action}."
        ) from error


def png_dimensions(path: Path) -> tuple[int, int]:
    try:
        with path.open("rb") as image:
            header = image.read(24)
    except OSError as error:
        raise FathomError("ffmpeg_failed", "Frame output was not created.") from error
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise FathomError("ffmpeg_failed", "Frame output was not a valid PNG.")
    return struct.unpack(">II", header[16:24])


def frame_path(frames_dir: Path, seconds: float) -> Path:
    name = display_timestamp(seconds).replace(":", "-").replace(".", "-")
    return frames_dir / f"frame-{name}.png"


def extract_direct_frame(
    ffmpeg: str, hls_url: str, token: str, seconds: float, destination: Path
) -> float:
    stderr = run_ffmpeg(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-y",
            "-i",
            hls_url,
            "-an",
            "-vf",
            f"select=gte(t\\,{seconds:.6f}),showinfo",
            "-frames:v",
            "1",
            "-fps_mode",
            "vfr",
            "-c:v",
            "png",
            "-update",
            "1",
            str(destination),
        ],
        f"extract frame at {seconds:g}s",
        token,
    )
    matches = re.findall(r"pts_time:([0-9.]+)", stderr)
    return float(matches[-1]) if matches else seconds


def remux_video(ffmpeg: str, hls_url: str, token: str, destination: Path) -> None:
    run_ffmpeg(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            hls_url,
            "-map",
            "0",
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(destination),
        ],
        "cache the Fathom playback stream",
        token,
    )


def extract_local_frame(
    ffmpeg: str, video_path: Path, token: str, seconds: float, destination: Path
) -> None:
    run_ffmpeg(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            display_timestamp(seconds),
            "-i",
            str(video_path),
            "-map",
            "0:v:0",
            "-frames:v",
            "1",
            "-c:v",
            "png",
            "-update",
            "1",
            str(destination),
        ],
        f"extract frame at {seconds:g}s",
        token,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Fathom /share/ URL")
    parser.add_argument(
        "--timestamp",
        action="append",
        default=[],
        help="Frame timestamp in seconds, MM:SS, or HH:MM:SS; repeat as needed",
    )
    parser.add_argument(
        "--output-dir",
        help="Writable artifact directory (default: a new system temporary directory)",
    )
    parser.add_argument(
        "--download-video",
        action="store_true",
        help="Retain recording.mp4 when the Fathom owner enabled downloads",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    share_url, token = parse_share_url(args.url)
    timestamps = [(value, parse_timestamp(value)) for value in args.timestamp]
    ffmpeg = require_ffmpeg() if timestamps or args.download_video else None

    page = fetch_bytes(share_url, "share page").decode("utf-8", errors="replace")
    page_data = parse_page(page)
    props = page_data.get("props")
    if not isinstance(props, dict) or not isinstance(props.get("call"), dict):
        raise FathomError("page_changed", "Fathom call metadata was unavailable.")
    call = props["call"]

    title = call.get("title") if isinstance(call.get("title"), str) else "Fathom recording"
    duration = props.get("duration")
    if (
        not isinstance(duration, (int, float))
        or isinstance(duration, bool)
        or not math.isfinite(float(duration))
        or duration < 0
    ):
        duration = None
    can_download = props.get("canDownload") is True
    if duration is not None:
        for original, seconds in timestamps:
            if seconds > float(duration):
                raise FathomError(
                    "invalid_timestamp",
                    f"Timestamp {original} exceeds the {float(duration):g}s duration.",
                )
    if args.download_video and not can_download:
        raise FathomError(
            "download_not_permitted",
            "The recording owner disabled downloads; use timestamped frame extraction instead.",
        )

    hls_url = None
    if timestamps or args.download_video:
        hls_url = same_origin_url(call.get("video_url"), "video playback URL")
    transcript_url = same_origin_url(props.get("copyTranscriptUrl"), "transcript URL")
    transcript_title, entries = parse_transcript(
        fetch_bytes(transcript_url, "transcript")
    )
    transcript_title = transcript_title or title

    output_dir = prepare_output_dir(args.output_dir, token)
    frames_dir = output_dir / "frames"
    if frames_dir.is_symlink():
        raise FathomError(
            "invalid_output", f"Artifact directory must not be a symlink: {frames_dir}"
        )
    transcript_path = output_dir / "transcript.md"
    metadata_path = output_dir / "metadata.json"
    ensure_artifact_target(transcript_path, output_dir)
    ensure_artifact_target(metadata_path, output_dir)
    retained_video_path = output_dir / "recording.mp4"
    if args.download_video:
        ensure_artifact_target(retained_video_path, output_dir)
    ensure_artifact_directory(frames_dir, output_dir)
    for _, seconds in timestamps:
        ensure_artifact_target(frame_path(frames_dir, seconds), output_dir)

    write_transcript(transcript_path, transcript_title, entries, output_dir)

    frames: list[dict[str, Any]] = []
    video_path: Path | None = None
    if timestamps or args.download_video:
        assert ffmpeg is not None and hls_url is not None
        direct = (
            len(timestamps) == 1
            and timestamps[0][1] <= DIRECT_FRAME_LIMIT_SECONDS
            and not args.download_video
        )
        if direct:
            original, seconds = timestamps[0]
            destination = frame_path(frames_dir, seconds)
            temporary_frame = temporary_artifact(frames_dir, ".png", output_dir)
            try:
                actual = extract_direct_frame(
                    ffmpeg, hls_url, token, seconds, temporary_frame
                )
                width, height = png_dimensions(temporary_frame)
                publish_artifact(temporary_frame, destination, output_dir)
            finally:
                temporary_frame.unlink(missing_ok=True)
            frames.append(
                {
                    "requested_timestamp": original,
                    "requested_seconds": seconds,
                    "actual_seconds": actual,
                    "path": str(destination),
                    "width": width,
                    "height": height,
                }
            )
        else:
            processing_video = temporary_artifact(output_dir, ".mp4", output_dir)
            try:
                remux_video(ffmpeg, hls_url, token, processing_video)
                for original, seconds in timestamps:
                    destination = frame_path(frames_dir, seconds)
                    temporary_frame = temporary_artifact(frames_dir, ".png", output_dir)
                    try:
                        extract_local_frame(
                            ffmpeg, processing_video, token, seconds, temporary_frame
                        )
                        width, height = png_dimensions(temporary_frame)
                        publish_artifact(temporary_frame, destination, output_dir)
                    finally:
                        temporary_frame.unlink(missing_ok=True)
                    frames.append(
                        {
                            "requested_timestamp": original,
                            "requested_seconds": seconds,
                            "actual_seconds": seconds,
                            "path": str(destination),
                            "width": width,
                            "height": height,
                        }
                    )
                if args.download_video:
                    publish_artifact(processing_video, retained_video_path, output_dir)
                    video_path = retained_video_path
            finally:
                processing_video.unlink(missing_ok=True)

    token_hash = hashlib.sha256(token.encode()).hexdigest()[:12]
    metadata = {
        "call_id": call.get("id"),
        "share_token_hash": token_hash,
        "title": title,
        "transcript_title": transcript_title,
        "duration_seconds": duration,
        "started_at": call.get("started_at"),
        "state": call.get("state"),
        "can_download": can_download,
        "transcript_entry_count": len(entries),
        "last_transcript_seconds": entries[-1]["timestamp"],
    }
    atomic_write_text(
        metadata_path, json.dumps(metadata, indent=2) + "\n", output_dir
    )
    result = {
        "status": "ok",
        **metadata,
        "output_dir": str(output_dir),
        "transcript": {
            "path": str(transcript_path),
            "entry_count": len(entries),
            "final_timestamp_seconds": entries[-1]["timestamp"],
        },
        "metadata_path": str(metadata_path),
        "video_path": str(video_path) if video_path is not None else None,
        "frames": frames,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FathomError as error:
        print(json.dumps({"status": error.status, "error": str(error)}), file=sys.stderr)
        raise SystemExit(1)
