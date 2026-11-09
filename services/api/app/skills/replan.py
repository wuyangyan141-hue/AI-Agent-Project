"""Constraint-checked schedule proposal; changes require explicit confirmation."""


def propose_replan(tasks: list[dict], days: int, minutes_per_day: int) -> dict:
    if not 1 <= days <= 14 or not 15 <= minutes_per_day <= 240:
        raise ValueError('Invalid time budget')
    remaining = [task for task in sorted(tasks, key=lambda t: t['id']) if not task['done']]
    if not remaining:
        raise ValueError('No unfinished tasks')
    schedule = []
    day, used = 1, 0
    for task in remaining:
        minutes = task['estimated_minutes']
        if minutes > minutes_per_day:
            raise ValueError('A task exceeds the daily budget; split it first')
        if used + minutes > minutes_per_day:
            day, used = day + 1, 0
        if day > days:
            raise ValueError('Not enough time to schedule all unfinished tasks')
        schedule.append({'task_id': task['id'], 'title': task['title'], 'day': day, 'minutes': minutes, 'previous_day': task['scheduled_day']})
        used += minutes
    return {'days': days, 'minutes_per_day': minutes_per_day, 'schedule': schedule, 'reason': '按现有任务顺序安排，单日时长不超过预算。请确认后保存。'}
