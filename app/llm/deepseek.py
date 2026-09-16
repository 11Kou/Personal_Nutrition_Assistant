from typing import Any


def _success(data: Any, message: str) -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "data": None, "message": message}


def _profile_summary(profile_data: dict[str, Any]) -> str:
    lines = []
    labels = {
        "height_cm": "身高 cm",
        "weight_kg": "体重 kg",
        "body_fat_percent": "体脂率 %",
        "age": "年龄",
        "sex": "性别",
        "goal": "目标",
        "injuries": "伤病禁忌",
        "diet_preferences": "饮食偏好",
        "training_conditions": "训练条件",
        "activity_level": "活动水平",
    }
    for key, label in labels.items():
        value = profile_data.get(key)
        if value is None or value == "" or value == []:
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        lines.append(f"- {label}: {value}")
    if not lines:
        return "- 未提供用户画像"
    return "\n".join(lines)


def _source_summary(sources: list[dict[str, Any]]) -> str:
    lines = []
    for source in sources:
        index = source.get("index")
        title = source.get("title")
        snippet = source.get("snippet")
        lines.append(f"[{index}] {title}: {snippet}")
    return "\n".join(lines)


def _build_messages(
    question: str,
    profile_data: dict[str, Any],
    rag_data: dict[str, Any],
) -> list[tuple[str, str]]:
    sources = rag_data.get("sources", [])
    system_prompt = "\n".join(
        [
            "你是一个个性化健身营养助手。",
            "你只能基于已提供的本地 RAG 资料、用户画像和工具结果回答。",
            "不要编造来源、公式、医学诊断或不存在的数值。",
            "如果资料不足，要明确说资料不足。",
            "回答必须保留来源编号，例如 [1]、[2]。",
            "涉及疾病、伤病、诊断、治疗或用药时，提醒咨询医生、物理治疗师或注册营养师。",
            "用中文回答，格式清晰，尽量分成：建议、原因、注意事项、来源。",
        ]
    )
    user_prompt = "\n\n".join(
        [
            f"用户问题：{question}",
            f"用户画像：\n{_profile_summary(profile_data)}",
            f"本地 RAG 初步回答：\n{rag_data.get('answer', '')}",
            f"可引用来源：\n{_source_summary(sources)}",
        ]
    )
    return [("system", system_prompt), ("user", user_prompt)]


def create_deepseek_model(
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model_name: str = "deepseek-flash",
    temperature: float = 0.2,
) -> dict[str, Any]:
    """[Agent-Ready] Create a DeepSeek OpenAI-compatible chat model."""
    try:
        if not str(api_key).strip():
            raise ValueError("api_key cannot be empty")
        if not str(base_url).strip():
            raise ValueError("base_url cannot be empty")
        if not str(model_name).strip():
            raise ValueError("model_name cannot be empty")

        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
        )
        return _success({"model": model}, "DeepSeek model created.")
    except Exception as exc:
        return _error(f"Failed to create DeepSeek model: {exc}")


def generate_deepseek_rag_answer(
    question: str,
    profile_data: dict[str, Any],
    rag_data: dict[str, Any],
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model_name: str = "deepseek-flash",
    temperature: float = 0.2,
    model: Any | None = None,
) -> dict[str, Any]:
    """[Agent-Ready] Generate a natural answer with DeepSeek from local RAG evidence."""
    try:
        cleaned_question = str(question).strip()
        if not cleaned_question:
            raise ValueError("question cannot be empty")
        if not isinstance(profile_data, dict):
            raise TypeError("profile_data must be a dictionary")
        if not isinstance(rag_data, dict):
            raise TypeError("rag_data must be a dictionary")
        sources = rag_data.get("sources", [])
        if not sources:
            return _success(
                {
                    "answer": rag_data.get(
                        "answer",
                        "没有在本地知识库中找到可靠来源，因此不调用大模型生成回答。",
                    ),
                    "model_name": None,
                    "used_llm": False,
                },
                "Skipped DeepSeek because no RAG sources were available.",
            )

        selected_model = model
        if selected_model is None:
            model_result = create_deepseek_model(
                api_key=api_key,
                base_url=base_url,
                model_name=model_name,
                temperature=temperature,
            )
            if model_result["status"] == "error":
                return model_result
            selected_model = model_result["data"]["model"]

        response = selected_model.invoke(_build_messages(cleaned_question, profile_data, rag_data))
        answer = str(getattr(response, "content", response)).strip()
        if not answer:
            raise ValueError("DeepSeek returned an empty answer")

        return _success(
            {
                "answer": answer,
                "model_name": model_name,
                "used_llm": True,
            },
            "DeepSeek answer generated.",
        )
    except Exception as exc:
        return _error(f"Failed to generate DeepSeek answer: {exc}")

