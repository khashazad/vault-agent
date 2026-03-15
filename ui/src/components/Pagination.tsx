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
        className="text-xs text-accent bg-transparent border border-border rounded px-3 py-1 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
      >
        &larr; Previous
      </button>
      <span className="text-xs text-muted">
        {page * pageSize + 1}&ndash;
        {Math.min((page + 1) * pageSize, totalItems)} of {totalItems}
      </span>
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={(page + 1) * pageSize >= totalItems}
        className="text-xs text-accent bg-transparent border border-border rounded px-3 py-1 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Next &rarr;
      </button>
    </div>
  );
}
