import { useEffect, useState } from 'react';
import { cleanupChaos, injectChaos } from '../api';

function formatScenarioLabel(value) {
  return value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export default function ChaosControls({
  onLog,
  serviceOptions = [],
  scenarioOptions = [],
}) {
  const [service, setService] = useState(serviceOptions[0] || '');
  const [scenario, setScenario] = useState(scenarioOptions[0] || '');
  const [loading, setLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);

  useEffect(() => {
    if (!serviceOptions.includes(service)) {
      setService(serviceOptions[0] || '');
    }
  }, [service, serviceOptions]);

  useEffect(() => {
    if (!scenarioOptions.includes(scenario)) {
      setScenario(scenarioOptions[0] || '');
    }
  }, [scenario, scenarioOptions]);

  const handleInject = async () => {
    if (!service || !scenario) {
      return;
    }

    setLoading(true);
    onLog({ level: 'chaos', msg: `Injecting [${scenario}] into ${service}...` });

    try {
      const res = await injectChaos(service, scenario);
      onLog({
        level: 'chaos',
        msg: `Chaos injected -> ${service} (${scenario}) - ${res.message || 'OK'}`,
      });
    } catch (e) {
      onLog({ level: 'anomaly', msg: `Chaos inject failed: ${e.message}` });
    } finally {
      setLoading(false);
    }
  };

  const handleCleanup = async () => {
    setCleaning(true);
    onLog({ level: 'info', msg: 'Running chaos cleanup...' });

    try {
      await cleanupChaos();
      onLog({ level: 'recover', msg: 'All chaos experiments cleaned up.' });
    } catch (e) {
      onLog({ level: 'anomaly', msg: `Cleanup failed: ${e.message}` });
    } finally {
      setCleaning(false);
    }
  };

  return (
    <div className="card" style={{ gridColumn: '1 / -1' }}>
      <div className="section-title">Chaos Controls</div>
      <div className="chaos-controls">
        <div className="form-group">
          <label className="form-label">Service</label>
          <select value={service} onChange={(e) => setService(e.target.value)}>
            {serviceOptions.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Scenario</label>
          <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
            {scenarioOptions.map((value) => (
              <option key={value} value={value}>
                {formatScenarioLabel(value)}
              </option>
            ))}
          </select>
        </div>
        <button
          className="btn btn-danger"
          onClick={handleInject}
          disabled={loading || !service || !scenario}
        >
          {loading ? 'Injecting...' : 'Inject Chaos'}
        </button>
        <button className="btn btn-outline" onClick={handleCleanup} disabled={cleaning}>
          {cleaning ? 'Cleaning...' : 'Cleanup All'}
        </button>
      </div>
    </div>
  );
}
