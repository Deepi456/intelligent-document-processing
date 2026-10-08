import { Activity, BarChart3, CalendarDays } from "lucide-react";

import { getAnalytics } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { useApiResource } from "../hooks/useApiResource";

export function AnalyticsPage() {
  const analytics = useApiResource(getAnalytics);

  return (
    <>
      <PageHeader eyebrow="System Metrics" title="Analytics" description="Monitor document processing throughput, entity extraction counts, and knowledge graph growth." />
      {analytics.loading ? <LoadingState label="Loading analytics" /> : analytics.error ? <ErrorState error={analytics.error} onRetry={analytics.reload} /> : <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><StatCard label="Documents processed" value={analytics.data.document_count} detail="Processed documents in graph" /><StatCard label="Entities extracted" value={analytics.data.entity_count} detail="Extracted entity mentions" accent="blue" /><StatCard label="Evidence records" value={analytics.data.evidence_count} detail="Captured provenance snippets" /><StatCard label="Relationships found" value={analytics.data.relationship_count} detail="Connected entity relations" accent="amber" /></section>}
      <section className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_0.6fr]">
        <div className="panel p-5 md:p-6"><div className="flex items-center gap-3"><div className="soft-icon"><BarChart3 size={18} /></div><div><p className="eyebrow">Processing Overview</p><h2 className="section-title">Extraction Statistics</h2></div></div><div className="mt-6"><EmptyState title="Real-time graph metrics" description="Metrics are aggregated directly from the active Neo4j knowledge graph and document repository." /></div></div>
        <div className="panel p-5 md:p-6"><div className="flex items-center gap-3"><div className="soft-icon"><Activity size={18} /></div><div><p className="eyebrow">Quality & Provenance</p><h2 className="section-title">Evidence Coverage</h2></div></div><div className="mt-6"><EmptyState title="Provenance status" description="Every extracted entity mention and relationship maintains linked evidence bounding boxes and source page numbers." /></div></div>
      </section>
    </>
  );
}