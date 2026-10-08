import { Database } from "lucide-react";

export function EmptyState({ title = "No data available yet", description = "This view will populate once the FastAPI data layer is connected." }) {
  return (
    <div className="flex min-h-[230px] flex-col items-center justify-center border border-dashed border-[#cfd6ce] bg-[#fafbf9] px-6 text-center">
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-[#e6ece5] text-[#52705a]"><Database size={19} /></div>
      <h3 className="font-display text-base font-semibold">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-6 text-[#7a837c]">{description}</p>
    </div>
  );
}