import { ArrowUpRight, FilePlus2, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getDashboardSummary, getHealth } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { useApiResource } from "../hooks/useApiResource";

export function DashboardPage() {
  const navigate = useNavigate();
  const summary = useApiResource(getDashboardSummary);
  const health = useApiResource(getHealth);

  return (
    <>
      <PageHeader
        eyebrow="System Overview"
        title="Document Intelligence Dashboard"
        description="A clear view of your document intelligence workspace, from intake through connected evidence."
        action={<button className="button-primary" onClick={() => navigate("/documents")}><FilePlus2 size={16} /> Add document</button>}
      />
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Documents processed" value={summary.loading ? "…" : summary.data?.documentCount ?? "—"} detail={summary.error ? "API unavailable" : "From GET /documents"} />
        <StatCard label="Entities extracted" value={summary.loading ? "…" : summary.data?.entityCount ?? "—"} detail={summary.data?.entityCount == null && !summary.loading ? "No entity data available" : "Across loaded documents"} accent="blue" />
        <StatCard label="Evidence records" value={summary.loading ? "…" : summary.data?.evidenceCount ?? "—"} detail={summary.data?.evidenceCount == null && !summary.loading ? "No evidence data available" : "Captured provenance records"} />
        <StatCard label="Relationships found" value={summary.loading ? "…" : summary.data?.relationshipCount ?? "—"} detail={summary.data?.relationshipCount == null && !summary.loading ? "No relationship data available" : "Across loaded documents"} accent="amber" />
      </section>
      <section className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
        <div className="panel p-5 md:p-6">
          <div className="mb-5 flex items-start justify-between">
            <div><p className="eyebrow">Activity</p><h2 className="section-title">Recent documents</h2></div>
              <button className="icon-button" aria-label="Refresh recent documents" onClick={summary.reload}><RefreshCw size={17} /></button>
          </div>
            {summary.loading ? <LoadingState label="Loading recent documents" /> : summary.error ? <ErrorState error={summary.error} onRetry={summary.reload} /> : summary.data.documents.length ? <div className="divide-y divide-[#e8ebe7]">{summary.data.documents.slice(0, 5).map((document) => <div className="flex items-center justify-between gap-4 py-3 first:pt-0" key={document.document_id}><div><p className="truncate text-sm font-semibold">{document.filename || document.file_name || document.document_id}</p><p className="mt-1 text-xs text-[#7a837c]">{document.document_type || "Unknown type"}</p></div><span className="status-badge">Processed</span></div>)}</div> : <EmptyState title="Your document stream is empty" description="The API returned no processed documents." />}
        </div>
        <div className="panel p-5 md:p-6">
          <p className="eyebrow">Workspace health</p>
          <h2 className="section-title">System readiness</h2>
          <div className="mt-6 space-y-5">
              {["FastAPI service", "Neo4j graph", "Extraction pipeline"].map((item) => (
              <div key={item} className="flex items-center justify-between border-b border-[#e8ebe7] pb-4 last:border-0 last:pb-0">
                <span className="text-sm text-[#4e574f]">{item}</span>
                  <span className="flex items-center gap-2 text-xs text-[#8a938c]"><span className={`status-dot ${item === "FastAPI service" ? (health.loading ? "bg-[#d09b45]" : health.error ? "bg-[#a45d42]" : "bg-[#52705a]") : "bg-[#d09b45]"}`} /> {item === "FastAPI service" ? (health.loading ? "Checking" : health.error ? "Unavailable" : "Connected") : "API dependent"}</span>
              </div>
            ))}
          </div>
            <div className="mt-7 flex items-center gap-2 text-xs text-[#52705a]"><ArrowUpRight size={15} /> Health is read from GET /health</div>
        </div>
      </section>
    </>
  );
}