import type { ReactNode } from 'react';

export type StampTone = 'seal' | 'ink' | 'brass' | 'faint';

interface StampProps {
  tone?: StampTone;
  children: ReactNode;
  rotate?: number;
  title?: string;
}

/** 朱红/墨绿印章：用于置信度、风险档位、状态等「档案戳记」。 */
export default function Stamp({ tone = 'ink', children, rotate = -2, title }: StampProps) {
  return (
    <span className={`stamp stamp-${tone}`} title={title} style={{ transform: `rotate(${rotate}deg)` }}>
      {children}
    </span>
  );
}
