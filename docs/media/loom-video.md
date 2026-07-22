# loom-video

```bash
npx skills add izakfilmalter/skills --skill loom-video
```

[`loom-video`](../../skills/media/loom-video/SKILL.md) extracts timestamped transcripts and exact PNG frames from Loom share or embed URLs accessible to an anonymous session. It uses the transcript to resolve content requests to precise frame timestamps.

The bundled Python script has no third-party Python dependencies. Transcript extraction requires Python 3.10+ and network access; frame extraction additionally requires `ffmpeg`. Artifacts default to a new operating-system temporary directory, while `--output-dir` accepts any writable location visible to the current agent harness.

The extractor validates HTTPS URLs, rejects embedded credentials and local-network targets, and redacts signed media data from errors. It does not accept cookies or bypass password and authentication requirements.
