export function StatCard({ label, value = "—", detail, accent = "green" }) {
  return (
    <div className="panel relative overflow-hidden p-5">
      <div className={`absolute left-0 top-0 h-full w-1 ${accent === "amber" ? "bg-[#d09b45]" : accent === "blue" ? "bg-[#55798a]" : "bg-[#52705a]"}`} />
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[#7a837c]">{label}</p>
      <p className="mt-4 font-display text-3xl font-semibold tracking-tight text-[#202521]">{value}</p>
      <p className="mt-2 text-xs text-[#8a938c]">{detail}</p>
    </div>
  );
}