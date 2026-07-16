"""
119 Copilot — AI-assisted emergency call triage dashboard
Google Cloud Study Jam Hackathon 2026

Flow: upload call audio -> Gemini multimodal analysis -> structured
dispatch card. The AI assists the dispatcher; it never dispatches on
its own (human-in-the-loop by design).

Run:
    pip install streamlit google-genai
    export GEMINI_API_KEY="your-key-from-ai-studio"
    streamlit run app.py
"""

import json
import os
import time

import streamlit as st
from google import genai
from google.genai import types

# ---------------------------------------------------------------- config

MODEL_ID = "gemini-3.5-flash"

SEVERITY_COLOR = {
    5: "#DC2626", 4: "#EA580C", 3: "#D97706", 2: "#2563EB", 1: "#16A34A",
}

SEVERITY_LABEL = {
    "en": {5: "CRITICAL", 4: "URGENT", 3: "SERIOUS", 2: "MODERATE", 1: "MINOR"},
    "ko": {5: "긴급", 4: "위급", 3: "심각", 2: "보통", 1: "경미"},
}

INCIDENT_ICONS = {
    "fire": "🔥", "medical": "🚑", "rescue": "⛑️",
    "traffic": "🚗", "crime": "🚨", "hazmat": "☣️", "other": "📞",
}

# ---------------------------------------------------------- ui translations

UI_TEXT = {
    "en": {
        "sidebar_title": "⚙️ Console settings",
        "api_key_label": "Gemini API key",
        "sidebar_caption": (
            "911 Copilot assists the human dispatcher. It never dispatches units on its own — "
            "every recommendation requires human confirmation."
        ),
        "header_title": "911 Copilot — Dispatch Console",
        "header_subtitle": (
            "Incoming call queue · upload call audio, then analyze. Cards are ordered by severity."
        ),
        "uploader_label": "Incoming calls (audio)",
        "analyze_button": "▶ Analyze incoming calls",
        "api_key_error": "Add your Gemini API key in the sidebar (AI Studio → Get API key).",
        "progress_start": "Triaging calls…",
        "progress_step": "Triaged {i}/{n}",
        "error_prefix": "analysis failed",
        "field_location": "Location",
        "field_people": "People at risk",
        "field_caller_lang": "Caller language",
        "field_acoustic": "Acoustic signals · caller state",
        "no_sounds": "no notable background sounds",
        "field_units": "Recommended units (dispatcher confirms)",
        "field_questions": "Ask the caller next",
        "details_expander": "Details · transcript · audio",
        "key_facts": "Key facts",
        "hazards": "Hazards",
        "transcript_original": "Transcript (original)",
        "transcript_translated": "Transcript ({lang})",
        "empty_queue": "Queue is empty. Upload one or more call recordings above, then press **Analyze incoming calls**.",
        "unknown": "unknown",
    },
    "ko": {
        "sidebar_title": "⚙️ 콘솔 설정",
        "api_key_label": "Gemini API 키",
        "sidebar_caption": (
            "119 코파일럿은 사람 디스패처를 보조합니다. 스스로 출동 지시를 내리지 않으며 "
            "모든 권고사항은 사람의 확인을 거쳐야 합니다."
        ),
        "header_title": "119 코파일럿 — 지령 콘솔",
        "header_subtitle": "수신 신고 대기열 · 통화 음성을 업로드한 뒤 분석하세요. 카드는 심각도순으로 정렬됩니다.",
        "uploader_label": "수신 신고 (음성)",
        "analyze_button": "▶ 신고 분석 시작",
        "api_key_error": "사이드바에 Gemini API 키를 입력하세요 (AI Studio → API 키 발급).",
        "progress_start": "신고 분류 중…",
        "progress_step": "{i}/{n}건 분류 완료",
        "error_prefix": "분석 실패",
        "field_location": "위치",
        "field_people": "위험 인원",
        "field_caller_lang": "발신자 언어",
        "field_acoustic": "음향 신호 · 발신자 상태",
        "no_sounds": "특이 배경음 없음",
        "field_units": "권장 출동 유닛 (디스패처 확인 필요)",
        "field_questions": "다음 질문",
        "details_expander": "상세 정보 · 스크립트 · 음성",
        "key_facts": "주요 사실",
        "hazards": "위험 요소",
        "transcript_original": "스크립트 (원문)",
        "transcript_translated": "스크립트 ({lang})",
        "empty_queue": "대기열이 비어 있습니다. 위에서 통화 녹음 파일을 업로드한 뒤 **신고 분석 시작**을 누르세요.",
        "unknown": "미상",
    },
}

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "language_detected": {"type": "STRING"},
        "transcript_original": {"type": "STRING"},
        "transcript_translated": {
            "type": "STRING",
            "description": "Transcript translated into the dispatcher's language. Empty string if already in that language.",
        },
        "incident_type": {
            "type": "STRING",
            "enum": ["fire", "medical", "rescue", "traffic", "crime", "hazmat", "other"],
        },
        "severity": {"type": "INTEGER", "description": "1 (minor) to 5 (life-threatening, in progress)"},
        "location": {"type": "STRING", "description": "Most specific location mentioned, or 'NOT STATED'"},
        "people_at_risk": {"type": "STRING", "description": "Count and condition of victims/people at risk, or 'unknown'"},
        "hazards": {"type": "ARRAY", "items": {"type": "STRING"}},
        "acoustic_signals": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Sounds actually audible in the background (alarms, breaking glass, traffic, shouting, crying). Empty if none.",
        },
        "caller_state": {
            "type": "STRING",
            "description": "Audible vocal cues only: e.g. 'whispering', 'labored breathing', 'calm', 'shouting'. Not a diagnosis.",
        },
        "key_facts": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "3-5 bullet facts a dispatcher needs"},
        "recommended_units": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "e.g. fire engine, ambulance, police, rescue"},
        "questions_to_ask": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "2-3 questions the human dispatcher should ask next to fill information gaps",
        },
        "one_line_summary": {"type": "STRING"},
    },
    "required": [
        "language_detected", "transcript_original", "incident_type",
        "severity", "location", "one_line_summary", "key_facts",
        "recommended_units", "questions_to_ask",
    ],
}


def build_prompt(dispatcher_lang: str) -> str:
    return f"""You are an AI triage assistant supporting a human 119 emergency dispatcher in Korea.
You will receive audio of an incoming emergency call. Analyze it and return ONLY structured data.

Rules:
- Transcribe exactly what you hear. If audio is unclear, mark unclear parts with [inaudible]. Never invent details.
- The caller may speak ANY language. Detect it. If it is not {dispatcher_lang}, translate the transcript into {dispatcher_lang} in transcript_translated.
- All analysis fields (summary, key_facts, questions_to_ask, hazards) must be written in {dispatcher_lang}.
- severity: 5 = life-threatening and in progress, 4 = urgent risk to life, 3 = serious injury/damage, 2 = needs response but stable, 1 = minor/informational.
- location: extract the MOST specific location mentioned (address, building, landmark, cross-street). If none stated, write exactly NOT STATED.
- questions_to_ask: the 2-3 most valuable questions the human dispatcher should ask next, given what is missing.
- Analyze the ENTIRE auditory scene, not just the words. acoustic_signals: background sounds you can actually hear (alarms, breaking glass, engines, shouting, crying). caller_state: audible vocal cues only (whispering, labored breathing, calm, shouting).
- Report only sounds that are genuinely audible. Never speculate about sounds, emotions, or causes you cannot hear. These are cues for the human dispatcher, not conclusions.
- Be conservative: if a fact was not stated, do not infer it."""


# ---------------------------------------------------------------- gemini


def analyze_call(client: genai.Client, audio_bytes: bytes, mime: str, dispatcher_lang: str) -> dict:
    """One multimodal call, structured JSON out, one retry on failure."""
    contents = [
        types.Part.from_bytes(data=audio_bytes, mime_type=mime),
        build_prompt(dispatcher_lang),
    ]
    cfg = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=RESPONSE_SCHEMA,
        temperature=0.1,
    )
    last_err = None
    for _ in range(2):  # one retry
        try:
            resp = client.models.generate_content(model=MODEL_ID, contents=contents, config=cfg)
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001 - surface anything to the UI
            last_err = e
            time.sleep(1.0)
    raise RuntimeError(f"Gemini analysis failed after retry: {last_err}")


MIME_BY_EXT = {
    "mp3": "audio/mp3", "wav": "audio/wav", "m4a": "audio/mp4",
    "aac": "audio/aac", "ogg": "audio/ogg", "flac": "audio/flac",
}

# ---------------------------------------------------------------- ui


st.set_page_config(page_title="119 Copilot", page_icon="🚨", layout="wide")


st.markdown("""
<style>
  .stApp { background: #F1F5F9; color: #1F2937; }
  h1, h2, h3 { color: #1F2937 !important; }
  section[data-testid="stSidebar"] {
    background: #FFFFFF; border-right: 1px solid #E2E8F0;
  }

  .app-header {
    background: #111827; padding: 26px 32px; border-radius: 12px;
    margin-bottom: 24px; box-shadow: 0 4px 14px rgba(15,23,42,.18);
  }
  .app-header h1 {
    color: #F9FAFB !important; margin: 0; font-size: 1.65rem;
    font-weight: 700; letter-spacing: -.01em;
  }
  .app-header p {
    color: #9CA3AF; margin: 8px 0 0 0; font-size: .9rem;
  }

  .call-card {
    background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;
    padding: 20px 24px 16px 24px; margin-bottom: 18px;
    border-left: 6px solid var(--sev, #2563EB);
    box-shadow: 0 1px 2px rgba(15,23,42,.04), 0 6px 16px rgba(15,23,42,.05);
  }
  .sev-badge {
    display:inline-block; padding: 3px 12px; border-radius: 999px;
    font-family: ui-monospace, monospace; font-weight: 700; font-size: 0.72rem;
    color: #FFFFFF; background: var(--sev, #2563EB); letter-spacing: .06em;
  }
  .field-label {
    font-family: ui-monospace, monospace; font-size: .66rem; letter-spacing: .12em;
    color: #94A3B8; text-transform: uppercase; margin-bottom: 3px; font-weight: 700;
  }
  .field-value { font-size: .95rem; margin-bottom: 12px; color: #1F2937; }
  .mono { font-family: ui-monospace, monospace; }
  .live-dot {
    display:inline-block; width:9px; height:9px; border-radius:50%;
    background:#EF4444; margin-right:8px; animation: pulse 1.4s infinite;
  }
  @keyframes pulse { 0%,100% {opacity:1} 50% {opacity:.25} }
  .queue-hint { color:#64748B; font-size:.85rem; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    ui_lang_choice = st.radio(
        "Dashboard language / 대시보드 언어", ["한국어", "English"], index=0, horizontal=True,
    )
    ui_lang = "ko" if ui_lang_choice == "한국어" else "en"
    T = UI_TEXT[ui_lang]
    dispatcher_lang = "Korean" if ui_lang == "ko" else "English"
    lang_display = "한국어" if ui_lang == "ko" else "English"
    st.markdown("---")
    st.markdown(f"### {T['sidebar_title']}")
    api_key = st.text_input(T["api_key_label"], value=os.environ.get("GEMINI_API_KEY", ""), type="password")
    st.markdown("---")
    st.caption(T["sidebar_caption"])

st.markdown(f"""
<div class="app-header">
  <h1><span class="live-dot"></span>{T['header_title']}</h1>
  <p>{T['header_subtitle']}</p>
</div>
""", unsafe_allow_html=True)

uploads = st.file_uploader(
    T["uploader_label"], type=list(MIME_BY_EXT), accept_multiple_files=True,
    label_visibility="collapsed",
)

if "results" not in st.session_state:
    st.session_state.results = {}  # filename -> analysis dict

if uploads and st.button(T["analyze_button"], type="primary", use_container_width=True):
    if not api_key:
        st.error(T["api_key_error"])
    else:
        client = genai.Client(api_key=api_key)
        prog = st.progress(0.0, text=T["progress_start"])
        for i, up in enumerate(uploads):
            if up.name in st.session_state.results:
                prog.progress((i + 1) / len(uploads))
                continue
            mime = MIME_BY_EXT.get(up.name.rsplit(".", 1)[-1].lower(), "audio/mp3")
            try:
                st.session_state.results[up.name] = analyze_call(client, up.getvalue(), mime, dispatcher_lang)
            except Exception as e:  # noqa: BLE001
                st.session_state.results[up.name] = {"error": str(e)}
            prog.progress((i + 1) / len(uploads), text=T["progress_step"].format(i=i + 1, n=len(uploads)))
        prog.empty()

# render cards, highest severity first
audio_by_name = {u.name: u for u in (uploads or [])}
ordered = sorted(
    st.session_state.results.items(),
    key=lambda kv: -(kv[1].get("severity", 0) if isinstance(kv[1], dict) else 0),
)

for name, r in ordered:
    if "error" in r:
        st.error(f"**{name}** — {T['error_prefix']}: {r['error']}")
        continue

    sev = int(r.get("severity", 1))
    sev_color = SEVERITY_COLOR.get(sev, SEVERITY_COLOR[1])
    sev_label = SEVERITY_LABEL[ui_lang].get(sev, SEVERITY_LABEL[ui_lang][1])
    icon = INCIDENT_ICONS.get(r.get("incident_type", "other"), "📞")

    st.markdown(f"""
    <div class="call-card" style="--sev:{sev_color}">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <div style="font-size:1.15rem; font-weight:700;">{icon} {r.get('one_line_summary','')}</div>
        <div class="sev-badge">SEV {sev} · {sev_label}</div>
      </div>
      <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap: 0 24px;">
        <div><div class="field-label">{T['field_location']}</div>
             <div class="field-value mono">{r.get('location','—')}</div></div>
        <div><div class="field-label">{T['field_people']}</div>
             <div class="field-value">{r.get('people_at_risk', T['unknown'])}</div></div>
        <div><div class="field-label">{T['field_caller_lang']}</div>
             <div class="field-value">{r.get('language_detected','—')}</div></div>
      </div>
      <div class="field-label">{T['field_acoustic']}</div>
      <div class="field-value">🎧 {(' · '.join(r.get('acoustic_signals', [])) or T['no_sounds'])} — <em>{r.get('caller_state', '—')}</em></div>
      <div class="field-label">{T['field_units']}</div>
      <div class="field-value">{' · '.join(r.get('recommended_units', []) or ['—'])}</div>
      <div class="field-label">{T['field_questions']}</div>
      <div class="field-value">{'<br>'.join('• ' + q for q in r.get('questions_to_ask', []))}</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander(f"{T['details_expander']} — {name}"):
        if name in audio_by_name:
            st.audio(audio_by_name[name])
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{T['key_facts']}**")
            for f in r.get("key_facts", []):
                st.markdown(f"- {f}")
            if r.get("hazards"):
                st.markdown(f"**{T['hazards']}**")
                for h in r["hazards"]:
                    st.markdown(f"- ⚠️ {h}")
        with c2:
            st.markdown(f"**{T['transcript_original']}**")
            st.caption(r.get("transcript_original", ""))
            if r.get("transcript_translated"):
                st.markdown(f"**{T['transcript_translated'].format(lang=lang_display)}**")
                st.caption(r["transcript_translated"])

if not st.session_state.results:
    st.info(T["empty_queue"])