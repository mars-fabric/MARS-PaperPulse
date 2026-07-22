// Example usage of ModernConsoleViewer and ModernArtifactsViewer

import { ModernConsoleViewer, ModernArtifactsViewer } from '@/components/console'

// For live logs during execution
export function ExecutionPanelExample() {
  const sampleLogs = [
    {
      id: '1',
      timestamp: '14:23:45',
      level: 'info' as const,
      message: 'Starting research workflow...',
    },
    {
      id: '2',
      timestamp: '14:23:46',
      level: 'success' as const,
      message: 'Idea generation stage initialized',
    },
    {
      id: '3',
      timestamp: '14:23:50',
      level: 'info' as const,
      message: 'Processing research ideas...',
    },
    {
      id: '4',
      timestamp: '14:24:15',
      level: 'success' as const,
      message: '5 research ideas generated',
    },
    {
      id: '5',
      timestamp: '14:24:16',
      level: 'info' as const,
      message: 'Starting method development...',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Live Logs */}
      <ModernConsoleViewer
        logs={sampleLogs}
        isLive={true}
        title="Execution Logs"
        maxHeight="400px"
        onCopy={() => console.log('Copied logs')}
        onDownload={() => console.log('Downloading logs')}
      />

      {/* Generated Artifacts */}
      <ModernArtifactsViewer
        artifacts={[
          {
            id: '1',
            name: 'research_ideas.json',
            type: 'data',
            size: 15360,
            path: '/artifacts/research_ideas.json',
            timestamp: '14:24:15',
          },
          {
            id: '2',
            name: 'methodology.md',
            type: 'document',
            size: 8192,
            path: '/artifacts/methodology.md',
            timestamp: '14:24:30',
          },
          {
            id: '3',
            name: 'execution_code.py',
            type: 'code',
            size: 24576,
            path: '/artifacts/execution_code.py',
            timestamp: '14:25:00',
          },
        ]}
        title="Generated Artifacts"
        onViewFile={(path) => console.log('View file:', path)}
        onDownloadFile={(path) => console.log('Download:', path)}
        onRefresh={() => console.log('Refresh artifacts')}
      />
    </div>
  )
}
