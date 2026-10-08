import { useEffect, useState } from "react";
import { Background, Controls, Handle, MiniMap, Position, ReactFlow } from "@xyflow/react";
import { FileText, GitBranch, ShieldCheck, Tag, Info, ArrowRight } from "lucide-react";
import { formatConfidence } from "../utils/confidence";
import "@xyflow/react/dist/style.css";

const ENTITY_TYPE_THEMES = {
  Person: { bg: "#eef4ff", text: "#2563eb", border: "#bfdbfe" },
  Organization: { bg: "#f0fdf4", text: "#16a34a", border: "#bbf7d0" },
  Location: { bg: "#faf5ff", text: "#9333ea", border: "#e9d5ff" },
  Product: { bg: "#fff7ed", text: "#ea580c", border: "#ffedd5" },
  Date: { bg: "#ecfeff", text: "#0891b2", border: "#cffafe" },
  Amount: { bg: "#f0fdfa", text: "#0d9488", border: "#ccfbf1" },
  Event: { bg: "#fdf2f8", text: "#db2777", border: "#fce7f3" },
  Concept: { bg: "#f8fafc", text: "#475569", border: "#e2e8f0" },
  Thing: { bg: "#f9fafb", text: "#4b5563", border: "#e5e7eb" },
  Facility: { bg: "#fefce8", text: "#ca8a04", border: "#fef08a" },
};

function getEntityTypeTheme(type = "Entity") {
  return ENTITY_TYPE_THEMES[type] || { bg: "#f1f5f9", text: "#475569", border: "#cbd5e1" };
}

function EntityNode({ data }) {
  const theme = getEntityTypeTheme(data.entityType);
  return (
    <div
      className={`graph-node transition-all ${data.selected ? "graph-node-selected ring-2 ring-[#52705a]" : ""}`}
      style={{
        borderColor: data.selected ? "#52705a" : theme.border,
      }}
    >
      <Handle type="target" position={Position.Top} className="!border-0 !bg-transparent" />
      <div className="flex items-center justify-between gap-1">
        <span
          className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
          style={{ backgroundColor: theme.bg, color: theme.text }}
        >
          {data.entityType || "Entity"}
        </span>
        {data.pageNumber != null && (
          <span className="text-[9px] text-[#7a837c]">p.{data.pageNumber}</span>
        )}
      </div>
      <p className="graph-node-name text-xs font-bold text-[#202521] mt-1.5 truncate" title={data.label}>
        {data.label}
      </p>
      <Handle type="source" position={Position.Bottom} className="!border-0 !bg-transparent" />
    </div>
  );
}

const nodeTypes = { entity: EntityNode };

function graphDataToFlow(data, selectedEntityId, selectedNodeId, onSelectNode) {
  const entityById = new Map();
  const addEntity = (entity) => {
    if (entity?.entity_id && !entityById.has(entity.entity_id)) {
      entityById.set(entity.entity_id, entity);
    }
  };

  data.entities?.forEach(addEntity);
  if (data.entity) addEntity(data.entity);
  (data.relationships || []).forEach((relationship) => {
    addEntity(relationship.source_entity);
    addEntity(relationship.target_entity);
  });

  const entities = [...entityById.values()];
  const centerIndex = entities.findIndex((entity) => entity.entity_id === selectedEntityId);
  const centerEntity = entities[centerIndex] || entities[0] || data.entity || { entity_id: "root", name: "Document" };
  const connected = entities.filter((e) => e.entity_id !== centerEntity.entity_id);

  const radiusX = Math.min(360, Math.max(220, connected.length * 35));
  const radiusY = Math.min(240, Math.max(160, connected.length * 25));

  const nodes = [
    {
      id: centerEntity.entity_id,
      type: "entity",
      position: { x: 420, y: 240 },
      data: {
        label: centerEntity.name || centerEntity.entity_id,
        entityType: centerEntity.entity_type,
        pageNumber: centerEntity.page_number,
        selected: selectedNodeId === centerEntity.entity_id,
        onSelect: onSelectNode,
      },
    },
    ...connected.map((entity, index) => {
      const angle = (index / Math.max(connected.length, 1)) * Math.PI * 2 - Math.PI / 2;
      return {
        id: entity.entity_id,
        type: "entity",
        position: { x: 420 + Math.cos(angle) * radiusX, y: 240 + Math.sin(angle) * radiusY },
        data: {
          label: entity.name || entity.entity_id,
          entityType: entity.entity_type,
          pageNumber: entity.page_number,
          selected: selectedNodeId === entity.entity_id,
          onSelect: onSelectNode,
        },
      };
    }),
  ];

  const edges = (data.relationships || []).map((relationship, index) => {
    const isConnected =
      selectedNodeId === relationship.source_entity?.entity_id ||
      selectedNodeId === relationship.target_entity?.entity_id;
    const relLabel = relationship.relationship_type || "RELATED_TO";
    const confLabel = relationship.confidence != null ? ` · ${formatConfidence(relationship.confidence)}` : "";

    return {
      id: `${relationship.evidence_id || relLabel}-${index}`,
      source: relationship.source_entity?.entity_id,
      target: relationship.target_entity?.entity_id,
      label: `${relLabel}${confLabel}`,
      type: "smoothstep",
      animated: isConnected,
      data: { relationship },
      style: {
        stroke: isConnected ? "#3f5c47" : "#8a9e8e",
        strokeWidth: isConnected ? 2 : 1.25,
      },
      labelStyle: { fill: "#243a29", fontSize: 10, fontWeight: 700 },
      labelBgStyle: { fill: "#ffffff", fillOpacity: 0.95, stroke: "#dfe3dd", strokeWidth: 1 },
      labelBgPadding: [6, 3],
      labelBgBorderRadius: 3,
    };
  }).filter((edge) => edge.source && edge.target);

  return { nodes, edges };
}

export function KnowledgeGraphCanvas({ data, selectedEntityId, onNodeSelect, documentContext }) {
  const [selectedNodeId, setSelectedNodeId] = useState(selectedEntityId);
  const [selectedRelationship, setSelectedRelationship] = useState(null);

  useEffect(() => {
    setSelectedNodeId(selectedEntityId);
  }, [selectedEntityId]);

  const flow = graphDataToFlow(data, selectedEntityId, selectedNodeId, (entityId) => {
    setSelectedNodeId(entityId);
    setSelectedRelationship(null);
    onNodeSelect(entityId);
  });

  return (
    <div className="graph-layout">
      <div className="graph-canvas" aria-label="Interactive knowledge graph">
        <ReactFlow
          nodes={flow.nodes}
          edges={flow.edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.22 }}
          minZoom={0.3}
          maxZoom={1.6}
          nodesDraggable
          nodesConnectable={false}
          onNodeClick={(_, node) => {
            setSelectedNodeId(node.id);
            setSelectedRelationship(null);
            onNodeSelect(node.id);
          }}
          onEdgeClick={(_, edge) => {
            if (edge.data?.relationship) {
              setSelectedRelationship(edge.data.relationship);
            }
          }}
        >
          <Background color="#d7dfd6" gap={24} size={1} />
          <Controls showInteractive={false} />
          <MiniMap nodeColor="#9bb19e" maskColor="rgb(247 249 246 / 70%)" />
        </ReactFlow>
      </div>

      <GraphDetails
        data={data}
        selectedNodeId={selectedNodeId}
        selectedRelationship={selectedRelationship}
        onSelectEntity={(id) => {
          setSelectedNodeId(id);
          setSelectedRelationship(null);
          onNodeSelect(id);
        }}
        onSelectRelationship={(rel) => {
          setSelectedRelationship(rel);
        }}
        onClearRelationship={() => setSelectedRelationship(null)}
        documentContext={documentContext}
      />
    </div>
  );
}

function GraphDetails({
  data,
  selectedNodeId,
  selectedRelationship,
  onSelectEntity,
  onSelectRelationship,
  onClearRelationship,
  documentContext,
}) {
  const allEntities = [
    ...(data.entities || []),
    data.entity,
    ...(data.relationships || []).flatMap((rel) => [rel.source_entity, rel.target_entity]),
  ].filter(Boolean);

  const entity =
    allEntities.find((candidate) => candidate.entity_id === selectedNodeId) ||
    data.entities?.[0] ||
    data.entity ||
    { entity_id: "none", name: "No entity selected" };

  const connectedRelationships = (data.relationships || []).filter(
    (relationship) =>
      relationship.source_entity?.entity_id === entity.entity_id ||
      relationship.target_entity?.entity_id === entity.entity_id
  );

  const theme = getEntityTypeTheme(entity.entity_type);
  const docName = documentContext?.filename || entity.document_id || data.document_id || "Document";

  return (
    <aside className="graph-details overflow-y-auto max-h-[640px]">
      {selectedRelationship ? (
        <div>
          <div className="flex items-center justify-between">
            <p className="eyebrow text-[#52705a]">Selected Relationship</p>
            <button
              className="text-xs text-[#52705a] hover:underline"
              onClick={onClearRelationship}
            >
              Back to Entity
            </button>
          </div>

          <h2 className="section-title text-[#202521] mt-1">
            {selectedRelationship.relationship_type || "Relationship"}
          </h2>

          <div className="mt-3 rounded border border-[#e8ebe7] bg-[#fafbf9] p-3 text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[#7a837c]">Source Entity:</span>
              <button
                className="font-semibold text-[#52705a] hover:underline"
                onClick={() => onSelectEntity(selectedRelationship.source_entity?.entity_id)}
              >
                {selectedRelationship.source_entity?.name || "Source"}
              </button>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[#7a837c]">Target Entity:</span>
              <button
                className="font-semibold text-[#52705a] hover:underline"
                onClick={() => onSelectEntity(selectedRelationship.target_entity?.entity_id)}
              >
                {selectedRelationship.target_entity?.name || "Target"}
              </button>
            </div>
            {selectedRelationship.page_number != null && (
              <div className="flex items-center justify-between">
                <span className="text-[#7a837c]">Page Number:</span>
                <span className="font-medium text-[#202521]">Page {selectedRelationship.page_number}</span>
              </div>
            )}
            {selectedRelationship.confidence != null && (
              <div className="flex items-center justify-between">
                <span className="text-[#7a837c]">Confidence:</span>
                <span className="font-medium text-[#202521]">{formatConfidence(selectedRelationship.confidence)}</span>
              </div>
            )}
            {selectedRelationship.extraction_method && (
              <div className="flex items-center justify-between">
                <span className="text-[#7a837c]">Method:</span>
                <span className="font-medium text-[#202521]">{selectedRelationship.extraction_method}</span>
              </div>
            )}
            {selectedRelationship.evidence_id && (
              <div className="flex items-center justify-between">
                <span className="text-[#7a837c]">Evidence ID:</span>
                <code className="text-[#52705a] text-[10px]">{selectedRelationship.evidence_id}</code>
              </div>
            )}
          </div>

          {selectedRelationship.raw_text && (
            <div className="mt-4">
              <p className="field-label text-[10px]">Supporting Evidence</p>
              <p className="mt-1.5 rounded border border-[#edf0ed] bg-[#fafbf9] p-2.5 text-xs italic text-[#4e574f]">
                "{selectedRelationship.raw_text}"
              </p>
            </div>
          )}
        </div>
      ) : (
        <div>
          <p className="eyebrow">Selected Entity</p>
          <h2 className="section-title text-[#202521] break-words">{entity.name || entity.entity_id}</h2>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <span
              className="rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
              style={{ backgroundColor: theme.bg, color: theme.text }}
            >
              {entity.entity_type || "Entity"}
            </span>
            {entity.page_number != null && (
              <span className="status-badge text-[10px]">Page {entity.page_number}</span>
            )}
            {entity.confidence != null && (
              <span className="status-badge text-[10px]">{formatConfidence(entity.confidence)} conf</span>
            )}
          </div>

          {/* Entity Provenance Card */}
          <div className="mt-4 rounded border border-[#e8ebe7] bg-[#fafbf9] p-3 text-xs space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[#7a837c]">Document:</span>
              <span className="font-medium text-[#202521] truncate max-w-[150px]" title={docName}>{docName}</span>
            </div>
            {entity.extraction_method && (
              <div className="flex items-center justify-between">
                <span className="text-[#7a837c]">Method:</span>
                <span className="font-medium text-[#202521]">{entity.extraction_method}</span>
              </div>
            )}
            {entity.evidence_id && (
              <div className="flex items-center justify-between">
                <span className="text-[#7a837c]">Evidence ID:</span>
                <code className="text-[#52705a] text-[10px] truncate max-w-[140px]">{entity.evidence_id}</code>
              </div>
            )}
          </div>

          {entity.raw_text && entity.raw_text !== entity.name && (
            <div className="mt-3">
              <p className="field-label text-[10px]">Evidence Snippet</p>
              <p className="mt-1 rounded border border-[#edf0ed] bg-[#fafbf9] p-2 text-xs italic text-[#4e574f]">
                "{entity.raw_text}"
              </p>
            </div>
          )}

          {/* Connected Relationships Section */}
          <div className="mt-5 border-t border-[#e8ebe7] pt-4">
            <p className="field-label">
              Connected Relationships ({connectedRelationships.length})
            </p>
            {connectedRelationships.length ? (
              <div className="mt-3 space-y-2.5">
                {connectedRelationships.map((relationship, index) => {
                  const isSource = relationship.source_entity?.entity_id === entity.entity_id;
                  const otherEntity = isSource ? relationship.target_entity : relationship.source_entity;
                  const otherId = otherEntity?.entity_id;

                  return (
                    <div
                      className="border border-[#e8ebe7] bg-[#fff] p-2.5 text-xs hover:border-[#52705a] cursor-pointer transition-colors"
                      key={`${relationship.evidence_id || relationship.relationship_type}-${index}`}
                      onClick={() => onSelectRelationship(relationship)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold uppercase text-[10px] tracking-wider text-[#52705a]">
                          {relationship.relationship_type}
                        </span>
                        <span className="text-[10px] text-[#7a837c]">
                          {relationship.confidence != null ? `${formatConfidence(relationship.confidence)}` : ""}
                        </span>
                      </div>

                      <div className="mt-1 flex items-center gap-1 font-medium text-[#202521]">
                        <span>{isSource ? entity.name : otherEntity?.name || "Unknown"}</span>
                        <ArrowRight size={11} className="text-[#8a938c]" />
                        <span>{isSource ? otherEntity?.name || "Unknown" : entity.name}</span>
                      </div>

                      {relationship.raw_text && (
                        <p className="mt-1.5 truncate text-[11px] italic text-[#69716a]">
                          "{relationship.raw_text}"
                        </p>
                      )}

                      <div className="mt-1.5 flex items-center justify-between text-[10px] text-[#7a837c]">
                        <span>Page {relationship.page_number ?? "—"}</span>
                        {otherId && (
                          <button
                            type="button"
                            className="text-[#52705a] hover:underline"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectEntity(otherId);
                            }}
                          >
                            Jump to node →
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="mt-2 text-xs text-[#7a837c]">No connected relationships found for this entity.</p>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
