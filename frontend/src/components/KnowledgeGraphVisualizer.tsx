import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';

export interface GraphNodeData {
  id: string;
  label: string;
  type: 'Document' | 'Chunk' | 'Entity' | 'Topic' | string;
  properties: Record<string, any>;
}

export interface GraphEdgeData {
  source: string;
  target: string;
  relation: string;
  properties?: Record<string, any>;
}

interface KnowledgeGraphVisualizerProps {
  docId: string | null;
  nodes: GraphNodeData[];
  edges: GraphEdgeData[];
  isLoading?: boolean;
  onSelectEntity?: (name: string) => void;
  selectedEntityName?: string | null;
  height?: number;
}

interface SimNode extends GraphNodeData {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  textColor: string;
  pinned: boolean;
}

interface SimEdge {
  source: SimNode;
  target: SimNode;
  relation: string;
  properties?: Record<string, any>;
}

const TYPE_CONFIG: Record<string, { color: string; textColor: string; radius: number; label: string }> = {
  Document: { color: '#30302E', textColor: '#FFFFFF', radius: 24, label: 'Document' },
  Topic: { color: '#D97706', textColor: '#FFFFFF', radius: 17, label: 'Topic' },
  Entity: { color: '#15803D', textColor: '#FFFFFF', radius: 15, label: 'Entity' },
  Chunk: { color: '#475569', textColor: '#FFFFFF', radius: 14, label: 'Chunk' },
  Default: { color: '#6B7280', textColor: '#FFFFFF', radius: 13, label: 'Node' },
};

export const KnowledgeGraphVisualizer: React.FC<KnowledgeGraphVisualizerProps> = ({
  docId,
  nodes,
  edges,
  isLoading = false,
  onSelectEntity,
  selectedEntityName,
  height = 540,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Filter toggles
  const [showDocument, setShowDocument] = useState(true);
  const [showTopics, setShowTopics] = useState(true);
  const [showEntities, setShowEntities] = useState(true);
  const [showChunks, setShowChunks] = useState(true);
  const [showEdgeLabels, setShowEdgeLabels] = useState(true);
  const [searchFilter, setSearchFilter] = useState('');

  // Selection & Inspector
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const hoveredNodeIdRef = useRef<string | null>(null);

  // FalkorDB 2-hop query state
  const [twoHopData, setTwoHopData] = useState<{
    entity_name: string;
    entity_type: string;
    connected_entities: Array<{ name: string; type: string }>;
    referenced_chunks: string[];
    direct_relations: Array<{ target?: string; source?: string; relation: string }>;
  } | null>(null);
  const [isLoadingTwoHop, setIsLoadingTwoHop] = useState(false);

  // Transform state (Zoom & Pan)
  const transformRef = useRef({ x: 0, y: 0, k: 1 });
  const [zoomLevel, setZoomLevel] = useState(1);

  // Simulation state refs (so animation frame reads mutable data directly)
  const simNodesRef = useRef<Map<string, SimNode>>(new Map());
  const simEdgesRef = useRef<SimEdge[]>([]);
  const animFrameRef = useRef<number | null>(null);
  const isDraggingRef = useRef(false);
  const draggedNodeRef = useRef<SimNode | null>(null);
  const lastMousePosRef = useRef({ x: 0, y: 0 });
  const isPanningRef = useRef(false);
  const isSimulatingRef = useRef(false);
  const textWidthCache = useRef<Map<string, number>>(new Map());

  // Counts for pills
  const counts = useMemo(() => {
    let doc = 0;
    let topic = 0;
    let entity = 0;
    let chunk = 0;
    nodes.forEach((n) => {
      if (n.type === 'Document') doc++;
      else if (n.type === 'Topic') topic++;
      else if (n.type === 'Entity') entity++;
      else if (n.type === 'Chunk') chunk++;
    });
    return { doc, topic, entity, chunk };
  }, [nodes]);

  // Synchronize when selectedEntityName prop changes from outside
  useEffect(() => {
    if (selectedEntityName) {
      const match = nodes.find(
        (n) => n.type === 'Entity' && n.label.toLowerCase() === selectedEntityName.toLowerCase()
      );
      if (match) {
        setSelectedNodeId(match.id);
      }
    }
  }, [selectedEntityName, nodes]);

  // Re-initialize nodes and edges whenever nodes or edges props change
  useEffect(() => {
    const nodeMap = new Map<string, SimNode>();
    const width = containerRef.current ? containerRef.current.clientWidth : 800;
    const canvasHeight = height;

    // Filter nodes based on checkboxes
    const allowedNodes = nodes.filter((n) => {
      if (n.type === 'Document' && !showDocument) return false;
      if (n.type === 'Topic' && !showTopics) return false;
      if (n.type === 'Entity' && !showEntities) return false;
      if (n.type === 'Chunk' && !showChunks) return false;
      return true;
    });

    const allowedIds = new Set(allowedNodes.map((n) => n.id));

    allowedNodes.forEach((n, idx) => {
      const existing = simNodesRef.current.get(n.id);
      const conf = TYPE_CONFIG[n.type] || TYPE_CONFIG.Default;

      // Position in clusters or circles
      let initialX = width / 2 + (Math.random() - 0.5) * 260;
      let initialY = canvasHeight / 2 + (Math.random() - 0.5) * 200;

      if (n.type === 'Document') {
        initialX = width / 2;
        initialY = canvasHeight / 2;
      } else if (n.type === 'Topic') {
        const angle = (idx / Math.max(1, counts.topic)) * Math.PI * 2;
        initialX = width / 2 + Math.cos(angle) * 140;
        initialY = canvasHeight / 2 + Math.sin(angle) * 110;
      } else if (n.type === 'Chunk') {
        const chunkIdx = n.properties?.chunk_index ?? idx;
        const totalChunks = Math.max(1, counts.chunk);
        const spreadX = ((chunkIdx + 0.5) - totalChunks / 2) * 80;
        initialX = width / 2 + spreadX;
        initialY = canvasHeight / 2 + 130;
      } else if (n.type === 'Entity') {
        const entIdx = idx % Math.max(1, counts.entity);
        const angle = (entIdx / Math.max(1, counts.entity)) * Math.PI * 2;
        initialX = width / 2 + Math.cos(angle) * 190;
        initialY = canvasHeight / 2 + Math.sin(angle) * 150;
      }

      nodeMap.set(n.id, {
        ...n,
        x: existing ? existing.x : initialX,
        y: existing ? existing.y : initialY,
        vx: 0,
        vy: 0,
        radius: conf.radius,
        color: conf.color,
        textColor: conf.textColor,
        pinned: n.type === 'Document',
      });
    });

    simNodesRef.current = nodeMap;

    // Filter edges
    const simEdges: SimEdge[] = [];
    edges.forEach((e) => {
      const sourceNode = nodeMap.get(e.source);
      const targetNode = nodeMap.get(e.target);
      if (sourceNode && targetNode && allowedIds.has(e.source) && allowedIds.has(e.target)) {
        simEdges.push({
          source: sourceNode,
          target: targetNode,
          relation: e.relation,
          properties: e.properties,
        });
      }
    });

    simEdgesRef.current = simEdges;
    restartSimulation();
  }, [nodes, edges, showDocument, showTopics, showEntities, showChunks, height]);

  // Draw canvas scene (callable on demand without running physics)
  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.width / dpr;
    const canvasHeight = canvas.height / dpr;

    ctx.save();
    ctx.clearRect(0, 0, width, canvasHeight);

    // Apply Zoom and Pan transform
    const { x, y, k } = transformRef.current;
    ctx.translate(x, y);
    ctx.scale(k, k);

    const nodesArr = Array.from(simNodesRef.current.values());
    const edgesArr = simEdgesRef.current;

    // Identify highlighted node and direct 1-hop neighbors
    const activeId = selectedNodeId || hoveredNodeIdRef.current;
    const highlightedNeighborIds = new Set<string>();
    if (activeId) {
      highlightedNeighborIds.add(activeId);
      edgesArr.forEach((e) => {
        if (e.source.id === activeId) highlightedNeighborIds.add(e.target.id);
        if (e.target.id === activeId) highlightedNeighborIds.add(e.source.id);
      });
    }

    // 1. Draw Edges
    // Level-of-Detail (LOD): If an entity is active, only draw labels for directly incident edges
    // If no entity is active, draw labels only when zoomed in (k >= 1.25) or sparse graph (<= 35 edges)
    const shouldDrawAnyEdgeLabel = showEdgeLabels && (!activeId ? (k >= 1.25 || edgesArr.length <= 35) : true);

    edgesArr.forEach((edge) => {
      const isIncident = activeId ? (edge.source.id === activeId || edge.target.id === activeId) : false;
      const isConnected =
        !activeId ||
        isIncident ||
        (highlightedNeighborIds.has(edge.source.id) && highlightedNeighborIds.has(edge.target.id));

      const isInterChunk = edge.source.type === 'Chunk' && edge.target.type === 'Chunk';

      // Fast pass for dimmed edges when an active node exists: simple line, skip arrowheads and text
      if (activeId && !isConnected) {
        ctx.globalAlpha = 0.08;
        ctx.strokeStyle = '#D8D5CE';
        ctx.lineWidth = 1;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(edge.source.x, edge.source.y);
        ctx.lineTo(edge.target.x, edge.target.y);
        ctx.stroke();
        return;
      }

      ctx.globalAlpha = activeId ? (isConnected ? 0.95 : 0.12) : 0.7;

      if (isInterChunk) {
        if (edge.relation === 'NEXT_CHUNK') {
          ctx.strokeStyle = isIncident ? '#2563EB' : '#475569';
          ctx.lineWidth = isIncident ? 2.6 : 1.8;
          ctx.setLineDash([4, 3]);
        } else if (edge.relation === 'SHARES_ENTITY') {
          ctx.strokeStyle = isIncident ? '#059669' : '#15803D';
          ctx.lineWidth = isIncident ? 2.6 : 1.8;
          ctx.setLineDash([]);
        } else {
          ctx.strokeStyle = isIncident ? '#D97706' : '#B45309';
          ctx.lineWidth = isIncident ? 2.6 : 1.8;
          ctx.setLineDash([]);
        }
      } else {
        ctx.strokeStyle = isIncident ? '#E8A36A' : '#B8B5AD';
        ctx.lineWidth = isIncident ? 2.2 : 1.2;
        ctx.setLineDash([]);
      }

      // Draw line
      ctx.beginPath();
      ctx.moveTo(edge.source.x, edge.source.y);
      ctx.lineTo(edge.target.x, edge.target.y);
      ctx.stroke();
      ctx.setLineDash([]); // reset dash

      // Draw Arrowhead pointing to target
      const angle = Math.atan2(edge.target.y - edge.source.y, edge.target.x - edge.source.x);
      const arrowLength = isInterChunk ? 8 : 7;
      const targetEdgeX = edge.target.x - Math.cos(angle) * (edge.target.radius + 3);
      const targetEdgeY = edge.target.y - Math.sin(angle) * (edge.target.radius + 3);

      ctx.fillStyle = isInterChunk
        ? edge.relation === 'NEXT_CHUNK'
          ? '#2563EB'
          : edge.relation === 'SHARES_ENTITY'
          ? '#059669'
          : '#D97706'
        : isIncident
        ? '#E8A36A'
        : '#99958D';

      ctx.beginPath();
      ctx.moveTo(targetEdgeX, targetEdgeY);
      ctx.lineTo(
        targetEdgeX - arrowLength * Math.cos(angle - Math.PI / 6),
        targetEdgeY - arrowLength * Math.sin(angle - Math.PI / 6)
      );
      ctx.lineTo(
        targetEdgeX - arrowLength * Math.cos(angle + Math.PI / 6),
        targetEdgeY - arrowLength * Math.sin(angle + Math.PI / 6)
      );
      ctx.closePath();
      ctx.fill();

      // Draw edge relationship label if enabled and connected
      const shouldDrawThisLabel = shouldDrawAnyEdgeLabel && (!activeId || isIncident);
      if (shouldDrawThisLabel) {
        const midX = (edge.source.x + edge.target.x) / 2;
        const midY = (edge.source.y + edge.target.y) / 2;

        ctx.font = '9px "SFMono-Regular", Consolas, monospace';

        let labelText = edge.relation;
        if (edge.relation === 'NEXT_CHUNK') {
          labelText = 'NEXT_CHUNK';
        } else if (edge.relation === 'SHARES_ENTITY') {
          labelText = `SHARES: ${edge.properties?.entity || 'ENTITY'}`;
        } else if (edge.relation === 'CROSS_CHUNK_RELATION') {
          labelText = `BRIDGES: ${edge.properties?.relation || 'REL'}`;
        }

        let labelWidth = textWidthCache.current.get(labelText);
        if (labelWidth === undefined) {
          labelWidth = ctx.measureText(labelText).width;
          textWidthCache.current.set(labelText, labelWidth);
        }
        const padX = 4;
        const padY = 2;

        ctx.fillStyle = 'rgba(252, 251, 248, 0.94)';
        ctx.fillRect(
          midX - labelWidth / 2 - padX,
          midY - 5 - padY,
          labelWidth + padX * 2,
          11 + padY
        );

        ctx.strokeStyle = isInterChunk
          ? edge.relation === 'NEXT_CHUNK'
            ? '#3B82F6'
            : edge.relation === 'SHARES_ENTITY'
            ? '#10B981'
            : '#F59E0B'
          : isIncident
          ? '#E8A36A'
          : '#D8D5CE';
        ctx.lineWidth = 0.8;
        ctx.strokeRect(
          midX - labelWidth / 2 - padX,
          midY - 5 - padY,
          labelWidth + padX * 2,
          11 + padY
        );

        ctx.fillStyle = isInterChunk
          ? edge.relation === 'NEXT_CHUNK'
            ? '#1E40AF'
            : edge.relation === 'SHARES_ENTITY'
            ? '#065F46'
            : '#92400E'
          : isIncident
          ? '#C27129'
          : '#6F6D68';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(labelText, midX, midY + 0.5);
      }
    });

    // 2. Draw Nodes
    nodesArr.forEach((node) => {
      const isHighlighted = !activeId || highlightedNeighborIds.has(node.id);
      const isSelected = selectedNodeId === node.id;
      const isHovered = hoveredNodeIdRef.current === node.id;
      const isSearchMatch =
        searchFilter.trim() !== '' &&
        node.label.toLowerCase().includes(searchFilter.trim().toLowerCase());

      ctx.globalAlpha = isHighlighted ? 1 : 0.18;

      // Outer focus glow/ring for selected or search match
      if (isSelected || isSearchMatch) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius + 6, 0, Math.PI * 2);
        ctx.fillStyle = isSelected ? 'rgba(232, 163, 106, 0.28)' : 'rgba(5, 150, 105, 0.25)';
        ctx.fill();
        ctx.strokeStyle = isSelected ? '#E8A36A' : '#15803D';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      if (isHovered && !isSelected) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius + 4, 0, Math.PI * 2);
        ctx.strokeStyle = '#30302E';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Main Node Circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = node.color;
      ctx.fill();
      ctx.strokeStyle = '#FCFBF8';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Node Icon / Short symbol inside
      ctx.fillStyle = node.textColor;
      ctx.font = 'bold 10px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';

      let symbol = '';
      if (node.type === 'Document') symbol = 'DOC';
      else if (node.type === 'Topic') symbol = 'T';
      else if (node.type === 'Entity') symbol = 'E';
      else if (node.type === 'Chunk') symbol = `#${node.properties?.chunk_index ?? ''}`;
      ctx.fillText(symbol, node.x, node.y);

      // Node Label Text Below
      const isKeyNode = node.type === 'Document' || node.type === 'Topic';
      const showPill = isHighlighted && (isSelected || isHovered || isSearchMatch || isKeyNode || k >= 0.72 || nodesArr.length <= 40);

      if (showPill) {
        ctx.globalAlpha = isHighlighted ? 1 : 0.2;
        ctx.font = isSelected
          ? 'bold 11px sans-serif'
          : '10px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

        // Truncate label if too long
        let displayLabel = node.label;
        if (displayLabel.length > 22) displayLabel = displayLabel.slice(0, 20) + '...';

        let textW = textWidthCache.current.get(displayLabel);
        if (textW === undefined) {
          textW = ctx.measureText(displayLabel).width;
          textWidthCache.current.set(displayLabel, textW);
        }
        const badgeY = node.y + node.radius + 9;

        // Label pill background
        ctx.fillStyle = isSelected ? '#30302E' : 'rgba(252, 251, 248, 0.95)';
        ctx.strokeStyle = isSelected ? '#30302E' : '#D8D5CE';
        ctx.lineWidth = 1;

        const pad = 3;
        ctx.beginPath();
        if (typeof ctx.roundRect === 'function') {
          ctx.roundRect(
            node.x - textW / 2 - pad,
            badgeY - 7,
            textW + pad * 2,
            14,
            3
          );
        } else {
          ctx.rect(
            node.x - textW / 2 - pad,
            badgeY - 7,
            textW + pad * 2,
            14
          );
        }
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = isSelected ? '#FCFBF8' : '#252525';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(displayLabel, node.x, badgeY);
      }
    });

    ctx.restore();
  }, [selectedNodeId, searchFilter, showEdgeLabels]);

  // Restart physics loop with full kinetic energy; settles and automatically pauses
  const restartSimulation = useCallback((initialEnergy = 70, maxSimulationTicks = 75) => {
    let energy = initialEnergy;
    let ticks = 0;
    const maxTicks = maxSimulationTicks;

    isSimulatingRef.current = true;
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }

    const tick = () => {
      const canvas = canvasRef.current;
      if (!canvas) {
        isSimulatingRef.current = false;
        animFrameRef.current = null;
        return;
      }

      ticks++;
      const nodesArr = Array.from(simNodesRef.current.values());
      const edgesArr = simEdgesRef.current;
      const width = canvas.width / (window.devicePixelRatio || 1);
      const canvasHeight = canvas.height / (window.devicePixelRatio || 1);
      const centerX = width / 2;
      const centerY = canvasHeight / 2;

      // Physics update if system still has kinetic energy or user is dragging
      if ((energy > 0.08 || isDraggingRef.current) && ticks < maxTicks) {
        // 1. Center gravity
        nodesArr.forEach((node) => {
          if (node.pinned && !isDraggingRef.current) return;
          const dx = centerX - node.x;
          const dy = centerY - node.y;
          node.vx += dx * 0.0006;
          node.vy += dy * 0.0006;
        });

        // 2. Coulomb electrostatic repulsion between nodes (with 250px cutoff)
        const maxRepulsionDistSq = 62500;
        for (let i = 0; i < nodesArr.length; i++) {
          const a = nodesArr[i];
          for (let j = i + 1; j < nodesArr.length; j++) {
            const b = nodesArr[j];
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const distSq = dx * dx + dy * dy + 100;
            if (distSq > maxRepulsionDistSq) continue;
            const dist = Math.sqrt(distSq);
            const force = 3000 / distSq;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            if (!a.pinned) {
              a.vx -= fx;
              a.vy -= fy;
            }
            if (!b.pinned) {
              b.vx += fx;
              b.vy += fy;
            }
          }
        }

        // 3. Hooke's spring attraction along edges
        edgesArr.forEach((edge) => {
          const a = edge.source;
          const b = edge.target;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;

          // Target link distance depends on relationship
          let targetDist = 95;
          if (edge.relation === 'HAS_CHUNK') targetDist = 120;
          if (edge.relation === 'HAS_TOPIC') targetDist = 75;
          if (edge.relation === 'MENTIONS') targetDist = 85;

          const diff = dist - targetDist;
          const force = Math.max(-6, Math.min(6, diff * 0.035));
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;

          if (!a.pinned) {
            a.vx -= fx;
            a.vy -= fy;
          }
          if (!b.pinned) {
            b.vx += fx;
            b.vy += fy;
          }
        });

        // 4. Integrate velocities with fast damping
        let totalVelocity = 0;
        nodesArr.forEach((node) => {
          if (node === draggedNodeRef.current) return;
          if (!node.pinned) {
            node.vx *= 0.78;
            node.vy *= 0.78;
            node.x += node.vx;
            node.y += node.vy;
            totalVelocity += Math.abs(node.vx) + Math.abs(node.vy);
          }
        });

        energy = totalVelocity;
        drawCanvas();
        animFrameRef.current = requestAnimationFrame(tick);
      } else {
        // System settled into resting state: render final clean frame and pause animation loop
        drawCanvas();
        animFrameRef.current = null;
        isSimulatingRef.current = false;
      }
    };

    animFrameRef.current = requestAnimationFrame(tick);
  }, [drawCanvas]);

  // Canvas Resize observer
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) return;

      const dpr = window.devicePixelRatio || 1;
      const width = container.clientWidth;
      const canvasHeight = height;

      canvas.width = width * dpr;
      canvas.height = canvasHeight * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${canvasHeight}px`;

      const ctx = canvas.getContext('2d');
      if (ctx) ctx.scale(dpr, dpr);
      drawCanvas();
    };

    handleResize();
    const ro = new ResizeObserver(handleResize);
    if (containerRef.current) ro.observe(containerRef.current);

    return () => ro.disconnect();
  }, [height]);

  // Clean up animation frame
  useEffect(() => {
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, []);

  // Screen coordinates to Canvas Simulation coordinates
  const screenToWorld = useCallback((screenX: number, screenY: number) => {
    const { x, y, k } = transformRef.current;
    return {
      x: (screenX - x) / k,
      y: (screenY - y) / k,
    };
  }, []);

  // Mouse / Pointer Event Handlers
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldPos = screenToWorld(mouseX, mouseY);

    // Check if clicked a node
    const nodesArr = Array.from(simNodesRef.current.values());
    let hitNode: SimNode | null = null;

    // Search top-most node (reverse)
    for (let i = nodesArr.length - 1; i >= 0; i--) {
      const node = nodesArr[i];
      const dx = worldPos.x - node.x;
      const dy = worldPos.y - node.y;
      if (dx * dx + dy * dy <= (node.radius + 6) * (node.radius + 6)) {
        hitNode = node;
        break;
      }
    }

    if (hitNode) {
      isDraggingRef.current = true;
      draggedNodeRef.current = hitNode;
      setSelectedNodeId(hitNode.id);
      if (hitNode.type === 'Entity' && onSelectEntity) {
        onSelectEntity(hitNode.label);
      }
      setTwoHopData(null); // reset 2-hop panel for newly selected node
      if (!isSimulatingRef.current) {
        restartSimulation(35, 45);
      }
    } else {
      isPanningRef.current = true;
    }

    lastMousePosRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const dx = e.clientX - lastMousePosRef.current.x;
    const dy = e.clientY - lastMousePosRef.current.y;
    lastMousePosRef.current = { x: e.clientX, y: e.clientY };

    if (isDraggingRef.current && draggedNodeRef.current) {
      // Move dragged node in world space
      draggedNodeRef.current.x += dx / transformRef.current.k;
      draggedNodeRef.current.y += dy / transformRef.current.k;
      draggedNodeRef.current.vx = 0;
      draggedNodeRef.current.vy = 0;
      if (!isSimulatingRef.current) {
        restartSimulation(35, 45);
      } else {
        drawCanvas();
      }
    } else if (isPanningRef.current) {
      // Pan canvas without physics overhead
      transformRef.current.x += dx;
      transformRef.current.y += dy;
      drawCanvas();
    } else {
      // Hover detection without React re-rendering
      const worldPos = screenToWorld(mouseX, mouseY);
      const nodesArr = Array.from(simNodesRef.current.values());
      let hovered: SimNode | null = null;
      for (let i = nodesArr.length - 1; i >= 0; i--) {
        const node = nodesArr[i];
        const ndx = worldPos.x - node.x;
        const ndy = worldPos.y - node.y;
        if (ndx * ndx + ndy * ndy <= (node.radius + 4) * (node.radius + 4)) {
          hovered = node;
          break;
        }
      }
      const newHoverId = hovered ? hovered.id : null;
      if (newHoverId !== hoveredNodeIdRef.current) {
        hoveredNodeIdRef.current = newHoverId;
        drawCanvas();
      }
    }
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
    draggedNodeRef.current = null;
    isPanningRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
    const currentK = transformRef.current.k;
    const nextK = Math.min(3.5, Math.max(0.2, currentK * zoomFactor));

    // Zoom centered on cursor position
    transformRef.current.x = mouseX - (mouseX - transformRef.current.x) * (nextK / currentK);
    transformRef.current.y = mouseY - (mouseY - transformRef.current.y) * (nextK / currentK);
    transformRef.current.k = nextK;
    setZoomLevel(nextK);
    drawCanvas();
  };

  // Zoom control buttons
  const handleZoomIn = () => {
    const nextK = Math.min(3.5, transformRef.current.k * 1.25);
    const canvas = canvasRef.current;
    if (canvas) {
      const cx = canvas.width / (2 * (window.devicePixelRatio || 1));
      const cy = canvas.height / (2 * (window.devicePixelRatio || 1));
      transformRef.current.x = cx - (cx - transformRef.current.x) * (nextK / transformRef.current.k);
      transformRef.current.y = cy - (cy - transformRef.current.y) * (nextK / transformRef.current.k);
      transformRef.current.k = nextK;
      setZoomLevel(nextK);
      drawCanvas();
    }
  };

  const handleZoomOut = () => {
    const nextK = Math.max(0.2, transformRef.current.k * 0.8);
    const canvas = canvasRef.current;
    if (canvas) {
      const cx = canvas.width / (2 * (window.devicePixelRatio || 1));
      const cy = canvas.height / (2 * (window.devicePixelRatio || 1));
      transformRef.current.x = cx - (cx - transformRef.current.x) * (nextK / transformRef.current.k);
      transformRef.current.y = cy - (cy - transformRef.current.y) * (nextK / transformRef.current.k);
      transformRef.current.k = nextK;
      setZoomLevel(nextK);
      drawCanvas();
    }
  };

  const handleResetCamera = () => {
    transformRef.current = { x: 0, y: 0, k: 1 };
    setZoomLevel(1);
    drawCanvas();
  };

  // Fetch FalkorDB 2-hop subgraph for selected entity
  const handleFetchTwoHop = async (entityName: string) => {
    setIsLoadingTwoHop(true);
    try {
      const res = await fetch(`/api/v1/understand/graph/entity/${encodeURIComponent(entityName)}`);
      if (res.ok) {
        const data = await res.json();
        setTwoHopData(data);
      }
    } catch (err) {
      console.error('Failed to fetch 2-hop FalkorDB data:', err);
    } finally {
      setIsLoadingTwoHop(false);
    }
  };

  // Get current selected node data
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return simNodesRef.current.get(selectedNodeId) || null;
  }, [selectedNodeId]);

  // Direct connected edges and neighbor nodes for inspector
  const connections = useMemo(() => {
    if (!selectedNodeId) return { in: [], out: [] };
    const inEdges = simEdgesRef.current.filter((e) => e.target.id === selectedNodeId);
    const outEdges = simEdgesRef.current.filter((e) => e.source.id === selectedNodeId);
    return { in: inEdges, out: outEdges };
  }, [selectedNodeId]);

  // Specialized Inter-chunk connections for Chunk nodes
  const interChunkConnections = useMemo(() => {
    if (!selectedNodeId) return [];
    return simEdgesRef.current
      .filter((e) => {
        const isChunkSource = e.source.type === 'Chunk' && e.source.id === selectedNodeId;
        const isChunkTarget = e.target.type === 'Chunk' && e.target.id === selectedNodeId;
        const otherIsChunk =
          (isChunkSource && e.target.type === 'Chunk') ||
          (isChunkTarget && e.source.type === 'Chunk');
        return (
          otherIsChunk &&
          ['NEXT_CHUNK', 'SHARES_ENTITY', 'CROSS_CHUNK_RELATION'].includes(e.relation)
        );
      })
      .map((e) => {
        const isOutgoing = e.source.id === selectedNodeId;
        const neighbor = isOutgoing ? e.target : e.source;
        return {
          edge: e,
          isOutgoing,
          neighbor,
          relation: e.relation,
          entity: e.properties?.entity,
          targetRelation: e.properties?.relation,
        };
      });
  }, [selectedNodeId]);

  return (
    <div className="bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg shadow-soft overflow-hidden flex flex-col">
      {/* Top Toolbar */}
      <div className="p-3 border-b border-[#D8D5CE] flex flex-wrap items-center justify-between gap-2.5 bg-[#F8F7F3]">
        {/* Left: Title & Live Counts */}
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1.5 font-mono text-xs font-semibold text-[#252525]">
            <span className="w-2 h-2 rounded-full bg-[#15803D] animate-pulse"></span>
            <span>FalkorDB Knowledge Graph</span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#EAE8E1] text-[#6F6D68] border border-[#D8D5CE]">
            {nodes.length} Nodes · {edges.length} Edges{docId ? ` · [${docId.slice(0, 8)}]` : ''}
          </span>
        </div>

        {/* Center: Type Filters */}
        <div className="flex items-center flex-wrap gap-1.5 text-[11px] font-mono">
          <button
            onClick={() => setShowDocument((prev) => !prev)}
            className={`px-2 py-0.5 rounded border transition ${
              showDocument
                ? 'bg-[#30302E] text-white border-[#30302E]'
                : 'bg-[#FCFBF8] text-[#99958D] border-[#D8D5CE]'
            }`}
          >
            Doc ({counts.doc})
          </button>
          <button
            onClick={() => setShowTopics((prev) => !prev)}
            className={`px-2 py-0.5 rounded border transition ${
              showTopics
                ? 'bg-[#D97706] text-white border-[#D97706]'
                : 'bg-[#FCFBF8] text-[#99958D] border-[#D8D5CE]'
            }`}
          >
            Topics ({counts.topic})
          </button>
          <button
            onClick={() => setShowEntities((prev) => !prev)}
            className={`px-2 py-0.5 rounded border transition ${
              showEntities
                ? 'bg-[#15803D] text-white border-[#15803D]'
                : 'bg-[#FCFBF8] text-[#99958D] border-[#D8D5CE]'
            }`}
          >
            Entities ({counts.entity})
          </button>
          <button
            onClick={() => setShowChunks((prev) => !prev)}
            className={`px-2 py-0.5 rounded border transition ${
              showChunks
                ? 'bg-[#475569] text-white border-[#475569]'
                : 'bg-[#FCFBF8] text-[#99958D] border-[#D8D5CE]'
            }`}
          >
            Chunks ({counts.chunk})
          </button>
        </div>

        {/* Right: Search & View Controls */}
        <div className="flex items-center space-x-1.5">
          <input
            type="text"
            placeholder="Search node..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="w-28 sm:w-36 bg-[#FCFBF8] border border-[#D8D5CE] rounded px-2 py-0.5 text-xs text-[#252525] font-mono focus:outline-none focus:border-[#30302E]"
          />
          <button
            onClick={() => setShowEdgeLabels((p) => !p)}
            title="Toggle Edge Labels"
            className={`px-2 py-1 rounded text-[11px] font-mono border ${
              showEdgeLabels ? 'bg-[#EAE8E1] text-[#252525] border-[#D8D5CE]' : 'bg-[#FCFBF8] text-[#99958D] border-[#D8D5CE]'
            }`}
          >
            Labels
          </button>
          <div className="flex items-center border border-[#D8D5CE] rounded bg-[#FCFBF8] overflow-hidden">
            <button
              onClick={handleZoomIn}
              title="Zoom In"
              className="px-2 py-0.5 hover:bg-[#EAE8E1] text-xs font-mono text-[#252525] border-r border-[#D8D5CE]"
            >
              +
            </button>
            <button
              onClick={handleZoomOut}
              title="Zoom Out"
              className="px-2 py-0.5 hover:bg-[#EAE8E1] text-xs font-mono text-[#252525] border-r border-[#D8D5CE]"
            >
              -
            </button>
            <button
              onClick={handleResetCamera}
              title="Reset View"
              className="px-2 py-0.5 hover:bg-[#EAE8E1] text-[10px] font-mono text-[#252525]"
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* Main Canvas + Inspector Area */}
      <div
        ref={containerRef}
        className="relative w-full overflow-hidden bg-[#FCFBF8] [background-image:radial-gradient(#D8D5CE_1px,transparent_1px)] [background-size:24px_24px]"
        style={{ height }}
      >
        {isLoading && (
          <div className="absolute inset-0 bg-[#FCFBF8]/80 backdrop-blur-sm flex items-center justify-center z-10">
            <div className="flex items-center space-x-2 text-xs font-mono text-[#6F6D68]">
              <span className="w-3 h-3 border-2 border-[#30302E] border-t-transparent rounded-full animate-spin"></span>
              <span>Loading Knowledge Graph Topology...</span>
            </div>
          </div>
        )}

        {nodes.length === 0 && !isLoading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6 text-[#99958D]">
            <span className="text-2xl mb-1">🕸️</span>
            <p className="text-xs font-mono">No graph topology indexed yet.</p>
            <p className="text-[11px] text-[#6F6D68] mt-1 max-w-sm">
              Upload a source document and run analysis to extract entities, topics, and FalkorDB knowledge relations.
            </p>
          </div>
        )}

        <canvas
          ref={canvasRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
          className="w-full h-full cursor-grab active:cursor-grabbing block"
        />

        {/* Floating Controls Overlay (Bottom-Left) */}
        <div className="absolute bottom-2.5 left-2.5 bg-[#FCFBF8]/95 backdrop-blur border border-[#D8D5CE] rounded px-3 py-1.5 text-[10px] font-mono text-[#6F6D68] shadow-soft pointer-events-none flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-semibold text-[#252525]">Zoom: {Math.round(zoomLevel * 100)}%</span>
          <span>•</span>
          <span>Scroll to Zoom · Drag to Move</span>
          <span>•</span>
          <div className="flex items-center space-x-2 text-[9px]">
            <span className="flex items-center space-x-1">
              <span className="w-3 h-0.5 border-t border-dashed border-[#2563EB] inline-block"></span>
              <span className="text-[#2563EB]">Next Chunk</span>
            </span>
            <span className="flex items-center space-x-1">
              <span className="w-3 h-0.5 bg-[#059669] inline-block"></span>
              <span className="text-[#059669]">Shared Entity</span>
            </span>
            <span className="flex items-center space-x-1">
              <span className="w-3 h-0.5 bg-[#D97706] inline-block"></span>
              <span className="text-[#D97706]">Cross-Chunk Relation</span>
            </span>
          </div>
        </div>

        {/* Selected Node Inspector Drawer (Right Side) */}
        {selectedNode && (
          <div className="absolute top-2.5 right-2.5 w-80 max-h-[calc(100%-20px)] bg-[#FCFBF8] border border-[#D8D5CE] rounded-lg shadow-soft p-3.5 space-y-3 overflow-y-auto text-xs z-20">
            <div className="flex items-start justify-between pb-2 border-b border-[#D8D5CE]">
              <div>
                <div className="flex items-center space-x-1.5 mb-1">
                  <span
                    className="w-2.5 h-2.5 rounded-full inline-block"
                    style={{ backgroundColor: selectedNode.color }}
                  ></span>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#6F6D68]">
                    {selectedNode.type} Node
                  </span>
                </div>
                <h4 className="text-xs font-bold text-[#252525] break-words">{selectedNode.label}</h4>
              </div>
              <button
                onClick={() => {
                  setSelectedNodeId(null);
                  setTwoHopData(null);
                }}
                className="text-[#99958D] hover:text-[#252525] text-sm font-mono px-1"
                title="Close Inspector"
              >
                ✕
              </button>
            </div>

            {/* Properties */}
            <div className="space-y-1 text-[11px] font-mono">
              <span className="text-[10px] text-[#6F6D68] uppercase block">Attributes</span>
              {selectedNode.type === 'Entity' && (
                <div className="p-2 bg-[#F8F7F3] rounded border border-[#D8D5CE] space-y-1">
                  <div>
                    <span className="text-[#6F6D68]">Classification: </span>
                    <span className="text-[#15803D] font-semibold">
                      {selectedNode.properties?.entity_type || 'ENTITY'}
                    </span>
                  </div>
                  {selectedNode.properties?.count !== undefined && (
                    <div>
                      <span className="text-[#6F6D68]">Occurrences: </span>
                      <span className="text-[#252525]">{selectedNode.properties.count} times</span>
                    </div>
                  )}
                </div>
              )}

              {selectedNode.type === 'Chunk' && (
                <div className="space-y-2">
                  <div className="p-2 bg-[#F8F7F3] rounded border border-[#D8D5CE] space-y-1">
                    <div>
                      <span className="text-[#6F6D68]">Chunk Index: </span>
                      <span className="text-[#252525] font-semibold">#{selectedNode.properties?.chunk_index}</span>
                    </div>
                    <div>
                      <span className="text-[#6F6D68]">Character Offsets: </span>
                      <span className="text-[#252525]">
                        [{selectedNode.properties?.char_start}:{selectedNode.properties?.char_end}]
                      </span>
                    </div>
                    {selectedNode.properties?.preview && (
                      <div className="mt-1 pt-1 border-t border-[#EAE8E1] text-[10px] font-sans text-[#252525] italic line-clamp-3">
                        "{selectedNode.properties.preview}"
                      </div>
                    )}
                  </div>

                  {/* Inter-Chunk Relationships Section */}
                  <div className="p-2 bg-[#F8F7F3] rounded border border-[#D8D5CE] space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase font-semibold text-[#475569]">
                        Inter-Chunk Relationships ({interChunkConnections.length})
                      </span>
                    </div>
                    {interChunkConnections.length === 0 ? (
                      <div className="text-[10px] font-mono text-[#99958D]">
                        No direct inter-chunk connections found.
                      </div>
                    ) : (
                      <div className="space-y-1 max-h-36 overflow-y-auto pr-0.5">
                        {interChunkConnections.map((conn, idx) => (
                          <div
                            key={idx}
                            onClick={() => setSelectedNodeId(conn.neighbor.id)}
                            className="p-1.5 rounded bg-[#FCFBF8] hover:bg-[#EAE8E1] cursor-pointer border border-[#D8D5CE] flex items-center justify-between text-[10px] font-mono transition"
                            title={`Jump to ${conn.neighbor.label}`}
                          >
                            <div className="flex flex-col min-w-0 pr-1">
                              <span
                                className={`font-semibold truncate ${
                                  conn.relation === 'NEXT_CHUNK'
                                    ? 'text-[#2563EB]'
                                    : conn.relation === 'SHARES_ENTITY'
                                    ? 'text-[#059669]'
                                    : 'text-[#D97706]'
                                }`}
                              >
                                {conn.relation === 'NEXT_CHUNK'
                                  ? conn.isOutgoing
                                    ? '→ NEXT_CHUNK'
                                    : '← PREV_CHUNK'
                                  : conn.relation === 'SHARES_ENTITY'
                                  ? `⟷ SHARES: ${conn.entity || 'Entity'}`
                                  : `⟷ BRIDGES: ${conn.targetRelation || 'Relation'}`}
                              </span>
                              <span className="text-[9px] text-[#6F6D68] truncate">
                                {conn.neighbor.label}
                              </span>
                            </div>
                            <span className="text-[#99958D] text-xs">→</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {selectedNode.type === 'Topic' && (
                <div className="p-2 bg-[#F8F7F3] rounded border border-[#D8D5CE]">
                  <span className="text-[#6F6D68]">Topic: </span>
                  <span className="text-[#D97706] font-semibold">{selectedNode.label}</span>
                </div>
              )}

              {selectedNode.type === 'Document' && (
                <div className="p-2 bg-[#F8F7F3] rounded border border-[#D8D5CE]">
                  <span className="text-[#6F6D68]">Filename: </span>
                  <span className="text-[#30302E] font-medium">{selectedNode.label}</span>
                </div>
              )}
            </div>

            {/* Direct Connections (In & Out) */}
            <div className="space-y-1 text-[11px] font-mono">
              <span className="text-[10px] text-[#6F6D68] uppercase block">
                Topology Connections ({connections.in.length + connections.out.length})
              </span>
              <div className="max-h-36 overflow-y-auto space-y-1 pr-1">
                {connections.out.map((e, idx) => (
                  <div
                    key={`out-${idx}`}
                    onClick={() => setSelectedNodeId(e.target.id)}
                    className="p-1.5 rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] cursor-pointer border border-[#D8D5CE] flex items-center justify-between text-[10px]"
                  >
                    <span className="text-[#C27129] font-semibold">-[{e.relation}]-&gt;</span>
                    <span className="truncate max-w-[130px] text-[#252525] font-medium">
                      {e.target.label}
                    </span>
                  </div>
                ))}
                {connections.in.map((e, idx) => (
                  <div
                    key={`in-${idx}`}
                    onClick={() => setSelectedNodeId(e.source.id)}
                    className="p-1.5 rounded bg-[#F8F7F3] hover:bg-[#EAE8E1] cursor-pointer border border-[#D8D5CE] flex items-center justify-between text-[10px]"
                  >
                    <span className="truncate max-w-[130px] text-[#252525] font-medium">
                      {e.source.label}
                    </span>
                    <span className="text-[#6F6D68]">-[{e.relation}]-&gt;</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 2-Hop FalkorDB Deep Dive (if entity) */}
            {selectedNode.type === 'Entity' && (
              <div className="pt-2 border-t border-[#D8D5CE] space-y-2">
                <button
                  onClick={() => handleFetchTwoHop(selectedNode.label)}
                  disabled={isLoadingTwoHop}
                  className="w-full py-1.5 px-2 rounded bg-[#30302E] hover:bg-[#252525] text-white text-[10px] font-mono transition flex items-center justify-center space-x-1.5"
                >
                  {isLoadingTwoHop ? (
                    <span>Querying FalkorDB...</span>
                  ) : (
                    <>
                      <span>Explore 2-Hop Relations</span>
                      <span>→</span>
                    </>
                  )}
                </button>

                {twoHopData && (
                  <div className="p-2 bg-[#F8F7F3] rounded border border-[#D8D5CE] text-[10px] font-mono space-y-2">
                    <div className="font-semibold text-[#15803D]">
                      FalkorDB Subgraph for "{twoHopData.entity_name}":
                    </div>

                    {twoHopData.connected_entities.length > 0 ? (
                      <div>
                        <span className="text-[#6F6D68] block mb-0.5">Connected Entities:</span>
                        <div className="flex flex-wrap gap-1">
                          {twoHopData.connected_entities.map((ce, i) => (
                            <span
                              key={i}
                              className="px-1.5 py-0.5 bg-[#FCFBF8] border border-[#D8D5CE] rounded text-[#252525]"
                            >
                              {ce.name} <span className="text-[#99958D]">({ce.type})</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="text-[#99958D]">No direct entity-to-entity relations found.</div>
                    )}

                    {twoHopData.referenced_chunks.length > 0 && (
                      <div>
                        <span className="text-[#6F6D68] block mb-0.5">
                          Referenced in Chunks ({twoHopData.referenced_chunks.length}):
                        </span>
                        <div className="text-[#252525]">
                          {twoHopData.referenced_chunks.map((cid) => cid.slice(0, 8)).join(', ')}...
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
