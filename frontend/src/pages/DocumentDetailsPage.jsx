import { ArrowLeft, FileText, GitBranch, ScanText } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getDocument, getDocumentEntities, getDocumentEvidence, getDocumentRelationships } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { EvidenceViewer } from "../components/EvidenceViewer";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { useApiResource } from "../hooks/useApiResource";

export function DocumentDetailsPage() {
  const { documentId: encodedDocumentId } = useParams();
  const documentId = decodeURIComponent(encodedDocumentId || "");
  const document = useApiResource(() => getDocument(documentId), [documentId]);
  const entities = useApiResource(() => getDocumentEntities(documentId), [documentId]);
  const relationships = useApiResource(() => getDocumentRelationships(documentId), [documentId]);
  const evidence = useApiResource(() => getDocumentEvidence(documentId), [documentId]);
  const [selection, setSelection] = useState(null);

  if (document.loading) return <LoadingState label="Loading document" />;
  if (document.error) return <ErrorState error={document.error} onRetry={document.reload} />;

  return (
    <>
      <Link to="/documents" className="back-link"><ArrowLeft size={15} /> Back to documents</Link>
      <PageHeader eyebrow="Document detail" title={document.data.filename || document.data.file_name || documentId} description={document.data.source || documentId} />
      <section className="grid gap-4 sm:grid-cols-3">
        <DetailMetric icon={FileText} label="Entities" value={entities.loading ? "…" : entities.error ? "—" : entities.data.length} />
        <DetailMetric icon={GitBranch} label="Relationships" value={relationships.loading ? "…" : relationships.error ? "—" : relationships.data.length} />
        <DetailMetric icon={ScanText} label="Evidence records" value={evidence.loading ? "…" : evidence.error ? "—" : evidence.data.length} />
      </section>
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <DataPanel title="Entities" loading={entities.loading} error={entities.error} onRetry={entities.reload} empty={!entities.data?.length} emptyTitle="No entities found">
          <div className="divide-y divide-[#e8ebe7]">{entities.data?.map((entity) => <button className={`selectable-row ${selection?.kind === "entity" && selection.entity.mention_id === entity.mention_id ? "selectable-row-active" : ""}`} onClick={() => setSelection({ kind: "entity", entity })} key={entity.mention_id}><div><p className="text-left text-sm font-semibold">{entity.canonical_name || entity.name || entity.normalized_text}</p><p className="mt-1 text-left text-xs text-[#7a837c]">{entity.entity_type || "Entity"} · page {entity.page_number ?? "—"}</p></div><span className="text-xs text-[#7a837c]">{entity.confidence == null ? "Not provided" : entity.confidence}</span></button>)}</div>
        </DataPanel>
        <DataPanel title="Relationships" loading={relationships.loading} error={relationships.error} onRetry={relationships.reload} empty={!relationships.data?.length} emptyTitle="No relationships found">
          <div className="space-y-3">{relationships.data?.map((relationship, index) => <button className={`selectable-row selectable-row-card ${selection?.kind === "relationship" && selection.relationship.evidence_id === relationship.evidence_id ? "selectable-row-active" : ""}`} onClick={() => setSelection({ kind: "relationship", relationship })} key={`${relationship.evidence_id}-${index}`}><p className="text-left text-xs font-bold uppercase tracking-[0.12em] text-[#52705a]">{relationship.relationship_type}</p><p className="mt-2 text-left text-sm">{relationship.source_entity?.name || "Unknown"} <span className="px-1 text-[#8a938c]">→</span> {relationship.target_entity?.name || "Unknown"}</p><p className="mt-2 text-left text-xs text-[#7a837c]">Page {relationship.page_number ?? "—"} · Evidence {relationship.evidence_id || "Not provided"}</p></button>)}</div>
        </DataPanel>
        <div className="xl:col-span-2">{evidence.loading ? <DataPanel title="Evidence" loading /> : evidence.error ? <DataPanel title="Evidence" error={evidence.error} onRetry={evidence.reload} /> : evidence.data?.length ? <EvidenceViewer document={document.data} evidence={evidence.data} selection={selection} onClear={() => setSelection(null)} /> : <DataPanel title="Evidence" empty emptyTitle="No evidence found" />}</div>
      </div>
    </>
  );
}

function DetailMetric({ icon: Icon, label, value }) {
  return <div className="panel flex items-center gap-4 p-4"><div className="soft-icon"><Icon size={17} /></div><div><p className="text-xs uppercase tracking-[0.12em] text-[#7a837c]">{label}</p><p className="mt-1 font-display text-xl font-semibold">{value}</p></div></div>;
}

function DataPanel({ title, loading, error, onRetry, empty, emptyTitle, children }) {
  return <div className="panel p-5 md:p-6"><div className="mb-5 flex items-center justify-between"><h2 className="section-title">{title}</h2></div>{loading ? <LoadingState label={`Loading ${title.toLowerCase()}`} /> : error ? <ErrorState error={error} onRetry={onRetry} /> : empty ? <EmptyState title={emptyTitle} /> : children}</div>;
}