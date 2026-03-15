interface SkeletonProps {
  w?: string;
  h?: string;
  className?: string;
}

export function Skeleton({
  w,
  h = "h-4",
  className = "",
}: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-elevated rounded ${h} ${w ?? "w-full"} ${className}`}
    />
  );
}
