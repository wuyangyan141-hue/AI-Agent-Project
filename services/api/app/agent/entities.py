"""Normalize spoken / typed entities before intent routing."""
from __future__ import annotations

import re

_DIGIT = {
    '零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
}


def _cn_to_int(token: str) -> int | None:
    token = token.strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token == '十':
        return 10
    if token == '半':
        return None
    if token.endswith('十') and len(token) == 2 and token[0] in _DIGIT:
        return _DIGIT[token[0]] * 10
    if token.startswith('十') and len(token) == 2 and token[1] in _DIGIT:
        return 10 + _DIGIT[token[1]]
    if len(token) == 3 and token[1] == '十' and token[0] in _DIGIT and token[2] in _DIGIT:
        return _DIGIT[token[0]] * 10 + _DIGIT[token[2]]
    if len(token) == 1 and token in _DIGIT:
        return _DIGIT[token]
    return None


def normalize_zh_numerals(text: str) -> str:
    """Replace common Chinese numerals with Arabic digits for command parsing."""
    out = text
    out = re.sub(r'半\s*分钟', '30秒', out)
    out = re.sub(r'半\s*分', '30秒', out)

    def repl_minutes(match: re.Match[str]) -> str:
        value = _cn_to_int(match.group(1))
        return f'{value}分钟' if value is not None else match.group(0)

    def repl_seconds(match: re.Match[str]) -> str:
        value = _cn_to_int(match.group(1))
        return f'{value}秒' if value is not None else match.group(0)

    out = re.sub(r'([零〇一二两三四五六七八九十半]{1,3})\s*分钟', repl_minutes, out)
    out = re.sub(r'([零〇一二两三四五六七八九十半]{1,3})\s*秒', repl_seconds, out)
    return out


def normalize_utterance(text: str) -> str:
    """Light cleanup shared by speech and typed commands."""
    cleaned = text.strip()
    cleaned = cleaned.replace('ｓ', 's').replace('Ｓ', 's')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = normalize_zh_numerals(cleaned)
    return cleaned


SKIP_REVIEW = re.compile(r'跳过(这题|本题|复习)?|取消复习|先不答|下次再答')
# Short give-ups / ask-for-key while a review is waiting — reveal the answer, don't RAG.
GIVE_UP_REVIEW = re.compile(
    r'^\s*(?:'
    r'(?:我)?(?:不知道|不会|不懂|不清楚|不太清楚|答不上来|没学过|不会做|蒙的|随便|pass|idk)'
    r'|(?:这题|本题)?(?:的)?(?:标准|正确)?答案(?:是什么|是啥|呢)?'
    r'|告诉我(?:一下)?(?:这题|本题)?(?:的)?(?:标准|正确)?答案'
    r'|正确答案(?:是什么|是啥|呢)?'
    r'|直接给答案|公布答案|揭晓答案'
    r')\s*[。.!！…？?]?\s*$',
    re.I,
)


# Bare option keys / “选项B” / “B. …” while a card is waiting.
OBJECTIVE_OPTION_ANSWER = re.compile(
    r'^\s*(?:选项\s*)?([A-Da-d])(?:\s*[.、:：)]\s*.*)?\s*$',
)


def is_skip_review(text: str) -> bool:
    return bool(SKIP_REVIEW.search(text))


def is_give_up_review(text: str) -> bool:
    return bool(GIVE_UP_REVIEW.match((text or '').strip()))


def is_objective_review_answer(text: str) -> bool:
    return bool(OBJECTIVE_OPTION_ANSWER.match((text or '').strip()))
