# fathom-video

```bash
npx skills add izakfilmalter/skills --skill fathom-video
```

[`fathom-video`](../../skills/media/fathom-video/SKILL.md) extracts speaker-labelled, timestamped transcripts and exact PNG frames from accessible Fathom share URLs. It follows a transcript-first workflow so content requests can resolve to precise timestamps before decoding video.

The bundled Python script has no third-party Python dependencies. Transcript extraction requires Python 3.10+ and network access; frame extraction additionally requires `ffmpeg`. Artifacts default to a new operating-system temporary directory, while `--output-dir` accepts any writable location visible to the current agent harness.

The skill follows only access exposed by the supplied share page. It does not bypass private or locked recordings.
