interface PaginationProps {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export function Pagination({
  page,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between pt-2">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page === 0}
        className="text-xs text-purple bg-transparent border border-border/50 rounded-lg px-3 py-1.5 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed hover:bg-purple/10 transition-colors"
      >
        &larr; Previous
      </button>
      <span className="text-xs text-muted font-mono">
        {page * pageSize + 1}&ndash;
        {Math.min((page + 1) * pageSize, totalItems)} of {totalItems}
      </span>
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={(page + 1) * pageSize >= totalItems}
        className="text-xs text-purple bg-transparent border border-border/50 rounded-lg px-3 py-1.5 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed hover:bg-purple/10 transition-colors"
      >
        Next &rarr;
      </button>
    </div>
  );
}
