from pathlib import Path

import streamlit as st

from app.ui.actions import (
    ask_question_from_ui,
    get_ui_settings,
    ingest_documents_from_ui,
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


def _split_tags(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


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


def render_profile_page(settings: dict) -> None:
    st.header("用户画像")
    user_id = st.text_input("用户 ID", value="demo-user")

    existing_profile = None
    if user_id:
        profile_result = load_profile_for_ui(settings["database_url"], user_id)
        if profile_result["status"] == "success":
            existing_profile = profile_result["data"]

    with st.form("profile_form"):
        height_cm = st.number_input(
            "身高 cm",
            min_value=1.0,
            max_value=300.0,
            value=float(existing_profile.get("height_cm", 175) if existing_profile else 175),
        )
        weight_kg = st.number_input(
            "体重 kg",
            min_value=1.0,
            max_value=500.0,
            value=float(existing_profile.get("weight_kg", 70) if existing_profile else 70),
        )
        body_fat_percent = st.number_input(
            "体脂率 %",
            min_value=0.0,
            max_value=80.0,
            value=float(existing_profile.get("body_fat_percent", 18) if existing_profile else 18),
        )
        age = st.number_input(
            "年龄",
            min_value=1,
            max_value=120,
            value=int(existing_profile.get("age", 28) if existing_profile else 28),
        )
        sex_label = st.selectbox("性别", list(SEX_OPTIONS.keys()))
        goal_label = st.selectbox("目标", list(GOAL_OPTIONS.keys()))
        activity_label = st.selectbox("活动水平", list(ACTIVITY_OPTIONS.keys()), index=2)
        injuries = st.text_input("伤病禁忌，用英文逗号分隔", value="膝伤")
        diet_preferences = st.text_input("饮食偏好，用英文逗号分隔", value="乳糖不耐")
        training_conditions = st.text_input("训练条件，用英文逗号分隔", value="居家, 哑铃")
        submitted = st.form_submit_button("保存画像")

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
                "injuries": _split_tags(injuries),
                "diet_preferences": _split_tags(diet_preferences),
                "training_conditions": _split_tags(training_conditions),
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
    question = st.text_area("问题", value="膝伤用户怎么做居家训练？")
    index_dir = st.text_input("索引目录", value=str(Path(settings["chroma_dir"]).parent / "index"), key="chat_index_dir")
    top_k = st.slider("来源数量", min_value=1, max_value=10, value=5)
    use_chroma = st.checkbox("使用 Chroma 检索", value=False, key="chat_use_chroma")

    if st.button("提交问题"):
        profile_result = load_profile_for_ui(settings["database_url"], user_id)
        if profile_result["status"] == "error":
            st.error("请先在用户画像页保存画像。")
            return

        result = ask_question_from_ui(
            question=question,
            profile_data=profile_result["data"],
            index_dir=index_dir,
            top_k=top_k,
            use_chroma=use_chroma,
        )
        if result["status"] == "error":
            st.error(result["message"])
            return

        st.subheader("回答")
        st.write(result["data"]["answer"])

        st.subheader("来源")
        for source in result["data"]["sources"]:
            st.markdown(f"**[{source['index']}] {source['title']}**")
            st.caption(source["source"])
            st.write(source["snippet"])

        if result["data"].get("removed_chunks"):
            st.subheader("已过滤内容")
            st.json(result["data"]["removed_chunks"])


def main() -> None:
    st.set_page_config(page_title="Personal Nutrition Assistant", layout="wide")
    st.title("Personal Nutrition Assistant")
    settings = _settings()

    page = st.sidebar.radio("页面", ["用户画像", "资料库", "问答"])
    if page == "用户画像":
        render_profile_page(settings)
    elif page == "资料库":
        render_documents_page(settings)
    else:
        render_chat_page(settings)


if __name__ == "__main__":
    main()
