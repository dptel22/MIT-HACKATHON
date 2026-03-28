const STAGES = [
  { key: 'injected',  label: 'Fault\nInjected' },
  { key: 'detected',  label: 'Anomaly\nDetected' },
  { key: 'decided',   label: 'Decision\nMade' },
  { key: 'restarted', label: 'Pod\nRestarted' },
  { key: 'healed',    label: 'Healed' },
];

const STAGE_DOT_COLORS = {
  injected:  '#ef4444',
  detected:  '#f59e0b',
  decided:   '#38bdf8',
  restarted: '#a78bfa',
  healed:    '#22c55e',
};

function getDotClass(stageKey, doneStages) {
  const idx = STAGES.findIndex(s => s.key === stageKey);
  const doneIdx = doneStages; // number of stages completed (0-5)
  if (idx < doneIdx)   return 'done';
  if (idx === doneIdx) return 'active';
  return 'pending';
}

export default function IncidentTimeline({ incidents }) {
  // Use the most recent incident to build the timeline
  const latest = incidents[0] || null;

  // Determine stage from the latest incident status
  let doneStages = 0;
  let timestamps = {};

  if (latest) {
    const ts = latest.timestamp || '';
    const timeStr = ts ? new Date(ts * 1000).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';

    if (latest.status === 'HEALED') {
      doneStages = 5;
      timestamps = { injected: timeStr, detected: timeStr, decided: timeStr, restarted: timeStr, healed: timeStr };
    } else if (latest.status === 'RECOVERING') {
      doneStages = 3;
      timestamps = { injected: timeStr, detected: timeStr, decided: timeStr };
    } else if (latest.status === 'FAILED') {
      doneStages = 2;
      timestamps = { injected: timeStr, detected: timeStr };
    } else {
      doneStages = 1;
      timestamps = { injected: timeStr };
    }
  }

  return (
    <div className="card" style={{ gridColumn: '1 / -1' }}>
      <div className="section-title">
        Incident Timeline
        {latest && (
          <span style={{ marginLeft: 10, fontStyle: 'normal', color: 'var(--text-muted)', textTransform: 'none', letterSpacing: 0, fontWeight: 400 }}>
            · {latest.service} · <span className={`badge badge-${latest.status?.toLowerCase()}`} style={{ fontSize: 9 }}>{latest.status}</span>
          </span>
        )}
      </div>
      <div className="timeline-wrap">
        <div className="timeline-track">
          {STAGES.map((stage, i) => {
            const cls = getDotClass(stage.key, doneStages);
            return (
              <div key={stage.key} style={{ display: 'flex', alignItems: 'flex-start', flex: 1 }}>
                <div className="timeline-step">
                  <div
                    className={`timeline-dot ${cls}`}
                    style={cls === 'done' ? { background: STAGE_DOT_COLORS[stage.key], borderColor: STAGE_DOT_COLORS[stage.key], boxShadow: `0 0 8px ${STAGE_DOT_COLORS[stage.key]}` } : {}}
                  />
                  {stage.label.split('\n').map((l, j) => (
                    <span key={j} className="timeline-label" style={{ display: 'block' }}>{l}</span>
                  ))}
                  {timestamps[stage.key] && (
                    <span className="timeline-time">{timestamps[stage.key]}</span>
                  )}
                </div>
                {i < STAGES.length - 1 && (
                  <div
                    className={`timeline-connector ${i < doneStages - 1 ? 'active' : ''}`}
                    style={{ marginTop: 9, flex: 1, height: 2 }}
                  />
                )}
              </div>
            );
          })}
        </div>
        {!latest && (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', padding: '12px 0', fontStyle: 'italic' }}>
            No incidents yet — inject chaos to begin
          </div>
        )}
      </div>
    </div>
  );
}
