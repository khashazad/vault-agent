interface ErrorAlertProps {
  message: string;
}

export function ErrorAlert({ message }: ErrorAlertProps) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="bg-red-bg border border-red rounded py-3 px-4 mb-4 text-[13px]"
    >
      <strong>Error:</strong> {message}
    </div>
  );
}
