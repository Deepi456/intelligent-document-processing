import { CircleAlert, RefreshCw } from "lucide-react";

export function ErrorState({ error, onRetry }) {
  return (
    <div className="flex min-h-[180px] flex-col items-center justify-center border border-dashed border-[#dfc7ba] bg-[#fffaf7] px-6 text-center">
      <CircleAlert size={20} className="text-[#a45d42]" />
      <h3 className="mt-3 font-display text-base font-semibold">Unable to load this data</h3>
      <p className="mt-2 max-w-md text-sm leading-6 text-[#8a6e62]">{error?.message || "The API is unavailable right now."}</p>
      {onRetry && <button className="button-secondary mt-4" onClick={onRetry}><RefreshCw size={15} /> Try again</button>}
    </div>
  );
}