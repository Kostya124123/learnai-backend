"""
LLM Service — реальная интеграция с LM Studio через OpenAI-совместимый API.
"""
import httpx
import os
import random
from typing import Optional

LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen2.5-7b-instruct")


async def _chat(messages: list, temperature: float = 0.3, max_tokens: int = 2048) -> str:
    """Отправляет запрос к LM Studio и возвращает текст ответа."""
    url = f"{LM_STUDIO_URL}/chat/completions"
    payload = {
        "model": LM_STUDIO_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
    }
    try:
        # Отключаем прокси для локальных запросов к LM Studio
        async with httpx.AsyncClient(timeout=120.0, proxies={}) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"LM Studio недоступен: {e}")


async def generate_course_content(title: str, doc_text: Optional[str] = None) -> dict:
    """
    Генерирует курс через LM Studio на основе текста документа.
    """
    context = doc_text[:3000] if doc_text else ""

    system_prompt = (
        "Ты — корпоративный тренер. Создаёшь учебные материалы на основе документов организации. "
        "Отвечай строго на русском языке. Используй Markdown для форматирования."
    )

    # 1. Теория
    theory_prompt = (
        f"На основе следующего документа создай теоретический учебный модуль по теме '{title}'.\n\n"
        f"ДОКУМЕНТ:\n{context}\n\n"
        "Структура модуля:\n"
        "## Основные концепции\n"
        "## Цели обучения\n"
        "## Содержание (с подразделами)\n"
        "## Итоги раздела\n\n"
        "Пиши конкретно по содержимому документа. Объём: 300-500 слов."
    )

    theory_content = await _chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": theory_prompt},
    ], temperature=0.3)

    # 2. Тест
    test_prompt = (
        f"На основе следующего документа создай ровно 5 тестовых вопросов по теме '{title}'.\n\n"
        f"ДОКУМЕНТ:\n{context}\n\n"
        "Требования к каждому вопросу:\n"
        "- 4 варианта ответа\n"
        "- Один правильный ответ\n"
        "- Вопросы должны проверять понимание документа\n\n"
        "Отвечай СТРОГО в формате JSON (без markdown-блоков, только чистый JSON):\n"
        '[\n'
        '  {\n'
        '    "question": "текст вопроса",\n'
        '    "options": ["вариант1", "вариант2", "вариант3", "вариант4"],\n'
        '    "correct_answer": "правильный вариант",\n'
        '    "points": 10\n'
        '  }\n'
        ']'
    )

    questions = _get_stub_questions()
    try:
        test_raw = await _chat([
            {"role": "system", "content": "Ты создаёшь тестовые вопросы. Отвечай только валидным JSON."},
            {"role": "user", "content": test_prompt},
        ], temperature=0.2, max_tokens=1500)

        # Очищаем от markdown-блоков если есть
        clean = test_raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        import json
        parsed = json.loads(clean)
        if isinstance(parsed, list) and len(parsed) > 0:
            questions = parsed
    except Exception:
        pass  # используем заглушку если LLM вернула невалидный JSON

    # 3. Кейс
    case_prompt = (
        f"На основе следующего документа создай практический кейс по теме '{title}'.\n\n"
        f"ДОКУМЕНТ:\n{context}\n\n"
        "Структура кейса:\n"
        "## Ситуация\n"
        "(опиши реалистичную рабочую ситуацию из документа)\n"
        "## Задание\n"
        "(4 вопроса для самостоятельного разбора)\n"
        "## Критерии оценки\n"
        "(3 критерия с процентами)\n\n"
        "Объём: 200-300 слов."
    )

    case_content = await _chat([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": case_prompt},
    ], temperature=0.4)

    return {
        "modules": [
            {
                "module_type": "theory",
                "order_index": 1,
                "title": f"Теория: {title}",
                "content": theory_content,
            },
            {
                "module_type": "test",
                "order_index": 2,
                "title": "Тест: проверка знаний",
                "content": "Ответьте на вопросы по изученному материалу.",
                "questions": questions,
            },
            {
                "module_type": "case",
                "order_index": 3,
                "title": "Кейс: практическое задание",
                "content": case_content,
            },
        ]
    }


async def answer_question(question: str, context: str = "") -> dict:
    """
    Отвечает на вопрос пользователя используя RAG-контекст из документов.
    """
    system_prompt = (
        "Ты — корпоративный AI-ассистент платформы обучения LearnAI. "
        "ВАЖНО: Ты ВСЕГДА отвечаешь ТОЛЬКО на русском языке. Никогда не используй китайский, английский или другие языки. "
        "Отвечай ТОЛЬКО на основе предоставленного контекста из документов. "
        "Если ответа нет в документах — так и скажи. "
        "Будь кратким и конкретным."
    )

    if context:
        user_message = (
            f"КОНТЕКСТ ИЗ ДОКУМЕНТОВ:\n{context}\n\n"
            f"ВОПРОС: {question}\n\n"
            "Ответь на вопрос строго на основе контекста выше."
        )
        source = "корпоративные документы"
    else:
        user_message = (
            f"ВОПРОС: {question}\n\n"
            "Документы не загружены. Сообщи пользователю, что для получения ответов "
            "необходимо сначала загрузить корпоративные документы через HR-панель."
        )
        source = "нет загруженных документов"

    try:
        answer = await _chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ], temperature=0.2, max_tokens=1024)

        return {"answer": answer, "source": source}

    except RuntimeError as e:
        return {
            "answer": (
                f"⚠️ LM Studio недоступен: {e}\n\n"
                "Проверьте что LM Studio запущен с загруженной моделью и туннель ngrok/localtunnel активен."
            ),
            "source": "ошибка подключения"
        }


def _get_stub_questions() -> list:
    """Запасные вопросы если LLM не смогла сгенерировать JSON."""
    return random.sample([
        {
            "question": "Какое первое действие необходимо выполнить при обнаружении нарушения регламента?",
            "options": [
                "Продолжить работу и сообщить в конце смены",
                "Остановить работу и уведомить руководителя",
                "Самостоятельно устранить нарушение",
                "Занести в отчёт без уведомления"
            ],
            "correct_answer": "Остановить работу и уведомить руководителя",
            "points": 10
        },
        {
            "question": "Кто несёт ответственность за соблюдение требований регламента?",
            "options": [
                "Только руководитель отдела",
                "Только сотрудники службы безопасности",
                "Каждый сотрудник в пределах своих обязанностей",
                "Исключительно HR-отдел"
            ],
            "correct_answer": "Каждый сотрудник в пределах своих обязанностей",
            "points": 10
        },
        {
            "question": "Что необходимо зафиксировать при возникновении нестандартной ситуации?",
            "options": [
                "Только устно сообщить коллегам",
                "Время, место, описание ситуации и принятые меры",
                "Только конечный результат ситуации",
                "Фиксация не требуется"
            ],
            "correct_answer": "Время, место, описание ситуации и принятые меры",
            "points": 10
        },
        {
            "question": "Как часто необходимо проходить повторный инструктаж по регламенту?",
            "options": [
                "Один раз при приёме на работу",
                "Только при изменении регламента",
                "Раз в год или при изменении требований",
                "Каждый месяц"
            ],
            "correct_answer": "Раз в год или при изменении требований",
            "points": 10
        },
        {
            "question": "Какой документ является основным при разрешении спорных ситуаций?",
            "options": [
                "Личная переписка сотрудников",
                "Устные договорённости",
                "Утверждённый регламент и журнал фиксации событий",
                "Мнение большинства сотрудников"
            ],
            "correct_answer": "Утверждённый регламент и журнал фиксации событий",
            "points": 10
        },
    ], 5)
