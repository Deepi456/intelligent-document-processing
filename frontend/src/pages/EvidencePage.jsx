import { BookOpenCheck, ScanSearch } from "lucide-react";
import { useState } from "react";

import { getDocumentEvidence, getDocuments } from "../api/client";
import { formatConfidence } from "../utils/confidence";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { useApiResource } from "../hooks/useApiResource";

export function EvidencePage() {
  const documents = useApiResource(getDocuments);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const selectedDocument = selectedDocumentId || documents.data?.[0]?.document_id || "";
  const evidence = useApiResource(() => selectedDocument ? getDocumentEvidence(selectedDocument) : Promise.resolve([]), [selectedDocument]);

  return (
    <>
      <PageHeader eyebrow="Audit trail" title="Evidence & provenance" description="Trace extracted claims back to the page, text, bounding box, and method that produced them." action={<button className="button-secondary"><ScanSearch size={16} /> Inspect evidence</button>} />
      <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
        <div className="panel p-5 md:p-6"><p className="eyebrow">Evidence index</p><h2 className="section-title">Source records</h2>{documents.loading ? <div className="mt-5"><LoadingState label="Loading documents" /></div> : documents.error ? <div className="mt-5"><ErrorState error={documents.error} onRetry={documents.reload} /></div> : documents.data.length ? <div className="mt-5"><label className="field-label" htmlFor="evidence-document">Document</label><select id="evidence-document" className="select-field" value={selectedDocument} onChange={(event) => setSelectedDocumentId(event.target.value)}>{documents.data.map((document) => <option value={document.document_id} key={document.document_id}>{document.filename || document.file_name || document.document_id}</option>)}</select></div> : <div className="mt-5"><EmptyState title="No documents available" description="The API returned no documents to inspect." /></div>}</div>
        <div className="panel p-5 md:p-6"><div className="flex items-center gap-3"><div className="soft-icon"><BookOpenCheck size={18} /></div><div><p className="eyebrow">Provenance detail</p><h2 className="section-title">Inspection panel</h2></div></div><div className="mt-5">{!selectedDocument ? <EmptyState title="Waiting for a document" description="Select a document after the API returns available records." /> : evidence.loading ? <LoadingState label="Loading evidence" /> : evidence.error ? <ErrorState error={evidence.error} onRetry={evidence.reload} /> : evidence.data.length ? <div className="space-y-3">{evidence.data.map((item) => <div className="border border-[#e8ebe7] p-4" key={item.evidence_id}><div className="flex justify-between gap-3"><p className="text-xs font-bold uppercase tracking-[0.12em] text-[#52705a]">Page {item.page ?? "—"}</p><span className="text-xs text-[#7a837c]">{item.confidence == null ? "—" : `${formatConfidence(item.confidence)} confidence`}</span></div><p className="mt-3 text-sm leading-6 text-[#4e574f]">{item.raw_text || "No raw text available"}</p><p className="mt-3 text-xs text-[#7a837c]">{item.extraction_method || "Unknown method"}</p></div>)}</div> : <EmptyState title="No evidence found" description="The API returned no evidence for this document." />}</div></div>
      </div>
    </>
  );
}