import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'quiet' | 'danger';

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  compact?: boolean;
};

/** Pawprint l-btn 变体：每视图建议仅一个 primary（饼干黄） */
export function PawprintButton({
  variant = 'secondary',
  compact,
  className,
  type = 'button',
  ...rest
}: Props) {
  const classes = [
    'pp-btn',
    `pp-btn--${variant}`,
    compact ? 'pp-btn--compact' : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ');
  return <button type={type} className={classes} {...rest} />;
}