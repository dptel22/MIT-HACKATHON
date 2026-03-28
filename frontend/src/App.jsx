import { useCallback, useEffect, useRef, useState } from 'react';
import './index.css';

import Header from './components/Header';
import StatCard from './components/StatCard';
import VoteBuffer from './components/VoteBuffer';
import ServiceStatus from './components/ServiceStatus';
import LatencyChart from './components/LatencyChart';
import IncidentHistory from './components/IncidentHistory';
import ChaosControls from './components/ChaosControls';

import {
  getConfig,
  getHealth,
  getIncidents,
  getWarmupStatus,
  recoverService,
  runDetect,
  startWarmup,
} from './api';

const POLL_MS = 2000;
const MAX_HISTORY = 10;

function ts() {
  return new Date().toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function makeInitialServices(serviceNames = []) {
  return Object.fromEntries(
    serviceNames.map((service) => [
      service,
      {
        votes: [],
        confidence: 0,
        is_anomaly: false,
        features: { p95_latency_ms: 0 },
        _status: 'HEALTHY',
      },
    ]),
  );
}

function makeInitialHistoryMap(serviceNames = []) {
  return Object.fromEntries(serviceNames.map((service) => [service, []]));
}

export default function App() {
  const [connected, setConnected] = useState(false);
  const [warmupDone, setWarmupDone] = useState(false);
  const [serviceList, setServiceList] = useState([]);
  const [chaosServices, setChaosServices] = useState([]);
  const [chaosScenarios, setChaosScenarios] = useState([]);
  const [autoChaos, setAutoChaos] = useState(false);
  const [services, setServices] = useState({});
  const [incidents, setIncidents] = useState([]);
  const [logs, setLogs] = useState([
    { time: ts(), level: 'info', msg: 'Dashboard initialised. Connecting to backend...' },
  ]);
  const [selected, setSelected] = useState('');
  const [historyMap, setHistoryMap] = useState({});

  const focusedSvc = services[selected] || {};
  const anomalyVotes = (focusedSvc.votes || []).filter((vote) => vote === 1).length;
  const totalVotes = (focusedSvc.votes || []).length;
  const confidence = focusedSvc.confidence || 0;
  const incidentCount = incidents.length;
  const latestIncident = incidents[0] || null;
  const globalStatus = services[selected]?._status || 'HEALTHY';

  const detectPollRef = useRef(null);
  const pendingRecover = useRef(new Set());

  const addLog = useCallback((entry) => {
    setLogs((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.msg === entry.msg) return prev;
      return [...prev.slice(-199), { time: ts(), ...entry }];
    });
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const runtimeConfig = await getConfig();
        const nextServices = runtimeConfig.services || [];

        setServiceList(nextServices);
        setChaosServices(runtimeConfig.chaos_services || []);
        setChaosScenarios(runtimeConfig.chaos_scenarios || []);
        setAutoChaos(runtimeConfig.auto_chaos === true);
        setServices(makeInitialServices(nextServices));
        setHistoryMap(makeInitialHistoryMap(nextServices));
        setSelected(nextServices[0] || '');

        await getHealth();
        setConnected(true);
        addLog({ level: 'info', msg: 'Backend connected.' });
      } catch (e) {
        setConnected(false);
        addLog({ level: 'anomaly', msg: `Backend unreachable: ${e.message}` });
        return;
      }

      try {
        await startWarmup();
        addLog({ level: 'info', msg: 'Warm-up started - baseline collection in progress...' });
      } catch {
        addLog({ level: 'info', msg: 'Warm-up already completed or skipped.' });
      }
    })();
  }, [addLog]);

  // Handle Warmup Polling properly outside of the once-per-mount effect
  useEffect(() => {
    if (!connected || warmupDone) return;

    const intervalId = setInterval(async () => {
      try {
        const { done } = await getWarmupStatus();
        if (done) {
          setWarmupDone(true);
          addLog({ level: 'recover', msg: 'Warm-up complete. Baseline fitted.' });
        }
      } catch {
        // ignore background errors
      }
    }, 1500);

    return () => clearInterval(intervalId);
  }, [connected, warmupDone, addLog]);

  useEffect(() => {
    if (!serviceList.length) {
      return;
    }

    if (!selected || !serviceList.includes(selected)) {
      setSelected(serviceList[0]);
    }
  }, [selected, serviceList]);

  useEffect(() => {
    if (!warmupDone || !serviceList.length) {
      return undefined;
    }

    let isPolling = true;

    const poll = async () => {
      if (!isPolling) return;
      try {
        const data = await runDetect();
        setConnected(true);
        if (data.error) {
          addLog({ level: 'info', msg: data.error });
          detectPollRef.current = setTimeout(poll, POLL_MS);
          return;
        }

        const backendServices = Object.keys(data);
        setServiceList((prev) => (
          prev.length === backendServices.length
          && prev.every((service, index) => service === backendServices[index])
            ? prev
            : backendServices
        ));

        setServices((prev) => {
          const next = { ...prev };
          Object.entries(data).forEach(([service, svcState]) => {
            const prevStatus = prev[service]?._status || 'HEALTHY';
            let newStatus = prevStatus;
            
            if (svcState.recovery_in_progress) {
              newStatus = 'RECOVERING';
            } else if (svcState.circuit_broken) {
              newStatus = 'CIRCUIT_BROKEN';
            } else if (svcState.cooldown && svcState.cooldown > 0) {
              newStatus = 'COOLDOWN';
            } else if (svcState.is_anomaly && svcState.confidence >= 80) {
              newStatus = 'ANOMALY';
            } else if (svcState.is_anomaly && svcState.confidence > 0) {
              newStatus = 'WATCHING';
            } else if (prevStatus !== 'FAILED' && prevStatus !== 'HEALED') {
              newStatus = 'HEALTHY';
            }

            next[service] = { ...svcState, _status: newStatus };
          });
          return next;
        });

        setHistoryMap((prev) => {
          const next = { ...prev };
          Object.entries(data).forEach(([service, svcState]) => {
            const latency = svcState.features?.p95_latency_ms ?? 0;
            const status = svcState.is_anomaly ? 'anomaly' : 'normal';
            const entry = { latency, status };
            next[service] = [...(prev[service] || []).slice(-(MAX_HISTORY - 1)), entry];
          });
          return next;
        });

        for (const [service, svcState] of Object.entries(data)) {
          const votes = svcState.votes || [];
          if (
            !svcState.is_anomaly
            || svcState.confidence < 80
            || pendingRecover.current.has(service)
            || svcState.recovery_in_progress
            || svcState.circuit_broken
            || (svcState.cooldown && svcState.cooldown > 0)
          ) {
            continue;
          }

          pendingRecover.current.add(service);
          addLog({ level: 'anomaly', msg: `Anomaly detected - ${service} (${svcState.confidence.toFixed(0)}%)` });
          addLog({
            level: 'info',
            msg: `Votes ${votes.filter((vote) => vote === 1).length}/${votes.length}. Confidence ${svcState.confidence.toFixed(0)}%. Acting.`,
          });

          (async () => {
            try {
              const res = await recoverService(service);
              if (res.status === 'skipped') {
                addLog({ level: 'info', msg: `Recovery skipped for ${service}: ${res.reason}` });
                pendingRecover.current.delete(service);
                return;
              }

              addLog({ level: 'recover', msg: `Restarted pod: ${res.pod_name || 'unknown'}` });

              if (res.status === 'HEALED') {
                addLog({ level: 'healed', msg: `HEALED - ${service}` });
                setServices((prev) => ({
                  ...prev,
                  [service]: { ...prev[service], _status: 'HEALED', is_anomaly: false },
                }));
                // Update latency history to tag it as recovered
                setHistoryMap((prev) => ({
                  ...prev,
                  [service]: [
                    ...(prev[service] || []).slice(-1).map((entry) => ({ ...entry, status: 'recovered' })),
                    ...(prev[service] || []).slice(0, -1),
                  ],
                }));
              } else if (res.status === 'FAILED') {
                addLog({ level: 'anomaly', msg: `Recovery FAILED for ${service}. Manual mode engaged.` });
                setServices((prev) => ({
                  ...prev,
                  [service]: { ...prev[service], _status: 'FAILED' },
                }));
              }

              const nextIncidents = await getIncidents();
              setIncidents(nextIncidents);
            } catch (e) {
              addLog({ level: 'anomaly', msg: `Recovery error for ${service}: ${e.message}` });
            } finally {
              pendingRecover.current.delete(service);
            }
          })();
        }
      } catch {
        setConnected(false);
      } finally {
        if (isPolling) {
          detectPollRef.current = setTimeout(poll, POLL_MS);
        }
      }
    };

    poll();

    return () => {
      isPolling = false;
      clearTimeout(detectPollRef.current);
    };
  }, [addLog, serviceList, warmupDone]);

  useEffect(() => {
    getIncidents().then(setIncidents).catch(() => {});
  }, []);

  const statusColors = {
    HEALED: 'var(--purple)',
    HEALTHY: 'var(--green)',
    WATCHING: 'var(--yellow)',
    ANOMALY: 'var(--red)',
    FAILED: 'var(--red)',
    COOLDOWN: 'var(--blue)',
    CIRCUIT_BROKEN: '#ff9900',
    RECOVERING: '#ff9900',
  };

  return (
    <div className="dashboard">
      <Header connected={connected} warmupDone={warmupDone} />

      <div className="main-grid">
        <div className="stat-row">
          <StatCard
            label="Confidence"
            value={`${confidence.toFixed(0)}%`}
            sub="threshold: 80%"
            valueStyle={{ color: confidence >= 80 ? 'var(--red)' : 'var(--blue)', fontSize: '2.4rem' }}
          />
          <StatCard
            label="Anomaly Votes"
            value={`${anomalyVotes} / ${totalVotes || 5}`}
            sub="window: 5"
          />
          <StatCard
            label="Status"
            value={globalStatus}
            sub={latestIncident?.service || selected || '--'}
            valueStyle={{ color: statusColors[globalStatus] || 'var(--text)', fontSize: '1.8rem', paddingTop: 6 }}
          />
          <StatCard
            label="Incidents"
            value={incidentCount}
            sub="all recorded"
          />
        </div>

        <VoteBuffer
          votes={focusedSvc.votes || []}
          confidence={confidence}
          service={selected}
        />

        <ServiceStatus
          services={services}
          onSelectService={setSelected}
          selectedService={selected}
        />

        <LatencyChart
          history={historyMap[selected] || []}
          service={selected}
        />

        <div className="card" style={{ overflow: 'hidden' }}>
          <div className="section-title">Action Log</div>
          <div className="action-log-wrap" style={{ maxHeight: 230 }}>
            {logs.map((entry, index) => (
              <div className="log-entry" key={index}>
                <span className="log-time">{entry.time}</span>
                <span className={`log-msg-${entry.level || 'info'}`}>{entry.msg}</span>
              </div>
            ))}
          </div>
        </div>

        <ChaosControls
          onLog={addLog}
          serviceOptions={chaosServices}
          scenarioOptions={chaosScenarios}
          autoChaos={autoChaos}
          setAutoChaos={setAutoChaos}
        />

        <IncidentHistory incidents={incidents} />
      </div>
    </div>
  );
}
