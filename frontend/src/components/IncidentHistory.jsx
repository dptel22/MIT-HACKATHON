import React from 'react';

export default function IncidentHistory({ incidents = [] }) {
  if (incidents.length === 0) {
    return (
      <div className="card" style={{ gridColumn: '1 / -1' }}>
        <div className="section-title">Incident History</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 13, textAlign: 'center', padding: '24px 0', fontStyle: 'italic' }}>
          No incidents recorded
        </div>
      </div>
    );
  }

  return (
    <div className="card" style={{ gridColumn: '1 / -1' }}>
      <div className="section-title">Incident History</div>
      <div style={{ overflowX: 'auto', maxHeight: '300px', overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontFamily: 'var(--font-mono)' }}>
          <thead style={{ position: 'sticky', top: 0, background: 'var(--surface)', zIndex: 1 }}>
            <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--neon-cyan)', fontSize: '11px', textTransform: 'uppercase' }}>
              <th style={{ padding: '8px 12px' }}>ID</th>
              <th style={{ padding: '8px 12px' }}>Time</th>
              <th style={{ padding: '8px 12px' }}>Service</th>
              <th style={{ padding: '8px 12px' }}>Conf %</th>
              <th style={{ padding: '8px 12px' }}>Votes</th>
              <th style={{ padding: '8px 12px' }}>Pod Name</th>
              <th style={{ padding: '8px 12px' }}>Action</th>
              <th style={{ padding: '8px 12px' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {incidents.map((inc) => {
              const ts = new Date(inc.timestamp * 1000).toLocaleTimeString('en-GB', {
                hour: '2-digit', minute: '2-digit', second: '2-digit'
              });
              
              const votesRaw = `[${(inc.votes || []).join(', ')}]`;
              
              return (
                <tr key={inc.id} style={{ borderBottom: '1px dashed var(--border)', fontSize: '13px', color: 'var(--text)' }}>
                  <td style={{ padding: '8px 12px', color: 'var(--text-dim)' }}>#{inc.id}</td>
                  <td style={{ padding: '8px 12px' }}>{ts}</td>
                  <td style={{ padding: '8px 12px', fontWeight: 'bold' }}>{inc.service}</td>
                  <td style={{ padding: '8px 12px', color: inc.confidence >= 80 ? 'var(--neon-red)' : 'var(--neon-cyan)' }}>
                    {inc.confidence?.toFixed(0)}%
                  </td>
                  <td style={{ padding: '8px 12px', letterSpacing: '2px', color: 'var(--text-muted)' }}>{votesRaw}</td>
                  <td style={{ padding: '8px 12px', color: 'var(--text-dim)' }}>{inc.pod_name || '--'}</td>
                  <td style={{ padding: '8px 12px' }}>{inc.action || '--'}</td>
                  <td style={{ padding: '8px 12px' }}>
                    <span className={`badge badge-${inc.status?.toLowerCase()}`} style={{ fontSize: '10px' }}>
                      {inc.status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
