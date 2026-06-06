# youtub-longform-automation2

Korean medical common-sense longform YouTube automation workflow.

This repository is the medical common-sense longform workspace. Keep short-form quotes, sayings, and life-information longform content in their separate repositories so schedules, history files, and generated outputs do not overlap.

## Scheduled workflows

- Medical common-sense longform: `.github/workflows/daily-medical-common-sense-longform.yml`, every day at 06:10 KST.

Each workflow writes to its own topic history file:

- `longform_automation/topic-history-medical.json`

Both workflows run `longform_automation/daily_longform_upload_v2.py`; the topic category is selected with `LONGFORM_TOPIC_CATEGORY`.

## Optional HeyGen enhancement

The default renderer remains the original OpenAI/Gemini still-image slideshow with ElevenLabs narration.
HeyGen is opt-in and only replaces selected scenes when the generated clips pass local ffprobe quality checks.
If HeyGen fails, times out, returns a low-resolution/invalid clip, or too few scenes pass, the workflow falls back to the original renderer.

Set the API key only as an environment variable. Do not commit it.

```bash
export HEYGEN_API_KEY="..."
export HEYGEN_ENABLED=true
export HEYGEN_SCENE_INDICES="1,17"
export HEYGEN_MIN_REPLACED_SCENES=1
```

Useful options:

- `HEYGEN_SCENE_INDICES`: comma-separated 1-based scene numbers to try with HeyGen. Defaults to `1,17`.
- `HEYGEN_MIN_REPLACED_SCENES`: minimum accepted HeyGen scenes before the hybrid output is used. Defaults to `1`.
- `HEYGEN_RESOLUTION`: `720p`, `1080p`, or `4k`. Defaults to `1080p`.
- `HEYGEN_POLL_TIMEOUT`: seconds to wait for a HeyGen render. Defaults to `900`.

Recommended rollout:

1. Start with `HEYGEN_SCENE_INDICES="1"` and review the result.
2. Add the closing scene with `HEYGEN_SCENE_INDICES="1,17"` if quality is stable.
3. Only expand to more scenes after confirming lip sync, visual quality, and cost are acceptable.
