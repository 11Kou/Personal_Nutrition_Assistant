from app.llm.deepseek import create_deepseek_model, generate_deepseek_rag_answer


def assert_result_shape(result):
    assert set(result.keys()) == {"status", "data", "message"}
    assert result["status"] in {"success", "error"}
    assert isinstance(result["message"], str)


class FakeResponse:
    content = "建议以低冲击训练为主，并参考来源 [1]。"


class FakeModel:
    def __init__(self):
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return FakeResponse()


def test_create_deepseek_model_rejects_empty_key():
    result = create_deepseek_model(api_key="")

    assert_result_shape(result)
    assert result["status"] == "error"
    assert result["data"] is None


def test_generate_deepseek_rag_answer_uses_injected_model():
    model = FakeModel()
    result = generate_deepseek_rag_answer(
        question="膝伤怎么训练？",
        profile_data={"goal": "fat_loss", "injuries": ["膝伤"]},
        rag_data={
            "answer": "本地 RAG 回答 [1]",
            "sources": [
                {
                    "index": 1,
                    "title": "膝伤训练",
                    "snippet": "膝伤用户可以选择固定自行车。",
                }
            ],
        },
        api_key="test-key",
        model_name="deepseek-flash",
        model=model,
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["used_llm"] is True
    assert result["data"]["model_name"] == "deepseek-flash"
    assert "来源 [1]" in result["data"]["answer"]
    assert model.messages is not None


def test_generate_deepseek_rag_answer_skips_without_sources():
    result = generate_deepseek_rag_answer(
        question="没有资料的问题",
        profile_data={},
        rag_data={"answer": "没有在本地知识库中找到可靠来源。", "sources": []},
        api_key="test-key",
    )

    assert_result_shape(result)
    assert result["status"] == "success"
    assert result["data"]["used_llm"] is False
    assert "没有在本地知识库中找到可靠来源" in result["data"]["answer"]

