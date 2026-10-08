import { FileText, MessageSquareText, Send, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { askQuestion, getDocuments } from "../api/client";
import { formatConfidence } from "../utils/confidence";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";
import { PageHeader } from "../components/PageHeader";

const EXAMPLE_QUESTIONS = [
  "What entities are mentioned in this document?",
  "Which people are mentioned?",
  "Which locations are mentioned?",
  "What relationships are present?",
  "Where is X mentioned?",
  "How many entities are present?",
];

export function QueryPage() {
  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [docsError, setDocsError] = useState(null);
  const [selectedDocId, setSelectedDocId] = useState("");

  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function loadDocuments() {
    setLoadingDocs(true);
    setDocsError(null);
    try {
      const docs = await getDocuments();
      setDocuments(docs || []);
      if (docs && docs.length > 0 && !selectedDocId) {
        setSelectedDocId(docs[0].document_id);
      }
    } catch (err) {
      setDocsError(err);
    } finally {
      setLoadingDocs(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  async function submit(event) {
    if (event) event.preventDefault();
    if (!question.trim() || !selectedDocId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await askQuestion(question.trim(), selectedDocId);
      setResult(response);
    } catch (requestError) {
      setError(requestError);
    } finally {
      setLoading(false);
    }
  }

  const selectedDocument = documents.find((d) => d.document_id === selectedDocId);

  return (
    <>
      <PageHeader
        eyebrow="Document-Scoped Retrieval"
        title="Ask your document"
        description="Select a processed document to query its isolated knowledge graph. Answers are strictly grounded in the document's extracted entities, relationships, and evidence."
      />

      {loadingDocs ? (
        <div className="panel p-6 mt-4">
          <LoadingState label="Loading processed documents…" />
        </div>
      ) : docsError ? (
        <div className="panel p-6 mt-4">
          <ErrorState error={docsError} onRetry={loadDocuments} />
        </div>
      ) : documents.length === 0 ? (
        <div className="panel p-6 mt-4">
          <EmptyState
            title="No documents available"
            description="Please upload and process a document on the Documents page before asking questions."
          />
        </div>
      ) : (
        <>
          <form className="panel p-5 md:p-6" onSubmit={submit}>
            <div className="mb-4">
              <label className="field-label" htmlFor="document-select">
                Target Document
              </label>
              <div className="mt-1.5 flex items-center gap-2">
                <div className="relative flex-1">
                  <select
                    id="document-select"
                    className="select-field"
                    value={selectedDocId}
                    onChange={(e) => {
                      setSelectedDocId(e.target.value);
                      setResult(null);
                      setError(null);
                    }}
                  >
                    {documents.map((doc) => (
                      <option key={doc.document_id} value={doc.document_id}>
                        {doc.filename || doc.file_name || doc.document_id} ({doc.document_type ? doc.document_type.toUpperCase() : "Document"})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {selectedDocument && (
                <div className="mt-2 flex items-center gap-2 text-xs text-[#69716a]">
                  <FileText size={14} className="text-[#52705a]" />
                  <span className="font-medium text-[#202521]">Selected:</span>
                  <span className="truncate max-w-md">{selectedDocument.filename || selectedDocument.document_id}</span>
                </div>
              )}
            </div>

            <label className="field-label" htmlFor="question">
              Question
            </label>
            <div className="mt-2 flex flex-col gap-3 sm:flex-row">
              <label className="input-shell flex-1">
                <MessageSquareText size={17} />
                <input
                  id="question"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Ask a question about the selected document…"
                />
              </label>
              <button
                className="button-primary shrink-0"
                disabled={loading || !question.trim() || !selectedDocId}
                type="submit"
              >
                <Send size={16} />
                {loading ? "Searching…" : "Ask"}
              </button>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-[#7a837c] flex items-center gap-1">
                <Sparkles size={13} className="text-[#52705a]" /> Suggested:
              </span>
              {EXAMPLE_QUESTIONS.map((example, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setQuestion(example)}
                  className="rounded-full border border-[#cfd6ce] bg-[#f8faf7] px-3 py-1 text-xs text-[#52705a] hover:border-[#91aa95] hover:bg-[#edf4ed] transition-colors"
                >
                  {example}
                </button>
              ))}
            </div>
          </form>

          <section className="panel mt-6 p-5 md:p-6">
            <div className="flex items-center justify-between border-b border-[#e8ebe7] pb-4">
              <div className="flex items-center gap-3">
                <div className="soft-icon">
                  <ShieldCheck size={18} />
                </div>
                <div>
                  <p className="eyebrow">Document-Grounded Result</p>
                  <h2 className="section-title">Answer and Evidence Provenance</h2>
                </div>
              </div>
              {selectedDocument && result && (
                <span className="status-badge hidden sm:inline-flex items-center gap-1">
                  <FileText size={12} /> {selectedDocument.filename || "Document"}
                </span>
              )}
            </div>

            <div className="mt-5">
              {error ? (
                <ErrorState error={error} />
              ) : !result ? (
                <EmptyState
                  title="Ask a question to begin"
                  description="Questions are answered deterministically using the selected document's knowledge graph and extracted evidence."
                />
              ) : (
                <>
                  <div className="rounded border border-[#d6e3d7] bg-[#f4f8f4] p-4 text-[#243a29]">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#52705a]">Answer</p>
                    <p className="mt-1.5 text-base font-medium leading-7 text-[#202521]">{result.answer}</p>
                  </div>

                  {result.matched_entities?.length > 0 && (
                    <div className="mt-6">
                      <p className="field-label">Matched Entities ({result.matched_entities.length})</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {result.matched_entities.map((entity, index) => (
                          <span className="status-badge" key={`${entity.entity_id}-${index}`}>
                            {entity.name || entity.entity_id} · {entity.entity_type || "Entity"}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {result.matched_relationships?.length > 0 && (
                    <div className="mt-6">
                      <p className="field-label">Matched Relationships ({result.matched_relationships.length})</p>
                      <div className="mt-2 space-y-2">
                        {result.matched_relationships.map((relationship, index) => (
                          <div className="border border-[#e8ebe7] bg-[#fff] p-3.5" key={`${relationship.evidence_id}-${index}`}>
                            <div className="flex items-center justify-between">
                              <p className="text-xs font-bold uppercase tracking-[0.1em] text-[#52705a]">
                                {relationship.relationship_type}
                              </p>
                              <span className="text-xs text-[#7a837c]">
                                {relationship.confidence != null
                                  ? `${formatConfidence(relationship.confidence)} confidence`
                                  : "Confidence —"}
                              </span>
                            </div>
                            <p className="mt-1 text-sm font-medium text-[#202521]">
                              {relationship.source_entity?.name || "Source"}{" "}
                              <span className="px-1.5 text-[#8a938c]">→</span>{" "}
                              {relationship.target_entity?.name || "Target"}
                            </p>
                            {relationship.evidence_id && (
                              <p className="mt-1 text-xs text-[#7a837c]">
                                Evidence ID: <code className="text-[#52705a]">{relationship.evidence_id}</code>
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="mt-6">
                    <p className="field-label">
                      Supporting Evidence ({result.evidence?.length || 0})
                    </p>
                    {result.evidence?.length > 0 ? (
                      <div className="mt-3 space-y-3">
                        {result.evidence.map((item, index) => (
                          <article className="evidence-record" key={`${item.evidence_id}-${index}`}>
                            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#f0f2ef] pb-2">
                              <div className="flex items-center gap-1.5">
                                <FileText size={14} className="text-[#52705a]" />
                                <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#52705a]">
                                  {item.filename || item.document_id}
                                </p>
                              </div>
                              <span className="status-badge text-xs">
                                Page {item.page ?? "—"}
                              </span>
                            </div>
                            <p className="mt-3 text-sm leading-6 text-[#4e574f] font-mono bg-[#fafbf9] p-2.5 border border-[#edf0ed]">
                              "{item.raw_text || "Relationship evidence"}"
                            </p>
                            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-[#7a837c]">
                              <span>
                                Method: <strong className="text-[#4e574f]">{item.extraction_method || "Unknown"}</strong>
                              </span>
                              <span>
                                {item.confidence == null
                                  ? "Confidence not provided"
                                  : `${formatConfidence(item.confidence)} confidence`}
                              </span>
                              <span>
                                Evidence ID: <code className="text-[#52705a]">{item.evidence_id}</code>
                              </span>
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-sm text-[#7a837c]">
                        No supporting evidence records found for this query in the selected document.
                      </p>
                    )}
                  </div>
                </>
              )}
            </div>
          </section>
        </>
      )}
    </>
  );
}

