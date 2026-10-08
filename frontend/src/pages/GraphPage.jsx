import { FileText, Network, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getDocuments, getGraphOverview } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { KnowledgeGraphCanvas } from "../components/KnowledgeGraphCanvas";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";

export function GraphPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const docIdParam = searchParams.get("document_id") || "";

  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [docsError, setDocsError] = useState(null);

  const [selectedDocId, setSelectedDocId] = useState(docIdParam);
  const [graphData, setGraphData] = useState(null);
  const [loadingGraph, setLoadingGraph] = useState(true);
  const [graphError, setGraphError] = useState(null);

  const [selectedEntityId, setSelectedEntityId] = useState("");
  const [search, setSearch] = useState("");

  // Load available documents
  async function loadDocs() {
    setLoadingDocs(true);
    setDocsError(null);
    try {
      const docs = await getDocuments();
      setDocuments(docs || []);
      if (!docIdParam && docs && docs.length > 0) {
        setSelectedDocId(docs[0].document_id);
      }
    } catch (err) {
      setDocsError(err);
    } finally {
      setLoadingDocs(false);
    }
  }

  useEffect(() => {
    loadDocs();
  }, []);

  // Sync if URL search param changes
  useEffect(() => {
    if (docIdParam) {
      setSelectedDocId(docIdParam);
    }
  }, [docIdParam]);

  // Load graph data for selected scope
  async function loadGraph() {
    setLoadingGraph(true);
    setGraphError(null);
    setSelectedEntityId("");
    try {
      const data = await getGraphOverview(selectedDocId || null);
      setGraphData(data);
      if (data?.entities?.length > 0) {
        setSelectedEntityId(data.entities[0].entity_id);
      }
    } catch (err) {
      setGraphError(err);
    } finally {
      setLoadingGraph(false);
    }
  }

  useEffect(() => {
    loadGraph();
  }, [selectedDocId]);

  function handleDocChange(e) {
    const value = e.target.value;
    setSelectedDocId(value);
    if (value) {
      setSearchParams({ document_id: value });
    } else {
      setSearchParams({});
    }
  }

  const selectedDocument = documents.find((d) => d.document_id === selectedDocId);
  const activeEntityId = selectedEntityId || graphData?.entities?.[0]?.entity_id || "";
  const filteredEntities = graphData?.entities?.filter((entity) =>
    `${entity.name || ""} ${entity.entity_id} ${entity.entity_type || ""}`.toLowerCase().includes(search.toLowerCase())
  ) || [];

  return (
    <>
      <PageHeader
        eyebrow={selectedDocument ? "Document Knowledge Graph" : "Global Knowledge Graph"}
        title="Knowledge graph"
        description={
          selectedDocument
            ? `Showing extracted entities and typed relationships for ${selectedDocument.filename || selectedDocument.document_id}.`
            : "Explore canonical entities and typed relationships across all processed documents."
        }
      />

      {/* Control bar: Document selector & Entity Search */}
      <div className="panel mb-5 p-4 md:p-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 items-end">
          <div>
            <label className="field-label" htmlFor="graph-doc-select">
              Filter by Document
            </label>
            <select
              id="graph-doc-select"
              className="select-field mt-1.5"
              value={selectedDocId}
              onChange={handleDocChange}
              disabled={loadingDocs}
            >
              <option value="">All Documents (Global Knowledge Graph)</option>
              {documents.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.filename || doc.file_name || doc.document_id} ({doc.document_type ? doc.document_type.toUpperCase() : "Document"})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="field-label" htmlFor="entity-search">
              Search Entities
            </label>
            <div className="mt-1.5">
              <label className="input-shell">
                <Search size={16} />
                <input
                  id="entity-search"
                  placeholder="Search entity name or type…"
                  aria-label="Search entities"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  disabled={loadingGraph || !graphData?.entities?.length}
                />
              </label>
            </div>
          </div>

          <div>
            <label className="field-label" htmlFor="focus-entity-select">
              Focus Entity
            </label>
            <select
              id="focus-entity-select"
              className="select-field mt-1.5"
              aria-label="Select focus entity"
              value={activeEntityId}
              onChange={(event) => setSelectedEntityId(event.target.value)}
              disabled={loadingGraph || !filteredEntities.length}
            >
              {filteredEntities.length ? (
                filteredEntities.map((entity) => (
                  <option value={entity.entity_id} key={entity.entity_id}>
                    {entity.name || entity.entity_id} ({entity.entity_type || "Entity"})
                  </option>
                ))
              ) : (
                <option value="">No entities matching</option>
              )}
            </select>
          </div>
        </div>

        {selectedDocument && (
          <div className="mt-3 flex items-center gap-2 border-t border-[#f0f2ef] pt-3 text-xs text-[#69716a]">
            <FileText size={14} className="text-[#52705a]" />
            <span className="font-semibold text-[#202521]">Active Scope:</span>
            <span className="truncate">{selectedDocument.filename || selectedDocument.document_id}</span>
            <span className="text-[#8a938c]">·</span>
            <span>{graphData?.entities?.length || 0} entities</span>
            <span className="text-[#8a938c]">·</span>
            <span>{graphData?.relationships?.length || 0} relationships</span>
          </div>
        )}
      </div>

      <div className="panel overflow-hidden p-3 md:p-4">
        <div className="min-h-[640px] border border-[#e2e7e1] bg-[#f7f9f6]">
          {loadingDocs || loadingGraph ? (
            <LoadingState label={loadingDocs ? "Loading documents…" : "Loading knowledge graph…"} />
          ) : docsError ? (
            <ErrorState error={docsError} onRetry={loadDocs} />
          ) : graphError ? (
            <ErrorState error={graphError} onRetry={loadGraph} />
          ) : !graphData?.entities?.length && !graphData?.relationships?.length ? (
            <EmptyState
              title={selectedDocument ? "No graph data for this document" : "No graph entities available"}
              description={
                selectedDocument
                  ? "No entities or relationships were extracted from this document."
                  : "The knowledge graph is currently empty. Please process a document first."
              }
            />
          ) : (
            <KnowledgeGraphCanvas
              data={graphData}
              selectedEntityId={activeEntityId}
              onNodeSelect={setSelectedEntityId}
              documentContext={selectedDocument}
            />
          )}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between text-xs text-[#7a837c]">
        <div className="flex items-center gap-2">
          <Network size={15} className="text-[#52705a]" />
          <span>Interactive Knowledge Graph: Click any node or relationship to view detailed evidence and provenance.</span>
        </div>
      </div>
    </>
  );
}