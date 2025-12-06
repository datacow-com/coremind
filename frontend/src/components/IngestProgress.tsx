import React, { useState, useEffect } from 'react';
import { useSse } from '../hooks/useSse';

interface IngestProgressProps {
  taskId: string;
  onComplete?: () => void;
}

interface NodeStatus {
  name: string;
  status: 'pending' | 'running' | 'done' | 'error';
  timestamp?: number;
}

export function IngestProgress({ taskId, onComplete }: IngestProgressProps) {
  const [nodes, setNodes] = useState<NodeStatus[]>([
    { name: 'loader', status: 'pending' },
    { name: 'router', status: 'pending' },
    { name: 'parser', status: 'pending' },
    { name: 'chunker', status: 'pending' },
    { name: 'embedder', status: 'pending' },
    { name: 'indexer', status: 'pending' }
  ]);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Connect to SSE
  const { start, close } = useSse(`/api/ingest/progress?task_id=${taskId}`, {
    onMessage: (msg) => {
      try {
        const event = JSON.parse(msg.data);
        
        if (event.type === 'node_start') {
          updateNodeStatus(event.node, 'running');
        } else if (event.type === 'node_end') {
          updateNodeStatus(event.node, 'done');
        } else if (event.type === 'progress') {
          if (event.data && event.data.total_chunks > 0) {
            const p = (event.data.completed_chunks / event.data.total_chunks) * 100;
            setProgress(Math.min(p, 100));
          }
        } else if (event.type === 'complete') {
          close();
          if (onComplete) onComplete();
        }
      } catch (e) {
        console.error("SSE Parse Error", e);
      }
    },
    onError: (err) => {
      setError("Connection lost or error occurred.");
    }
  });

  useEffect(() => {
    if (taskId) {
      start();
    }
    return () => close();
  }, [taskId]);

  const updateNodeStatus = (nodeName: string, status: 'running' | 'done' | 'error') => {
    setNodes(prev => prev.map(n => {
      // Map graph node names to UI steps if needed
      // For now assume 1:1 or simplified mapping
      if (n.name === nodeName || (nodeName.includes('parser') && n.name === 'parser')) {
        return { ...n, status, timestamp: Date.now() };
      }
      return n;
    }));
  };

  return (
    <div className="p-4 border rounded shadow-sm bg-white">
      <h3 className="font-bold mb-4">Ingestion Progress</h3>
      
      {/* Pipeline Viz */}
      <div className="flex items-center justify-between mb-6 text-sm">
        {nodes.map((node, idx) => (
          <React.Fragment key={node.name}>
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 
                ${node.status === 'done' ? 'bg-green-100 border-green-500 text-green-700' : 
                  node.status === 'running' ? 'bg-blue-100 border-blue-500 text-blue-700 animate-pulse' : 
                  node.status === 'error' ? 'bg-red-100 border-red-500 text-red-700' : 'bg-gray-50 border-gray-300 text-gray-400'}`}>
                {node.status === 'done' ? '✓' : idx + 1}
              </div>
              <span className="mt-1 capitalize">{node.name}</span>
            </div>
            {idx < nodes.length - 1 && (
              <div className={`flex-1 h-1 mx-2 rounded 
                ${nodes[idx].status === 'done' ? 'bg-green-500' : 'bg-gray-200'}`} />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4">
        <div className="bg-blue-600 h-2.5 rounded-full transition-all duration-500" style={{ width: `${progress}%` }}></div>
      </div>
      
      {error && (
        <div className="text-red-500 text-sm bg-red-50 p-2 rounded">
          Error: {error}
        </div>
      )}
    </div>
  );
}

