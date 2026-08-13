"""
Diagnostic script — runs every pipeline step and prints exactly what fails.

Usage (from the backend/ directory):
    python scripts/diagnose_pipeline.py <lecture_id>

If no lecture_id is given it uses the most-recently created lecture with a video.
"""
import asyncio
import selectors
import sys
import os
import io
import logging

# Force SelectorEventLoop on Windows so psycopg3 async works
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
)

# ── make app importable ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def main() -> None:
    from app.config import get_settings
    settings = get_settings()

    # ── 0. Config check ────────────────────────────────────────────────────────
    print("\n══ CONFIG ════════════════════════════════════════════════")
    print(f"  GROQ_API_KEY      : {'SET (' + settings.GROQ_API_KEY[:8] + '...)' if settings.GROQ_API_KEY else 'MISSING ❌'}")
    print(f"  GEMINI_API_KEY    : {'SET (' + settings.GEMINI_API_KEY[:8] + '...)' if settings.GEMINI_API_KEY else 'MISSING ❌'}")
    print(f"  CLOUD_NAME        : {settings.CLOUD_NAME or 'MISSING ❌'}")
    print(f"  DATABASE_URL      : {'SET' if settings.DATABASE_URL else 'MISSING ❌'}")
    print(f"  WHISPER_MODEL     : {settings.WHISPER_MODEL}")
    print(f"  GEMINI_MODEL      : {settings.GEMINI_TRANSLATION_MODEL}")

    if not settings.GROQ_API_KEY:
        print("\n❌ GROQ_API_KEY is not set. Whisper and all Groq agents will fail.")
        print("   Add GROQ_API_KEY=gsk_... to backend/.env and restart.\n")
        return

    # ── 1. Find a lecture with a video ────────────────────────────────────────
    lecture_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    video_url: str = ""

    print("\n══ DATABASE ══════════════════════════════════════════════")
    try:
        from app.database.database import get_db
        from app.services.lecture_service import get_lecture, list_lectures

        async for db in get_db():
            if lecture_id_arg:
                lec = await get_lecture(db, lecture_id_arg)
                if not lec:
                    print(f"  ❌ Lecture {lecture_id_arg} not found")
                    return
            else:
                lectures = await list_lectures(db)
                lec = next((l for l in lectures if l.video_url), None)
                if not lec:
                    print("  ❌ No lecture with a video found in the database.")
                    return

        print(f"  Lecture  : {lec.lecture_id}")
        print(f"  Title    : {lec.title}")
        print(f"  Status   : {lec.status}")
        print(f"  video_url: {lec.video_url[:80]}..." if lec.video_url and len(lec.video_url) > 80 else f"  video_url: {lec.video_url}")
        video_url = lec.video_url or ""
    except Exception as exc:
        print(f"  ❌ DB error: {exc}")
        return

    if not video_url:
        print("  ❌ Lecture has no video_url — upload a video first.")
        return

    # ── 2. Download video ─────────────────────────────────────────────────────
    print("\n══ STEP 1: DOWNLOAD ══════════════════════════════════════")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
            video_bytes = resp.content
        print(f"  ✅ Downloaded {len(video_bytes):,} bytes  content-type={resp.headers.get('content-type')}")
    except Exception as exc:
        print(f"  ❌ Download failed: {exc}")
        return

    # ── 3. FFmpeg preprocessing ───────────────────────────────────────────────
    print("\n══ STEP 2: FFMPEG PREPROCESSING ══════════════════════════")
    try:
        from app.services.audio_preprocessor import preprocessor, check_ffmpeg
        ffmpeg_path = check_ffmpeg()
        print(f"  FFmpeg   : {ffmpeg_path}")

        wav_bytes = await preprocessor.clean_audio(video_bytes, input_format="mp4")
        print(f"  ✅ WAV output: {len(wav_bytes):,} bytes")

        # Basic WAV validation
        if wav_bytes[:4] == b"RIFF" and wav_bytes[8:12] == b"WAVE":
            print("  ✅ Valid WAV header (RIFF...WAVE)")
        else:
            print(f"  ⚠️  Unexpected WAV header: {wav_bytes[:12]!r}")
    except Exception as exc:
        print(f"  ❌ FFmpeg failed: {exc}")
        # Try without input_format override
        print("  Retrying without input_format...")
        try:
            # Patch: call with no format override
            import subprocess, shutil
            ffmpeg_bin = shutil.which("ffmpeg")
            cmd = [
                ffmpeg_bin, "-y", "-i", "pipe:0",
                "-af", "highpass=f=100,lowpass=f=8000,afftdn=nr=12:nf=-40,loudnorm",
                "-ar", "16000", "-ac", "1", "-f", "wav", "-acodec", "pcm_s16le", "pipe:1",
            ]
            result = subprocess.run(cmd, input=video_bytes, capture_output=True, timeout=60)
            if result.returncode == 0 and result.stdout:
                wav_bytes = result.stdout
                print(f"  ✅ Retry OK — WAV output: {len(wav_bytes):,} bytes")
            else:
                print(f"  ❌ Retry also failed (rc={result.returncode})")
                print(f"  FFmpeg stderr:\n{result.stderr.decode(errors='replace')[-2000:]}")
                return
        except Exception as exc2:
            print(f"  ❌ Retry exception: {exc2}")
            return

    # ── 4. Groq Whisper ───────────────────────────────────────────────────────
    print("\n══ STEP 3: GROQ WHISPER ══════════════════════════════════")
    try:
        from app.integrations.groq_service import get_groq_client
        from app.services.speech_service import WHISPER_TURBO

        client = get_groq_client()
        file_tuple = ("audio.wav", io.BytesIO(wav_bytes))
        print(f"  Sending {len(wav_bytes):,} bytes WAV to Groq Whisper ({WHISPER_TURBO})…")

        transcription = await client.audio.transcriptions.create(
            file=file_tuple,
            model=WHISPER_TURBO,
            response_format="verbose_json",
        )
        text = (transcription.text or "").strip()
        segments = getattr(transcription, "segments", None) or []
        print(f"  ✅ Transcript: {len(text)} chars, {len(segments)} segments")
        print(f"  Language: {getattr(transcription, 'language', 'unknown')}")
        if text:
            print(f"  First 200 chars: {text[:200]!r}")
        else:
            print("  ⚠️  Empty transcript — Whisper found no speech")
            return
    except Exception as exc:
        print(f"  ❌ Whisper failed: {exc}")
        return

    # ── 5. Translation agent ─────────────────────────────────────────────────
    print("\n══ STEP 4: TRANSLATION AGENT (Gemini) ════════════════════")
    if not settings.GEMINI_API_KEY:
        print("  ⚠️  GEMINI_API_KEY not set — skipping translation")
    else:
        try:
            from app.services.lecture_session import session_store
            from app.graph.nodes.translation import translate

            state = session_store.get_or_create("__diag__")
            state = state.model_copy(update={
                "last_transcript": text[:300],
                "target_language": "english",
            })
            result = await translate(state)
            if result:
                print(f"  ✅ Translation: {result.get('language')} — {len(result.get('translated',''))} chars")
                print(f"  First 200: {result['translated'][:200]!r}")
            else:
                print("  ⚠️  Translation returned empty (check GEMINI_API_KEY / model name)")
        except Exception as exc:
            print(f"  ❌ Translation failed: {exc}")

    # ── 6. Topic agent ────────────────────────────────────────────────────────
    print("\n══ STEP 5: TOPIC DETECTION (Groq) ════════════════════════")
    try:
        from app.services.lecture_session import session_store
        from app.graph.nodes.supervisor import detect_topic

        state = session_store.get_or_create("__diag2__")
        state = state.model_copy(update={"last_transcript": text[:300]})
        result = await detect_topic(state)
        if result:
            print(f"  ✅ Topic: {result.get('topic')!r}  Subtopic: {result.get('subtopic')!r}")
        else:
            print("  ⚠️  Topic detection returned empty")
    except Exception as exc:
        print(f"  ❌ Topic detection failed: {exc}")

    # ── 7. Important events ───────────────────────────────────────────────────
    print("\n══ STEP 6: IMPORTANT EVENTS (Groq) ═══════════════════════")
    try:
        from app.graph.nodes.router import detect_important_events
        events_found = await detect_important_events(text[:500], 0.0, "__diag__")
        print(f"  ✅ Found {len(events_found)} important events")
        for e in events_found[:3]:
            print(f"     • {e['content'][:80]!r}")
    except Exception as exc:
        print(f"  ❌ Important events failed: {exc}")

    print("\n══ ALL STEPS COMPLETE ════════════════════════════════════\n")


asyncio.run(main())
