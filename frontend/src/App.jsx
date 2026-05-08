import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');

    ws.onopen = () => setConnected(true);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      setData(message);
    };

    ws.onerror = (error) => console.error('WebSocket error:', error);
    ws.onclose = () => setConnected(false);

    return () => ws.close();
  }, []);

  if (!data) {
    return (
      <div className="loading">
        APEX BOT INITIALIZING...
        <div className="loading-sub">{connected ? 'Connected — waiting for data' : 'Connecting to ws://localhost:8000/ws'}</div>
      </div>
    );
  }

  const fmt = (num) => Math.round(num * 100) / 100;

  return (
    <div className="apex-dashboard">

      {/* Account Panel */}
      <div className="panel account-panel">
        <div className="panel-header">APEX BOT v1 — MULTI-STRATEGY</div>
        <div className="metric">
          <span>Balance</span>
          <span className="value">${fmt(data.live_data.balance)}</span>
        </div>
        <div className="metric">
          <span>P&amp;L</span>
          <span className={`value ${data.live_data.pnl >= 0 ? 'positive' : 'negative'}`}>
            ${fmt(data.live_data.pnl)}
          </span>
        </div>
        <div className="metric">
          <span>Win Rate</span>
          <span className="value">{data.live_data.win_rate}%</span>
        </div>
        <div className="metric">
          <span>WS Status</span>
          <span className={`value ${connected ? 'positive' : 'negative'}`}>
            {connected ? 'LIVE' : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      {/* Cycle Panel */}
      <div className="panel cycle-panel">
        <div className="cycle-counter">LIVE CYCLE #{data.cycle}</div>
        <div className="signal-badge" data-signal={data.trinity.signal}>
          {data.trinity.signal}
        </div>
        <div className="signal-status">
          <div>Models voting BUY: {data.trinity.buy_votes} / 10</div>
          <div>Avg Confidence: {Math.round(data.trinity.confidence * 100)}%</div>
        </div>
        <div className="vote-grid">
          {data.trinity.model_votes.map((v, i) => (
            <div key={i} className={`vote-dot ${v ? 'buy' : 'sell'}`} title={`Model ${i + 1}: ${v ? 'BUY' : 'SELL'}`} />
          ))}
        </div>
      </div>

      {/* Kelly Panel */}
      <div className="panel kelly-panel">
        <div className="panel-header">KELLY POSITION SIZING</div>
        <div className="metric">
          <span>Position Size</span>
          <span className="value">${fmt(data.kelly_size)}</span>
        </div>
        <div className="metric">
          <span>% of Capital</span>
          <span className="value">
            {fmt((data.kelly_size / data.live_data.balance) * 100)}%
          </span>
        </div>
        <div className="metric">
          <span>Max Allowed</span>
          <span className="value">${fmt(data.live_data.balance * 0.05)}</span>
        </div>
      </div>

      {/* Arbitrage Panel */}
      <div className="panel arb-panel">
        <div className="panel-header">ARBITRAGE DETECTOR</div>
        {data.arbitrage.opportunity ? (
          <>
            <div className="metric">
              <span>Spread</span>
              <span className="value positive">{Math.round(data.arbitrage.spread * 100)}%</span>
            </div>
            <div className="metric">
              <span>Action</span>
              <span className="value">{data.arbitrage.action}</span>
            </div>
            <div className="metric">
              <span>Profit Est.</span>
              <span className="value positive">${fmt(data.arbitrage.profit_potential)}</span>
            </div>
          </>
        ) : (
          <div className="no-opportunity">
            <div className="metric">
              <span>Status</span>
              <span className="value">Scanning...</span>
            </div>
            <div className="metric">
              <span>Threshold</span>
              <span className="value">8% spread</span>
            </div>
          </div>
        )}
      </div>

      {/* Performance Panel */}
      <div className="panel full-width perf-panel">
        <div className="panel-header">PERFORMANCE BREAKDOWN</div>
        <div className="perf-grid">
          {[
            { label: 'Trinity Bot', key: 'trinity' },
            { label: 'Copy Trading', key: 'copy' },
            { label: 'Discovered', key: 'discovered' },
          ].map(({ label, key }) => {
            const s = data.live_data.performance[key];
            const wr = Math.round((s.wins / (s.wins + s.losses)) * 100);
            return (
              <div className="strategy-stat" key={key}>
                <div className="stat-label">{label}</div>
                <div className="stat-value">{s.wins}W / {s.losses}L</div>
                <div className="stat-winrate">{wr}% win rate</div>
                <div className="stat-value positive">+${s.pnl.toLocaleString()}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Alerts Panel */}
      <div className="panel alerts-panel full-width">
        <div className="panel-header">REAL-TIME ALERTS</div>
        <div className="alert-item">
          {data.trinity.buy_votes} / 10 models agree &mdash; Confidence {Math.round(data.trinity.confidence * 100)}% &mdash; Signal: {data.trinity.signal}
        </div>
        <div className="alert-item">
          Cycle #{data.cycle} &mdash; Monitoring Kalshi + Polymarket &mdash; {new Date(data.timestamp).toLocaleTimeString()}
        </div>
        <div className="alert-item">
          Kelly Position: ${fmt(data.kelly_size)} &mdash; Arbitrage: {data.arbitrage.opportunity ? `OPPORTUNITY — ${data.arbitrage.action}` : 'No opportunity'}
        </div>
      </div>

    </div>
  );
}

export default App;
