import { CheckCircle2, Filter, Search, Upload, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getDocuments, uploadDocument } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";
import { useApiResource } from "../hooks/useApiResource";

export function DocumentsPage() {
  const documents = useApiResource(getDocuments);
  const [search, setSearch] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadedDocument, setUploadedDocument] = useState(null);
  const filteredDocuments = documents.data?.filter((document) => `${document.filename || ""} ${document.document_id}`.toLowerCase().includes(search.toLowerCase())) || [];

  async function handleUpload(event) {
    event.preventDefault();
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);
    setUploadedDocument(null);
    try {
      const result = await uploadDocument(selectedFile);
      setUploadedDocument(result);
      setSelectedFile(null);
      documents.reload();
    } catch (error) {
      setUploadError(error);
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="Workspace" title="Documents" description="Upload and analyze documents to extract structured knowledge." action={<button className="button-secondary"><Filter size={16} /> Filters</button>} />
      <form className="panel mb-6 p-5 md:p-6" onSubmit={handleUpload}>
        <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
          <div><p className="eyebrow">Document intake</p><h2 className="section-title">Upload and process</h2><p className="mt-1 text-sm text-[#7a837c]">Supported formats: PDF, JPG, JPEG, PNG. Processing runs synchronously through the extraction pipeline.</p></div>
          <label className="button-secondary shrink-0"><Upload size={16} /> Choose file<input className="sr-only" type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(event) => { setSelectedFile(event.target.files?.[0] || null); setUploadError(null); setUploadedDocument(null); }} /></label>
        </div>
        {selectedFile && <div className="mt-5 flex flex-col justify-between gap-3 border border-[#dfe3dd] bg-[#fafbf9] p-3 sm:flex-row sm:items-center"><div className="flex min-w-0 items-center gap-3"><FileBadge /><p className="truncate text-sm font-semibold">{selectedFile.name}</p><button type="button" className="icon-button shrink-0" aria-label="Clear selected file" onClick={() => setSelectedFile(null)}><X size={15} /></button></div><button className="button-primary shrink-0" type="submit" disabled={uploading}>{uploading ? "Processing…" : "Upload and process"}</button></div>}
        {uploading && <p className="mt-4 text-sm text-[#69716a]">Uploading and processing. This may take a moment.</p>}
        {uploadError && <div className="mt-4"><ErrorState error={uploadError} /></div>}
        {uploadedDocument && <div className="mt-4 flex flex-col gap-3 border border-[#c8dacb] bg-[#f1f7f1] p-4 sm:flex-row sm:items-center sm:justify-between"><div className="flex items-start gap-3"><CheckCircle2 size={18} className="mt-0.5 shrink-0 text-[#52705a]" /><div><p className="text-sm font-semibold text-[#385d42]">Document processed successfully</p><p className="mt-1 text-xs text-[#69716a]">{uploadedDocument.pages} page(s) · {uploadedDocument.entities} entities · {uploadedDocument.relationships} relationships</p></div></div><Link className="button-secondary shrink-0" to={`/documents/${encodeURIComponent(uploadedDocument.document_id)}`}>Open document</Link></div>}
      </form>
      <div className="panel p-5 md:p-6">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div><h2 className="section-title">Document registry</h2><p className="mt-1 text-sm text-[#7a837c]">Processed documents from the knowledge graph.</p></div>
          <label className="input-shell"><Search size={16} /><input placeholder="Search documents" aria-label="Search documents" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        </div>
        {documents.loading ? <LoadingState label="Loading documents" /> : documents.error ? <ErrorState error={documents.error} onRetry={documents.reload} /> : filteredDocuments.length ? <div className="overflow-x-auto"><table className="data-table"><thead><tr><th>Document</th><th>Type</th><th>Source</th><th /></tr></thead><tbody>{filteredDocuments.map((document) => <tr key={document.document_id}><td><Link className="font-semibold text-[#385d42] hover:underline" to={`/documents/${encodeURIComponent(document.document_id)}`}>{document.filename || document.file_name || document.document_id}</Link><p className="mt-1 max-w-[360px] truncate text-xs text-[#8a938c]">{document.document_id}</p></td><td>{document.document_type || "—"}</td><td>{document.source || "—"}</td><td className="text-right"><Link className="text-xs font-semibold text-[#52705a] hover:underline" to={`/documents/${encodeURIComponent(document.document_id)}`}>View detail</Link></td></tr>)}</tbody></table></div> : <EmptyState title={search ? "No matching documents" : "No processed documents"} description={search ? "Try a different document name or path." : "The API returned no processed documents."} />}
      </div>
    </>
  );
}

function FileBadge() {
  return <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[#e6ece5] text-[10px] font-bold uppercase text-[#52705a]">File</span>;
}