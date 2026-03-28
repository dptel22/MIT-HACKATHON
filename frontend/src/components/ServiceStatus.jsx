function getBadgeClass(state) {
  switch (state) {
    case 'HEALED':   return 'badge-healed';
    case 'HEALTHY':  return 'badge-healthy';
    case 'WATCHING': return 'badge-watching';
    case 'ANOMALY':  return 'badge-anomaly';
    case 'FAILED':   return 'badge-anomaly';
    case 'RECOVERING': return 'badge-circuit';
    case 'CIRCUIT_BROKEN': return 'badge-circuit';
    case 'COOLDOWN': return 'badge-cooldown';
    default:         return 'badge-watching';
  }
}

export default function ServiceStatus({ services, onSelectService, selectedService }) {
  return (
    <div className="card">
      <div className="section-title">Service Status</div>
      <div className="service-list">
        {Object.entries(services).map(([name, svcState]) => {
          let status = 'HEALTHY';
          if (svcState.is_anomaly && svcState.confidence >= 80) status = 'ANOMALY';
          else if (svcState.is_anomaly) status = 'WATCHING';

          // If backend returned a recovery status for this service, use it
          if (svcState._status) status = svcState._status;

          // Format Cooldown label
          let statusLabel = status;
          if (status === 'RECOVERING') {
            statusLabel = 'RECOVERING';
          } else if (status === 'CIRCUIT_BROKEN' && svcState.cooldown > 0) {
            statusLabel = `CIRCUIT BROKEN: ${Math.floor(svcState.cooldown)}s`;
          } else if (status === 'COOLDOWN' && svcState.cooldown > 0) {
            statusLabel = `COOLDOWN: ${Math.floor(svcState.cooldown)}s`;
          }

          return (
            <div
              key={name}
              className="service-row"
              style={selectedService === name ? { borderColor: 'rgba(56,189,248,0.5)', background: 'rgba(56,189,248,0.05)' } : {}}
              onClick={() => onSelectService(name)}
              title="Click to view vote buffer & latency"
            >
              <span className="service-name">{name}</span>
              <span className={`badge ${getBadgeClass(status)}`}>{statusLabel}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
