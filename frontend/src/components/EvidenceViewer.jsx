import { BookOpenCheck, FileText, GitBranch } from "lucide-react";

export function EvidenceViewer({ document, evidence, selection, onClear }) {
  const matchedEvidence = selection?.kind === "relationship"
    ? evidence.filter((item) => item.evidence_id === selection.relationship.evidence_id)
    : selection?.kind === "entity"
      ? evidence.filter((item) => matchesEntityEvidence(selection.entity, item))
      : [];

  return (
    <div className="panel overflow-hidden">
      <div className="border-b border-[#dfe3dd] bg-[#f7f9f6] p-5 md:p-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
          <div className="flex items-start gap-3">
            <div className="soft-icon"><BookOpenCheck size={18} /></div>
            <div>
              <p className="eyebrow">Evidence / provenance</p>
              <h2 className="section-title">Knowledge → Evidence → Source</h2>
              <p className="mt-1 text-sm text-[#69716a]">Inspect the source record behind the selected extraction.</p>
            </div>
          </div>
          {selection && <button className="button-secondary" onClick={onClear}>Clear selection</button>}
        </div>
      </div>
      {!selection ? <div className="p-5 md:p-6"><EmptyEvidence message="Select an entity or relationship above to inspect its evidence." /></div> : <div className="grid gap-0 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="border-b border-[#e8ebe7] p-5 md:p-6 lg:border-b-0 lg:border-r">
          <p className="field-label">Selected knowledge</p>
          {selection.kind === "entity" ? <EntitySummary entity={selection.entity} /> : <RelationshipSummary relationship={selection.relationship} />}
        </div>
        <div className="p-5 md:p-6">
          <p className="field-label">Source evidence</p>
          {matchedEvidence.length ? <div className="mt-4 space-y-4">{matchedEvidence.map((item) => <EvidenceRecord key={item.evidence_id} item={item} document={document} />)}</div> : <div className="mt-4"><EmptyEvidence message="No matching evidence was returned for this selection." /></div>}
        </div>
      </div>}
    </div>
  );
}

function EntitySummary({ entity }) {
  return <div className="mt-4 space-y-4"><div className="flex items-start gap-3"><FileText size={17} className="mt-0.5 text-[#52705a]" /><div><p className="text-sm font-semibold">{entity.name || entity.normalized_text || entity.canonical_name || "Unnamed mention"}</p><p className="mt-1 text-xs text-[#7a837c]">{entity.entity_type || "Entity"} · page {optional(entity.page_number)}</p></div></div><DetailLine label="Canonical entity" value={entity.canonical_name || entity.canonical_id} /></div>;
}

function RelationshipSummary({ relationship }) {
  return <div className="mt-4 space-y-4"><div className="flex items-start gap-3"><GitBranch size={17} className="mt-0.5 text-[#52705a]" /><div><p className="text-sm font-semibold">{relationship.source_entity?.name || "Unnamed source"} <span className="px-1 text-[#8a938c]">→</span> {relationship.target_entity?.name || "Unnamed target"}</p><p className="mt-1 text-xs font-bold uppercase tracking-[0.1em] text-[#52705a]">{relationship.relationship_type}</p></div></div><DetailLine label="Evidence ID" value={relationship.evidence_id} /><DetailLine label="Page" value={relationship.page_number} /></div>;
}

function EvidenceRecord({ item, document }) {
  return <article className="evidence-record"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-bold uppercase tracking-[0.12em] text-[#52705a]">Page {optional(item.page)}</p><span className="text-xs text-[#69716a]">Confidence: {optional(item.confidence)}</span></div><p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-[#4e574f]">{item.raw_text || "Raw text not provided"}</p><div className="mt-4 grid gap-3 border-t border-[#e8ebe7] pt-4 sm:grid-cols-2"><DetailLine label="Source document" value={document.filename || document.file_name || document.source} /><DetailLine label="Extraction method" value={item.extraction_method} /><DetailLine label="Bounding box" value={formatValue(item.bbox)} /><DetailLine label="Normalized bbox" value={formatValue(item.normalized_bbox)} /></div><p className="mt-4 text-[11px] text-[#8a938c]">Evidence ID: {item.evidence_id}</p></article>;
}

function DetailLine({ label, value }) {
  return <div><p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#8a938c]">{label}</p><p className="mt-1 break-words text-sm text-[#4e574f]">{optional(value)}</p></div>;
}

function EmptyEvidence({ message }) {
  return <div className="border border-dashed border-[#cfd6ce] bg-[#fafbf9] px-5 py-8 text-center text-sm text-[#7a837c]">{message}</div>;
}

function matchesEntityEvidence(entity, item) {
  if (entity.page_number != null && item.page !== entity.page_number) return false;
  const mention = String(entity.name || entity.normalized_text || entity.canonical_name || "").trim().toLowerCase();
  const rawText = String(item.raw_text || "").trim().toLowerCase();
  return Boolean(mention && rawText && (rawText.includes(mention) || mention.includes(rawText)));
}

function formatValue(value) {
  return value == null ? null : Array.isArray(value) ? value.join(", ") : value;
}

function optional(value) {
  return value == null || value === "" ? "Not provided" : String(value);
}