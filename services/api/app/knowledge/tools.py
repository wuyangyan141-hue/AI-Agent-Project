from langchain_core.tools import tool


def create_member1_tools(service, user_id="local-user"):
    """Bind the user on the server, never let the model choose somebody else's profile."""

    @tool
    def search_knowledge(query: str) -> dict:
        """检索用户上传的课程文档，返回原文、文件名、真实页码或正文片段位置；回答资料问题前先使用。"""
        return {"sources": service.search(user_id, query)}

    @tool
    def get_learning_preferences() -> dict:
        """读取用户明确设置的学习时段、回答语言、解释方式等偏好；制定学习计划前使用。"""
        return service.preferences(user_id)

    @tool
    def search_user_memory(query: str) -> list[dict]:
        """按问题检索该用户明确保存的长期记忆；记忆是个人信息，不能代替课程资料的证据。"""
        return service.search_memories(user_id, query)

    return [search_knowledge, get_learning_preferences, search_user_memory]
