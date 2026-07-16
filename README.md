# 🚨 119 Copilot — AI 기반 긴급 통화 트리아지

**Google Cloud Study Jam Hackathon 2026 · Track: Google AI for Social Good**

119 Copilot은 걸려오는 긴급 통화를 듣고 몇 초 만에 인간 상황실 요원에게 구조화되고 우선순위가 지정된 출동 카드(사건 유형, 심각도, 위치, 위험에 처한 사람, 권장 출동 단위, 그리고 가장 중요한 **요원이 다음으로 물어봐야 할 질문**)를 제공합니다. 발신자가 사용하는 모든 언어로 작동하며 상황실 요원의 언어로 모든 정보를 제공합니다.

텍스트 변환본(transcript)이 아닌 원본 오디오를 분석하기 때문에 **청각적 현장 전체**를 듣습니다. 발신자가 언급하지 않은 화재 경보기 소리, 배경에서 유리가 깨지는 소리, 속삭이거나 숨을 헐떡이는 발신자의 소리 등을 감지합니다. 이러한 정보는 요원을 위한 플래그가 지정된 단서로 표시되며, 절대 자동화된 결론으로 제시되지 않습니다.

> 🧑‍✈️ **설계상 Human-in-the-loop (인간 개입).** 119 Copilot은 스스로 출동 명령을 내리지 않습니다. 상황실 요원의 판단을 가속화할 뿐, 대체하지 않습니다.

## 도입 배경

- 요원은 극심한 시간 압박 속에서 패닉에 빠지고 시끄럽고 파편화된 말에서 위치, 심각도, 상황을 추출해야 합니다.
- 한국의 119 시스템은 이미 음성만으로 신고하는 것이 일부 그룹에게는 어렵다는 것을 인식하고 있습니다. 외국인, 노인, 의사소통이 어려운 사람들을 위해 다매체 신고 서비스(문자/앱/영상)가 존재합니다. 119 Copilot은 음성 채널 자체의 격차를 해소합니다. 베트남어만 사용하는 발신자도 한국어 원어민만큼 빠르게 분류됩니다.

## 작동 방식

```
통화 오디오 ──▶ Gemini (기본 멀티모달 오디오 이해)
                 │  스키마가 적용된 구조화된 출력
                 ▼
        출동 카드: 심각도 · 위치 · 출동 단위 · 질문할 내용
                 │
                 ▼
        인간 상황실 요원 확인 및 출동
```

오디오 파일당 하나의 Gemini 호출. 별도의 STT(Speech-to-Text) 단계가 없습니다. Gemini의 기본 오디오 이해 기능은 API 수준에서 적용되는 JSON 스키마를 사용하여 단일 멀티모달 요청에서 전사, 번역 및 분석을 처리합니다.

## ✨ 핵심 Gemini 기능 (Key Gemini Features)

이 프로젝트는 Gemini API의 강력한 기능들을 최대한 활용하여 구축되었습니다:

1. **네이티브 멀티모달 오디오 이해 (Native Multimodal Audio Understanding):** 별도의 음성 인식(STT) 모델을 거치지 않고, 원시 오디오(Raw Audio) 파일을 모델에 직접 입력하여 정보의 손실 없이 음성을 이해합니다.
2. **청각적 현장 분석 (Acoustic Scene Analysis):** 텍스트 전사로는 파악할 수 없는 **배경 소음**(화재 경보기, 유리 깨지는 소리, 사이렌 등)을 모델이 직접 듣고 식별하여 요원에게 중요한 단서를 제공합니다.
3. **음성 상태 분석 (Vocal Cue Analysis):** 발신자의 **목소리 상태**(속삭임, 가쁜 숨몰아쉬움, 당황함 등)를 감지하여 현장의 위급성을 파악하는 데 도움을 줍니다.
4. **실시간 다국어 번역 (Real-time Translation):** 발신자가 어떤 언어(영어, 베트남어, 등)로 말하든, 모델이 이를 즉시 감지하고 상황실 요원의 모국어(한국어)로 **전사 및 번역**을 동시에 수행합니다.
5. **엄격한 구조화된 출력 (Schema-Enforced Structured Output):** 요원이 즉각적으로 활용할 수 있도록, 긴급도, 위치, 핵심 사실 등을 API 단에서 강제되는 **JSON 스키마** 형태로 완벽하게 구조화하여 반환합니다.

## 사용 기술

- **Gemini API** (Google AI Studio) — 멀티모달 오디오 입력, 구조화된 JSON 출력 (`gemini-2.5-flash` 모델 사용)
- **Streamlit** — 상황실 콘솔 UI
- 해커톤을 위해 프로비저닝된 Google Cloud 프로젝트

## 실행 방법

```bash
pip install streamlit google-genai
export GEMINI_API_KEY="your-key"   # AI Studio → Get API key
streamlit run app.py
```

하나 이상의 통화 녹음 파일(`mp3/wav/m4a/…`)을 업로드하고 **Analyze incoming calls**(수신 통화 분석)를 누릅니다. 카드는 심각도에 따라 정렬되어 렌더링됩니다.

## 데모 및 샘플 통화

📹 데모 비디오: [LINK — 제출 전 추가]

데모에서는 주방 화재(영어), 교통사고(영어), 한국어로 신고된 가스 누출 등 세 가지 통화를 처리합니다. 파이프라인은 동일하고, 코드 변경은 없으며, 처음부터 끝까지 상황실 요원의 언어(한국어)로 출력됩니다.

**테스트용 샘플 통화 오디오 파일:**
- [비응급 911 통화 (Non-emergency 911)](https://web.archive.org/web/20150417114237/http://mp3.911dispatch.com.s3.amazonaws.com/non_emerg_911s.mp3)
- [다중 정보 분리 (Pick Apart)](https://web.archive.org/web/20150417114254/http://mp3.911dispatch.com.s3.amazonaws.com/pick_apart.mp3)
- [일산화탄소 경보기 (Flat Rock Carbon Monoxide)](https://web.archive.org/web/20150417094723/http://mp3.911dispatch.com.s3.amazonaws.com/flatrock_carbonmonoxide_911mp3.mp3)
- [집에 혼자 있는 아이 (Deltona Home Alone)](https://web.archive.org/web/20150417094828/http://mp3.911dispatch.com.s3.amazonaws.com/deltona_homealone_911.mp3)
- [눈보라 신고 (Green Lake County Snowstorm)](https://web.archive.org/web/20150417101704/http://mp3.911dispatch.com.s3.amazonaws.com/greenlakecounty_snowstorm_911.mp3)

## 안전 및 범위

- 2시간의 해커톤에서 제작된 프로토타입이며, 실제 프로덕션 응급 시스템이 아닙니다.
- 모델은 보수적으로 작동하도록 프롬프트되었습니다. 언급되지 않은 사실은 절대 추론하지 않으며, 불분명한 오디오는 `[inaudible]`(알 수 없음)로 표시됩니다.
- 데모용 샘플 통화는 대본/음성 연기로 제작되었습니다. 공개 데이터셋의 실제 911 녹음은 전사 견고성을 스트레스 테스트하기 위해 오프라인에서만 사용되었습니다.
