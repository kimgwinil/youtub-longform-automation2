import hashlib
import json
import os

import daily_longform_upload as base


_generate_gemini = base.generate_gemini
_generate_openai = base.generate_openai

_CATEGORY_INSTRUCTIONS = {
    "life": (
        "Choose a practical Korean everyday-life information topic such as household management, "
        "consumer decisions, education, work habits, public services, digital life, money habits, "
        "relationships, safety, or sustainable living. Do not choose medical diagnosis or treatment."
    ),
    "medical": (
        "Choose a Korean medical common-sense education topic for the general public. Keep it preventive, "
        "practical, and non-diagnostic. Do not provide personalized diagnosis, treatment plans, drug dosages, "
        "emergency instructions beyond advising professional care, or claims that replace a clinician."
    ),
    "medical_common_sense": (
        "Choose a Korean medical common-sense education topic for the general public. Keep it preventive, "
        "practical, and non-diagnostic. Do not provide personalized diagnosis, treatment plans, drug dosages, "
        "emergency instructions beyond advising professional care, or claims that replace a clinician."
    ),
}

_TOPIC_PROMPT_USER = (
    "Create one fresh Korean YouTube longform explainer topic as strict JSON. "
    "Avoid every used topic. The tone should be informative, practical, and suitable for a Korean audience. "
    "{category_instruction} "
    "Choose a concrete everyday problem that can be shown visually in realistic slides. "
    "Do not choose broad abstract topics, vague culture commentary, politics, disasters, or celebrities. "
    "The topic must naturally support 17 different visual scenes with Korean people, places, objects, or actions. "
    "Fields required: id, topic, title, description, tags, subject, problem, solution, example. "
    "description must include two short paragraphs and 5 Korean hashtags. "
    "tags must be a list of 5 to 7 Korean strings. "
    "subject must be an English visual prompt for realistic Korean documentary imagery, with a specific location and visible main subject. "
    "problem, solution, and example must be concise Korean phrases using standard Korean spelling. "
    "example must describe a concrete Korean real-life situation and must not include English. "
    "Do not use slang, intentionally misspelled Korean, or unclear abbreviations.\n\n"
    "Used topics:\n{used_topics}"
)


def generate_gemini_with_fallback(prompt, path):
    try:
        _generate_gemini(prompt, path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError("Gemini returned an empty image")
    except Exception as exc:
        print(f"Gemini image generation failed; falling back to OpenAI: {exc}")
        try:
            _generate_openai(prompt, path)
        except Exception as fallback_exc:
            print(f"OpenAI image fallback failed; using local visual fallback: {fallback_exc}")
            _generate_local_visual(prompt, path)


def generate_openai_with_fallback(prompt, path):
    try:
        _generate_openai(prompt, path)
    except Exception as exc:
        print(f"OpenAI image generation failed; falling back to Gemini: {exc}")
        try:
            _generate_gemini(prompt, path)
        except Exception as fallback_exc:
            print(f"Gemini image fallback failed; using local visual fallback: {fallback_exc}")
            _generate_local_visual(prompt, path)


def _generate_local_visual(prompt, path):
    digest = hashlib.sha256(prompt.encode("utf-8", errors="ignore")).digest()
    palettes = [
        ((24, 35, 55), (31, 86, 104), (235, 198, 103)),
        ((33, 38, 32), (87, 114, 84), (230, 214, 162)),
        ((44, 39, 64), (95, 87, 141), (239, 196, 138)),
        ((26, 50, 67), (77, 126, 138), (238, 220, 170)),
    ]
    bg_a, bg_b, accent = palettes[digest[0] % len(palettes)]
    small_w, small_h = 320, 180
    img = base.Image.new("RGB", (small_w, small_h), bg_a)
    pixels = img.load()
    for y in range(small_h):
        t = y / max(1, small_h - 1)
        row = tuple(int(bg_a[i] * (1 - t) + bg_b[i] * t) for i in range(3))
        for x in range(small_w):
            pixels[x, y] = row
    draw = base.ImageDraw.Draw(img, "RGBA")
    for i in range(10):
        cx = 20 + ((digest[i] * 7 + i * 31) % (small_w - 40))
        cy = 18 + ((digest[i + 10] * 5 + i * 19) % (small_h - 36))
        r = 16 + digest[i + 20] % 38
        color = (*accent, 34 + digest[i + 30] % 54)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    for i in range(4):
        y = 30 + i * 32 + digest[i + 2] % 12
        draw.line((28, y, small_w - 28, y + digest[i + 6] % 18 - 9), fill=(*accent, 62), width=2)
    img = img.resize((base.WIDTH, base.HEIGHT), base.Image.Resampling.BICUBIC)
    img = img.filter(base.ImageFilter.GaussianBlur(radius=1.1))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _parse_and_validate_topic(raw, used_topics):
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    topic = json.loads(text)
    required = {"id", "topic", "title", "description", "tags", "subject", "problem", "solution", "example"}
    missing = sorted(required - set(topic))
    if missing:
        raise RuntimeError(f"Generated topic is missing fields: {missing}")
    if topic["topic"] in used_topics:
        raise RuntimeError("Generated topic duplicated a used topic")
    return topic


def _generate_topic_openai(used_topics):
    category_instruction = _CATEGORY_INSTRUCTIONS.get(base.TOPIC_CATEGORY, _CATEGORY_INSTRUCTIONS["life"])
    client = base.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": "You return only valid JSON. Do not include markdown fences or commentary.",
            },
            {
                "role": "user",
                "content": _TOPIC_PROMPT_USER.format(
                    category_instruction=category_instruction,
                    used_topics=json.dumps(used_topics, ensure_ascii=False)
                ),
            },
        ],
        temperature=0.85,
    )
    return _parse_and_validate_topic(response.choices[0].message.content, used_topics)


def _generate_topic_gemini(used_topics):
    from google import genai

    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
    )
    category_instruction = _CATEGORY_INSTRUCTIONS.get(base.TOPIC_CATEGORY, _CATEGORY_INSTRUCTIONS["life"])
    prompt = (
        "You return only valid JSON. Do not include markdown fences or commentary.\n\n"
        + _TOPIC_PROMPT_USER.format(
            category_instruction=category_instruction,
            used_topics=json.dumps(used_topics, ensure_ascii=False)
        )
    )
    response = client.models.generate_content(
        model=os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash"),
        contents=prompt,
    )
    return _parse_and_validate_topic(response.text, used_topics)


_MANUAL_TOPIC_CANDIDATES = {
    "life": [
        {
            "id": "subscription-cleanup",
            "topic": "디지털 생활: 방치된 구독 서비스 정리하기",
            "title": "방치된 구독 서비스 정리하기",
            "description": "매달 자동 결제되는 구독 서비스가 많아지면 지출 흐름을 놓치기 쉽습니다.\n\n사용 빈도, 대체 가능성, 해지 시점을 기준으로 구독을 정리하는 방법을 설명합니다.\n\n#구독관리 #생활경제 #자동결제 #절약습관 #디지털생활",
            "tags": ["구독관리", "생활경제", "자동결제", "절약습관", "디지털생활"],
            "subject": "Korean adult reviewing subscription payments on a laptop at a small apartment desk, realistic documentary style",
            "problem": "자동 결제 구독을 방치해 불필요한 지출이 누적됨",
            "solution": "사용 빈도와 필요성을 기준으로 구독을 정리하는 것",
            "example": "한 달에 한 번도 쓰지 않는 앱이 계속 결제되는 직장인",
        },
        {
            "id": "delivery-fee-habit",
            "topic": "소비습관: 배달비가 생활비를 키우는 이유",
            "title": "배달비가 생활비를 키우는 이유",
            "description": "한 번의 배달비는 작아 보여도 반복되면 식비 구조를 크게 바꿉니다.\n\n주문 빈도, 최소 주문 금액, 대체 식사 계획을 함께 보는 방법을 설명합니다.\n\n#생활비 #배달비 #소비습관 #식비관리 #절약",
            "tags": ["생활비", "배달비", "소비습관", "식비관리", "절약"],
            "subject": "Korean person comparing delivery app orders and home meal ingredients on a kitchen table, realistic documentary style",
            "problem": "배달 주문의 반복 비용을 생활비 계획에 반영하지 않음",
            "solution": "주문 빈도와 대체 식사 계획을 함께 정하는 것",
            "example": "퇴근 후 습관적으로 배달 앱을 열어 식비가 늘어난 1인 가구",
        },
    ],
    "medical": [
        {
            "id": "hydration-signals",
            "topic": "의학상식: 물을 충분히 마시지 않을 때 나타나는 신호",
            "title": "수분 부족 신호 알아보기",
            "description": "수분 섭취가 부족하면 피로감, 집중력 저하, 입마름처럼 일상에서 알아차릴 수 있는 변화가 생길 수 있습니다.\n\n개인 진단이 아니라 생활 속 점검 기준과 물 마시는 습관을 설명합니다.\n\n#의학상식 #수분섭취 #건강습관 #생활건강 #예방",
            "tags": ["의학상식", "수분섭취", "건강습관", "생활건강", "예방"],
            "subject": "Korean office worker noticing an empty water bottle and dry mouth at a desk, realistic documentary style",
            "problem": "갈증과 피로 신호를 가볍게 넘겨 수분 섭취가 부족해짐",
            "solution": "하루 중 물 마시는 시간을 정하고 몸의 변화를 점검하는 것",
            "example": "오후마다 입이 마르고 집중이 떨어지지만 커피만 마시는 직장인",
        },
        {
            "id": "screen-eye-fatigue",
            "topic": "의학상식: 화면을 오래 볼 때 눈이 피로해지는 이유",
            "title": "눈 피로 줄이는 화면 습관",
            "description": "스마트폰과 컴퓨터 화면을 오래 보면 눈 깜박임이 줄고 피로감이 커질 수 있습니다.\n\n진단이 아니라 화면 거리, 휴식 간격, 조명 조절 같은 생활 관리 기준을 설명합니다.\n\n#의학상식 #눈피로 #화면습관 #생활건강 #예방",
            "tags": ["의학상식", "눈피로", "화면습관", "생활건강", "예방"],
            "subject": "Korean student rubbing tired eyes near a laptop and phone in a study room, realistic documentary style",
            "problem": "장시간 화면 사용 중 휴식과 거리 조절을 놓침",
            "solution": "정기적인 눈 휴식과 화면 환경 조절을 습관화하는 것",
            "example": "온라인 강의와 스마트폰 사용 후 눈이 뻑뻑해지는 학생",
        },
    ],
}


def _manual_topic_fallback(used_topics):
    category = "medical" if base.TOPIC_CATEGORY.startswith("medical") else "life"
    for topic in _MANUAL_TOPIC_CANDIDATES[category]:
        if topic["topic"] not in used_topics:
            print(f"Using manual topic fallback: {topic['topic']}")
            return topic
    raise RuntimeError("Manual topic fallback candidates are exhausted")


def generate_topic(history):
    used_topics = [x.get("topic", "") for x in history if x.get("topic")]
    max_retries = 5
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return _generate_topic_gemini(used_topics)
        except Exception as exc:
            print(f"Gemini topic generation attempt {attempt} failed: {exc}")
            last_exc = exc
        try:
            return _generate_topic_openai(used_topics)
        except Exception as exc:
            print(f"OpenAI topic generation attempt {attempt} failed: {exc}")
            last_exc = exc
    try:
        return _manual_topic_fallback(used_topics)
    except Exception as fallback_exc:
        raise RuntimeError(f"Topic generation failed after {max_retries} attempts: {last_exc}") from fallback_exc


def pick_topic(history):
    used = {x.get("topic") for x in history}
    for topic in base.TOPICS:
        if topic["topic"] not in used:
            return topic
    return generate_topic(history)


base.pick_topic = pick_topic
base.generate_gemini = generate_gemini_with_fallback
base.generate_openai = generate_openai_with_fallback


if __name__ == "__main__":
    base.main()
