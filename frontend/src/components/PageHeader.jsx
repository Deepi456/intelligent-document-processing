export function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-end">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="page-title">{title}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[#69716a]">{description}</p>
      </div>
      {action}
    </div>
  );
}