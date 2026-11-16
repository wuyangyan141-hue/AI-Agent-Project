import type { ReactNode } from 'react';
import type { CareTimelineStatus } from './careTimeline';
import { careStatusLabel } from './careTimeline';

const variantClass: Record<CareTimelineStatus, string> = {
  done: 'pp-badge--done',
  due: 'pp-badge--due',
  overdue: 'pp-badge--overdue',
  upcoming: 'pp-badge--upcoming',
};

type Props = {
  status?: CareTimelineStatus;
  children?: ReactNode;
  className?: string;
};

/** Pawprint 状态徽章：文字 + 圆点，不单靠颜色传达含义 */
export function PawprintBadge({ status, children, className }: Props) {
  const label = children ?? (status != null ? careStatusLabel(status) : null);
  if (label == null) return null;
  const extra = status != null ? variantClass[status] : '';
  const classes = ['pp-badge', extra, className ?? ''].filter(Boolean).join(' ');
  return (
    <span className={classes}>
      <span className="pp-badge-dot" aria-hidden="true" />
      {label}
    </span>
  );
}