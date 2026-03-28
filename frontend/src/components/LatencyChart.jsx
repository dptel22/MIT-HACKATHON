import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer,
} from 'recharts';

const NORMAL_COLOR   = '#22c55e';
const ANOMALY_COLOR  = '#ef4444';
const RECOVER_COLOR  = '#f59e0b';

function getColor(entry) {
  if (entry.status === 'anomaly')   return ANOMALY_COLOR;
  if (entry.status === 'recovered') return RECOVER_COLOR;
  return NORMAL_COLOR;
}

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div style={{
        background: '#1a2030', border: '1px solid #242c3d',
        borderRadius: 6, padding: '8px 12px', fontSize: 11, fontFamily: 'var(--mono)',
      }}>
        <div style={{ color: '#7a8499' }}>Window {d.window}</div>
        <div style={{ color: getColor(d), fontWeight: 700 }}>{d.latency.toFixed(1)}ms</div>
        <div style={{ color: '#4a5568', textTransform: 'uppercase', fontSize: 10 }}>{d.status}</div>
      </div>
    );
  }
  return null;
};

export default function LatencyChart({ history, service }) {
  const data = history.map((h, i) => ({ window: i + 1, ...h }));

  return (
    <div className="card">
      <div className="section-title">P95 Latency (last {history.length} windows) · {service}</div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height="100%" minWidth={100} minHeight={200}>
          <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barCategoryGap="25%">
            <CartesianGrid strokeDasharray="3 3" stroke="#242c3d" vertical={false} />
            <XAxis dataKey="window" tick={{ fontSize: 10, fill: '#4a5568' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: '#4a5568' }} axisLine={false} tickLine={false} unit="ms" />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
            <Bar dataKey="latency" radius={[3, 3, 0, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getColor(entry)} opacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="chart-legend">
        <div className="legend-item"><div className="legend-dot" style={{ background: NORMAL_COLOR }} /><span>normal</span></div>
        <div className="legend-item"><div className="legend-dot" style={{ background: ANOMALY_COLOR }} /><span>anomaly</span></div>
        <div className="legend-item"><div className="legend-dot" style={{ background: RECOVER_COLOR }} /><span>recovered</span></div>
      </div>
    </div>
  );
}
