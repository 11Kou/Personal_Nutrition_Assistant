from pathlib import Path
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.nutrition.calculations import calculate_bmi
from app.ui.actions import (
    ask_question_from_ui,
    get_ui_settings,
    ingest_documents_from_ui,
    list_profile_sidebar_items,
    load_profile_for_ui,
    save_profile_from_form,
)


GOAL_OPTIONS = {
    "减脂": "fat_loss",
    "增肌": "muscle_gain",
    "维持": "maintenance",
    "养生": "wellness",
}

SEX_OPTIONS = {
    "男": "male",
    "女": "female",
    "其他": "other",
}

ACTIVITY_OPTIONS = {
    "久坐": "sedentary",
    "轻度活动": "light",
    "中等活动": "moderate",
    "活跃": "active",
    "非常活跃": "very_active",
}

INJURY_OPTIONS = ["膝伤", "肩伤", "腰痛", "背伤", "踝伤", "手腕伤", "无"]
DIET_OPTIONS = ["乳糖不耐", "素食", "纯素", "不吃猪肉", "不吃牛肉", "海鲜过敏", "坚果过敏", "无"]
TRAINING_OPTIONS = ["居家", "健身房", "无器械", "哑铃", "杠铃", "弹力带", "跑步机", "固定自行车"]


def _split_tags(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _merge_selected_and_extra(selected: list[str], extra: str) -> list[str]:
    values = [item for item in selected if item != "无"]
    values.extend(_split_tags(extra))
    merged = []
    seen = set()
    for value in values:
        if value and value not in seen:
            merged.append(value)
            seen.add(value)
    return merged


def _default_selected(existing_values: list[str] | None, options: list[str]) -> list[str]:
    if not existing_values:
        return []
    return [value for value in existing_values if value in options]


def _default_extra(existing_values: list[str] | None, options: list[str]) -> str:
    if not existing_values:
        return ""
    return ", ".join(value for value in existing_values if value not in options)


def _show_result(result: dict) -> None:
    if result["status"] == "success":
        st.success(result["message"])
    else:
        st.error(result["message"])


def _settings() -> dict:
    result = get_ui_settings()
    if result["status"] == "error":
        st.error(result["message"])
        st.stop()
    return result["data"]


def render_profile_sidebar(settings: dict) -> None:
    st.sidebar.divider()
    st.sidebar.subheader("画像列表")
    result = list_profile_sidebar_items(settings["database_url"])
    if result["status"] == "error":
        st.sidebar.caption(result["message"])
        return
    if not result["data"]:
        st.sidebar.caption("暂无已保存画像")
        return

    for item in result["data"]:
        with st.sidebar.expander(item["user_id"]):
            if item["recent_questions"]:
                for question in item["recent_questions"]:
                    st.caption(question["question"])
            else:
                st.caption("暂无过往问题")


def render_profile_page(settings: dict) -> None:
    st.header("用户画像")
    user_id = st.text_input("用户 ID", value="demo-user")

    existing_profile = None
    if user_id:
        profile_result = load_profile_for_ui(settings["database_url"], user_id)
        if profile_result["status"] == "success":
            existing_profile = profile_result["data"]

    height_cm = st.number_input(
        "身高 cm",
        min_value=1.0,
        max_value=300.0,
        value=float(existing_profile.get("height_cm", 175) if existing_profile else 175),
        step=0.5,
        format="%.1f",
    )
    weight_kg = st.number_input(
        "体重 kg",
        min_value=1.0,
        max_value=500.0,
        value=float(existing_profile.get("weight_kg", 70) if existing_profile else 70),
        step=0.5,
        format="%.1f",
    )
    bmi_result = calculate_bmi({"height_cm": height_cm, "weight_kg": weight_kg})
    if bmi_result["status"] == "success":
        bmi_data = bmi_result["data"]
        st.metric("BMI 自动计算", f"{bmi_data['result']} {bmi_data['unit']}")
        st.caption(f"公式：{bmi_data['formula']}")

    existing_body_fat = existing_profile.get("body_fat_percent") if existing_profile else None
    knows_body_fat = st.checkbox("添加体脂率", value=existing_body_fat is not None)
    st.caption("不添加时不会使用默认体脂率，也不会把体脂率纳入后续计算或回答。")
    body_fat_percent = None
    if knows_body_fat:
        body_fat_percent = st.number_input(
            "体脂率 %",
            min_value=0.0,
            max_value=80.0,
            value=float(existing_body_fat if existing_body_fat is not None else 18),
            step=0.5,
            format="%.1f",
        )
    age = st.number_input(
        "年龄",
        min_value=1,
        max_value=120,
        value=int(existing_profile.get("age", 28) if existing_profile else 28),
        step=1,
    )
    sex_label = st.selectbox("性别", list(SEX_OPTIONS.keys()))
    goal_label = st.selectbox("目标", list(GOAL_OPTIONS.keys()))
    activity_label = st.selectbox("活动水平", list(ACTIVITY_OPTIONS.keys()), index=2)
    existing_injuries = existing_profile.get("injuries", []) if existing_profile else []
    existing_diet_preferences = existing_profile.get("diet_preferences", []) if existing_profile else []
    existing_training_conditions = existing_profile.get("training_conditions", []) if existing_profile else []

    injury_tab, diet_tab, training_tab = st.tabs(["伤病禁忌", "饮食偏好", "训练条件"])
    with injury_tab:
        injury_selected = st.multiselect(
            "选择伤病禁忌",
            INJURY_OPTIONS,
            default=_default_selected(existing_injuries, INJURY_OPTIONS),
        )
        injury_extra = st.text_input(
            "情况补充",
            value=_default_extra(existing_injuries, INJURY_OPTIONS),
            placeholder="例如：髋关节不适、颈椎不适",
            key="injury_extra",
        )
    with diet_tab:
        diet_selected = st.multiselect(
            "选择饮食偏好",
            DIET_OPTIONS,
            default=_default_selected(existing_diet_preferences, DIET_OPTIONS),
        )
        diet_extra = st.text_input(
            "情况补充",
            value=_default_extra(existing_diet_preferences, DIET_OPTIONS),
            placeholder="例如：不吃辣、控糖",
            key="diet_extra",
        )
    with training_tab:
        training_selected = st.multiselect(
            "选择训练条件",
            TRAINING_OPTIONS,
            default=_default_selected(existing_training_conditions, TRAINING_OPTIONS),
        )
        training_extra = st.text_input(
            "情况补充",
            value=_default_extra(existing_training_conditions, TRAINING_OPTIONS),
            placeholder="例如：小区健身器械、每次30分钟",
            key="training_extra",
        )
    submitted = st.button("保存画像")

    if submitted:
        result = save_profile_from_form(
            settings["database_url"],
            {
                "user_id": user_id,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "body_fat_percent": body_fat_percent,
                "age": age,
                "sex": SEX_OPTIONS[sex_label],
                "goal": GOAL_OPTIONS[goal_label],
                "injuries": _merge_selected_and_extra(injury_selected, injury_extra),
                "diet_preferences": _merge_selected_and_extra(diet_selected, diet_extra),
                "training_conditions": _merge_selected_and_extra(training_selected, training_extra),
                "activity_level": ACTIVITY_OPTIONS[activity_label],
            },
        )
        _show_result(result)

    if existing_profile:
        st.subheader("当前画像")
        st.json(existing_profile)


def render_documents_page(settings: dict) -> None:
    st.header("资料库")
    documents_dir = st.text_input("资料目录", value=settings["documents_dir"])
    index_dir = st.text_input("索引目录", value=str(Path(settings["chroma_dir"]).parent / "index"))
    use_chroma = st.checkbox("同时写入 Chroma", value=False)

    if st.button("入库资料"):
        result = ingest_documents_from_ui(
            document_paths=[documents_dir],
            index_dir=index_dir,
            use_chroma=use_chroma,
        )
        _show_result(result)
        if result["status"] == "success":
            st.json(result["data"])


def render_chat_page(settings: dict) -> None:
    st.header("问答")
    user_id = st.text_input("用户 ID", value="demo-user", key="chat_user_id")
    index_dir = st.text_input("索引目录", value=str(Path(settings["chroma_dir"]).parent / "index"), key="chat_index_dir")
    top_k = st.slider("来源数量", min_value=1, max_value=10, value=5)
    use_chroma = st.checkbox("使用 Chroma 检索", value=False, key="chat_use_chroma")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    if st.button("清空对话"):
        st.session_state.chat_messages = []

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("来源"):
                    for source in message["sources"]:
                        st.markdown(f"**[{source['index']}] {source['title']}**")
                        st.caption(source["source"])
                        st.markdown(source["snippet"])
            if message.get("removed_chunks"):
                with st.expander("已过滤内容"):
                    st.json(message["removed_chunks"])

    question = st.chat_input("输入你的问题")
    if question:
        st.session_state.chat_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        profile_result = load_profile_for_ui(settings["database_url"], user_id)
        if profile_result["status"] == "error":
            assistant_message = {
                "role": "assistant",
                "content": "请先在用户画像页保存画像。",
            }
            st.session_state.chat_messages.append(assistant_message)
            with st.chat_message("assistant"):
                st.error(assistant_message["content"])
            return

        result = ask_question_from_ui(
            question=question,
            profile_data=profile_result["data"],
            index_dir=index_dir,
            top_k=top_k,
            use_chroma=use_chroma,
            database_url_or_path=settings["database_url"],
            user_id=user_id,
        )
        if result["status"] == "error":
            assistant_message = {
                "role": "assistant",
                "content": result["message"],
            }
            st.session_state.chat_messages.append(assistant_message)
            with st.chat_message("assistant"):
                st.error(assistant_message["content"])
            return

        assistant_message = {
            "role": "assistant",
            "content": result["data"]["answer"],
            "sources": result["data"]["sources"],
            "removed_chunks": result["data"].get("removed_chunks", []),
        }
        st.session_state.chat_messages.append(assistant_message)
        with st.chat_message("assistant"):
            st.markdown(assistant_message["content"])
            if assistant_message["sources"]:
                with st.expander("来源"):
                    for source in assistant_message["sources"]:
                        st.markdown(f"**[{source['index']}] {source['title']}**")
                        st.caption(source["source"])
                        st.markdown(source["snippet"])
            if assistant_message["removed_chunks"]:
                with st.expander("已过滤内容"):
                    st.json(assistant_message["removed_chunks"])


def main() -> None:
    st.set_page_config(page_title="Personal Nutrition Assistant", layout="wide")
    st.title("Personal Nutrition Assistant")
    settings = _settings()

    page = st.sidebar.radio("页面", ["用户画像", "资料库", "问答"])
    render_profile_sidebar(settings)
    if page == "用户画像":
        render_profile_page(settings)
    elif page == "资料库":
        render_documents_page(settings)
    else:
        render_chat_page(settings)


if __name__ == "__main__":
    main()
