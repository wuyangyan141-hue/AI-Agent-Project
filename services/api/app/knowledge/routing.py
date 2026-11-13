"""Conservative request routing shared by REST, WebSocket and the desktop pet."""
import re

FOLLOWUP = re.compile(r"^(那|它|这个|这些|刚才|上述|为什么呢|再详细|举个例子|继续解释|then\b|what about\b|why\b|give an example\b)", re.I)
SUMMARY = re.compile(r"总结|概述|摘要|讲什么|讲了什么|主要内容|全文|summary|summari[sz]e|overview", re.I)
COMPARE = re.compile(r"对比|比较|异同|区别|compare|comparison|difference", re.I)
SOCIAL = re.compile(
    r"^(你好|嗨|hi\b|hello\b|在吗|早上好|晚上好|谢谢|晚安|再见|今天好累|我好累|我累了|"
    r"陪我聊|聊聊天|心情|今天天气|讲个笑话|你叫什么|你是谁)",
    re.I,
)
# Soft companionship — never treat as knowledge Q&A even with uploaded docs.
COMPANION = re.compile(
    r'陪我学习|陪我学|一起学习|一起学|来陪我|跟我学|我们一起学|陪学|想学习了|'
    r'开始学习吧|来学习|学一会儿|陪读|keep me company',
    re.I,
)
# Confusion / ask-for-explanation must route to knowledge — never become a plan goal.
CONFUSED = re.compile(
    r'看不懂|听不懂|看不明白|听不明白|不理解|没看懂|没听懂|不太懂|完全不懂|太难了|'
    r'什么意思|讲清楚|讲明白|讲简单|说简单|通俗点|再讲讲|再解释|能不能解释|'
    r"don'?t understand|too hard|explain (it|this|again)",
    re.I,
)
QUESTION = re.compile(
    r"[?？]|什么|为何|为什么|解释|讲解|如何|怎么|资料|文档|讲义|课件|根据|"
    r"看不懂|听不懂|不理解|没看懂|什么意思|讲清楚|讲明白|太难了|"
    r"\b(what|why|how|explain|describe|according)\b",
    re.I,
)


def route_request(text, *, forced=False, general=False, has_documents=False, active_topic=False):
    if general:
        return 'chat'
    # Companion / greeting lines stay chat even when documents are selected.
    stripped = text.strip()
    if SOCIAL.search(stripped) or COMPANION.search(stripped):
        return 'chat'
    if has_documents or forced:
        if SUMMARY.search(text):
            return 'summary'
        if COMPARE.search(text):
            return 'compare'
        if forced or QUESTION.search(text) or (active_topic and FOLLOWUP.search(text)):
            return 'knowledge'
    return 'chat'
