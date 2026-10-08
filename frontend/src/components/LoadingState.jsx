export function LoadingState({ label = "Loading data" }) {
  return (
    <div className="flex min-h-[180px] items-center justify-center gap-3 border border-dashed border-[#cfd6ce] bg-[#fafbf9] text-sm text-[#69716a]">
      <span className="loading-spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}