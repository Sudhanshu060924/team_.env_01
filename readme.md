# 🎓 VidyaRoom

> AI-powered live lecture understanding, translation, notes & Q&A.

VidyaRoom transforms a live or recorded lecture into an interactive learning
experience. For the MVP, a recorded MP4 is simulated as a live lecture while
AI processes speech and important visual content in real time.

## ✨ What it does

- 🎥 Live lecture playback
- 🎙️ Real-time speech transcription
- 🌐 Live translation
- 👁️ Important frame & slide detection
- 📝 OCR-based content extraction
- 🧠 Multi-agent lecture understanding
- 📚 Automatic lecture notes
- 💬 Lecture-grounded AI Q&A
- ⚡ Real-time updates through WebSockets

## 🏗️ Architecture

```text
MP4
 ↓
Next.js
 ↓
Audio / Frames
 ↓
FastAPI
 ↓
Whisper / OpenCV / OCR
 ↓
LectureEvent
 ↓
LangGraph
 ↓
Groq
 ↓
Lecture Memory
 ↓
Translation / Topics / Important Events
 ↓
WebSocket
 ↓
Next.js