import styles from './Skeleton.module.css';

interface SkeletonProps {
  variant?: 'text' | 'textShort' | 'card' | 'circle' | 'metric';
  width?: string | number;
  height?: string | number;
  count?: number;
}

export default function Skeleton({ variant = 'text', width, height, count = 1 }: SkeletonProps) {
  const cls = styles[variant] || styles.skeleton;
  const style: React.CSSProperties = {};
  if (width) style.width = typeof width === 'number' ? `${width}px` : width;
  if (height) style.height = typeof height === 'number' ? `${height}px` : height;

  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={cls} style={style} />
      ))}
    </>
  );
}

export function CardSkeleton({ count = 2 }: { count?: number }) {
  return (
    <div className={styles.grid}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={styles.card} />
      ))}
    </div>
  );
}

export function MetricsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className={styles.row}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={styles.metric} style={{ flex: 1 }} />
      ))}
    </div>
  );
}
