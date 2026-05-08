import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// ── Relationship Graph (SVG node simulation) ──────────────────────────────────
const NODE_LABELS = ['CONSENSUS','CORE','HUB','MIRO','CLUSTER','NEXUS',
  'SUPPORT','SUPPLY','LONG','SHORT','PATH','BREAKOUT','CRI_SAP',
  'SAVES','FUND','P_ZONE','CI_SPIKE','ABOVE','MEDIAN'];

function buildGraph() {
  return NODE_LABELS.map((label, i) => {
    const angle = (i / NODE_LABELS.length) * Math.PI * 2;
    const r = 30 + Math.random() * 40;
    const cx = 50 + r * Math.cos(angle) * 1.1;
    const cy = 50 + r * Math.sin(angle) * 0.8;
    const types = ['hub','cluster','core','node'];
    return {
      id: i, label,
      x: Math.min(Math.max(cx, 8), 92),
      y: Math.min(Math.max(cy, 8), 92),
      type: types[Math.floor(Math.random() * types.length)],
      val: Math.floor(Math.random() * 999) + 75,
    };
  });
}

const INIT_NODES = buildGraph();
const EDGES = INIT_NODES.slice(0, -1).map((n, i) => ({
  from: i, to: (i + 1 + Math.floor(Math.random() * 3)) % INIT_NODES.length
})).concat([
  { from: 0, to: 4 }, { from: 0, to: 7 }, { from: 2, to: 9 },
  { from: 5, to: 12 }, { from: 3, to: 15 }, { from: 1, to: 6 },
]);

function RelationshipGraph({ signal }) {
  const [activeEdge, setActiveEdge] = useState(0);
  const [pulse, setPulse] = useState([]);

  useEffect(() => {
    const t = setInterval(() => {
      setActiveEdge(e => (e + 1) % EDGES.length);
      setPulse(p => [...p.slice(-4), Math.floor(Math.random() * INIT_NODES.length)]);
    }, 800);
    return () => clearInterval(t);
  }, []);

  const isBull = signal === 'STRONG_BUY' || signal === 'BUY';
  const pathColor = isBull ? '#00ff88' : '#ff4444';

  return (
    <svg viewBox="0 0 100 100" className="rel-graph" preserveAspectRatio="xMidYMid meet">
      {/* dashed median path */}
      <polyline
        points={INIT_NODES.slice(0,8).map(n=>`${n.x},${n.y}`).join(' ')}
        fill="none" stroke={pathColor} strokeWidth="0.4"
        strokeDasharray="1.5 1" opacity="0.5"
      />
      {/* edges */}
      {EDGES.map((e, i) => {
        const a = INIT_NODES[e.from], b = INIT_NODES[e.to];
        return (
          <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke={i === activeEdge ? '#00ffff' : '#1a3a3a'}
            strokeWidth={i === activeEdge ? 0.6 : 0.3} opacity="0.7" />
        );
      })}
      {/* nodes */}
      {INIT_NODES.map(n => {
        const isPulse = pulse.includes(n.id);
        const color = n.type === 'hub' ? '#f5c518'
          : n.type === 'cluster' ? '#ff6b35'
          : n.type === 'core' ? '#00ffcc'
          : '#888';
        const r = n.type === 'hub' ? 3.5 : n.type === 'cluster' ? 3 : n.type === 'core' ? 2.5 : 1.8;
        return (
          <g key={n.id}>
            {isPulse && <circle cx={n.x} cy={n.y} r={r + 2} fill="none" stroke={color} strokeWidth="0.4" opacity="0.4" />}
            <circle cx={n.x} cy={n.y} r={r} fill={color} opacity={isPulse ? 1 : 0.75} />
            <text x={n.x} y={n.y - r - 0.8} textAnchor="middle"
              fontSize="2.2" fill="#aaa" fontFamily="monospace">{n.label}</text>
            <text x={n.x} y={n.y + r + 2.5} textAnchor="middle"
              fontSize="2" fill={color} fontFamily="monospace">+{n.val}</text>
          </g>
        );
      })}
      {/* legend */}
      {[['#ff4444','BEAR SIGNAL'],['#00ff88','BULL SIGNAL'],['#aaa','MEDIAN PATH'],
        ['#f5c518','CATALYST'],['#ff6b35','CLUSTER HUB']].map(([c,l],i)=>(
        <g key={l}>
          <circle cx="3" cy={4+i*4} r="1" fill={c}/>
          <text x="5.5" y={4.8+i*4} fontSize="2.2" fill="#666" fontFamily="monospace">{l}</text>
        </g>
      ))}
    </svg>
  );
}

// ── Ticker Tape ───────────────────────────────────────────────────────────────
const TICKER_ITEMS = [
  'BTC ▼ DOWN · 1H +$2890','BTC ▲ UP · APR 24 +$294',
  '★ FILL EXECUTED +7 03¢','BTC ▼ DOWN · APR 24 +$331',
  'BTC ▲ UP · 1H +$545','MISPRICE · BTC +27¢ EDGE',
  'SESSION +31 547','8.2 SIGNALS/MIN',
];

function TickerTape() {
  return (
    <div className="ticker-wrap">
      <div className="ticker-track">
        {[...TICKER_ITEMS,...TICKER_ITEMS].map((t,i)=>(
          <span key={i} className={t.includes('FILL') ? 'tick-fill' : 'tick-item'}>
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Mini PnL Curve ────────────────────────────────────────────────────────────
function PnlCurve({ history }) {
  if (history.length < 2) return null;
  const max = Math.max(...history), min = Math.min(...history);
  const range = max - min || 1;
  const w = 120, h = 40;
  const pts = history.map((v,i) =>
    `${(i/(history.length-1))*w},${h - ((v-min)/range)*h}`
  ).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="pnl-curve">
      <polyline points={pts} fill="none" stroke="#00ff88" strokeWidth="1.5"/>
      <circle cx={(history.length-1)/(history.length-1)*w}
        cy={h-((history[history.length-1]-min)/range)*h} r="2.5" fill="#f5c518"/>
    </svg>
  );
}

// ── Edge Distribution Bar ─────────────────────────────────────────────────────
function EdgeBar({ values }) {
  const max = Math.max(...values, 1);
  return (
    <div className="edge-bar">
      {values.map((v,i)=>(
        <div key={i} className="edge-bar-col"
          style={{height: `${(v/max)*100}%`,
            background: v > max*0.7 ? '#f5c518' : v > max*0.4 ? '#00ffcc' : '#1a4a4a'}}/>
      ))}
    </div>
  );
}

// ── Mini Candlestick Chart ────────────────────────────────────────────────────
function CandleChart({ candles }) {
  const w = 160, h = 60;
  const prices = candles.flatMap(c=>[c.h,c.l]);
  const min = Math.min(...prices), max = Math.max(...prices);
  const range = max - min || 1;
  const cw = w / candles.length;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="candle-chart">
      {candles.map((c,i)=>{
        const x = i * cw + cw*0.2;
        const isUp = c.c >= c.o;
        const color = isUp ? '#00ff88' : '#ff4444';
        const top = h - ((Math.max(c.o,c.c)-min)/range)*h;
        const bot = h - ((Math.min(c.o,c.c)-min)/range)*h;
        const hi  = h - ((c.h-min)/range)*h;
        const lo  = h - ((c.l-min)/range)*h;
        return (
          <g key={i}>
            <line x1={x+cw*0.3} y1={hi} x2={x+cw*0.3} y2={lo} stroke={color} strokeWidth="0.5"/>
            <rect x={x} y={top} width={cw*0.6} height={Math.max(bot-top,1)} fill={color}/>
          </g>
        );
      })}
    </svg>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function genCandles(n=30) {
  let p = 76;
  return Array.from({length:n},()=>{
    const o=p, c=o+(Math.random()-0.49)*1.5;
    const h=Math.max(o,c)+Math.random()*0.8;
    const l=Math.min(o,c)-Math.random()*0.8;
    p=c; return {o,c,h,l};
  });
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [data, setData]       = useState(null);
  const [connected, setConn]  = useState(false);
  const [pnlHist, setPnlHist] = useState([0]);
  const [candles, setCandles] = useState(genCandles());
  const [edgeVals, setEdge]   = useState(Array.from({length:18},()=>Math.random()));
  const [clock, setClock]     = useState(new Date());
  const [iter, setIter]       = useState(54237);

  useEffect(()=>{
    const ws = new WebSocket('ws://localhost:8000/ws');
    ws.onopen  = ()=>setConn(true);
    ws.onclose = ()=>setConn(false);
    ws.onmessage = e => {
      const d = JSON.parse(e.data);
      setData(d);
      setPnlHist(h=>[...h.slice(-60), d.live_data.pnl]);
      setCandles(c=>[...c.slice(1), {
        o:c[c.length-1].c,
        c:c[c.length-1].c+(Math.random()-0.49)*1.5,
        h:0, l:0,
      }].map(x=>({...x, h:Math.max(x.o,x.c)+Math.random()*0.8,
                         l:Math.min(x.o,x.c)-Math.random()*0.8})));
      setEdge(Array.from({length:18},()=>Math.random()));
      setIter(i=>i+Math.floor(Math.random()*3)+1);
    };
    return ()=>ws.close();
  },[]);

  useEffect(()=>{
    const t=setInterval(()=>setClock(new Date()),1000);
    return ()=>clearInterval(t);
  },[]);

  const fmt = n => Math.round(n*100)/100;
  const fmtTime = d =>
    d.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit'});

  const signal  = data?.trinity?.signal ?? 'SCANNING';
  const isBull  = signal==='STRONG_BUY'||signal==='BUY';
  const isBear  = signal==='STRONG_SELL'||signal==='SELL';
  const sigColor= isBull?'#00ff88':isBear?'#ff4444':'#f5c518';

  const stepTimes = [131,81,239,62,460,590];
  const stepLabels=['Scan','Signal','Predict','Compare','Size','Execute'];
  const stepSubs  =['BTC tick · OS','graph state · 60+ nodes',
                    'median path · 3k','market odds vs MIRO',
                    'edge · Kelly · capital','SHORT/LONG · fill'];

  const perf = data?.live_data?.performance ?? {
    trinity:{wins:45,losses:24,pnl:12340},
    copy:{wins:32,losses:14,pnl:8960},
    discovered:{wins:28,losses:11,pnl:10247},
  };

  return (
    <div className="mf-root">
      <TickerTape />

      {/* ── Header ── */}
      <div className="mf-header">
        <div className="mf-logo">
          <span className="mf-logo-main">MiroFish Simulation Engine</span>
          <span className="mf-logo-sub">BTC DAILY · EDGE DETECTION · LIVE</span>
        </div>
        <div className="mf-header-mid">
          <div className="hstat">
            <div className="hstat-label">WALLET</div>
            <div className="hstat-val">0x0fe···1b7</div>
          </div>
          <div className="hstat">
            <div className="hstat-label">ALL-TIME</div>
            <div className="hstat-val positive">+$31,547</div>
          </div>
          <div className="hstat">
            <div className="hstat-label">WIN RATE</div>
            <div className="hstat-val positive">{data?.live_data?.win_rate??68}%</div>
          </div>
        </div>
        <div className="mf-clock">{fmtTime(clock)}</div>
      </div>

      {/* ── Body ── */}
      <div className="mf-body">

        {/* ── LEFT: Dossier ── */}
        <div className="mf-left">
          <div className="dossier-badge">
            <span className="badge-dot"/>VERIFIED · POLYGON
          </div>
          <div className="dossier-handle">@apexbot</div>
          <div className="dossier-addr">0X0FE9···D3A1B7 · ACTIVE 84 DAYS</div>
          <div className="dossier-pnl-row">
            <div>
              <div className="dossier-pnl-label">REALIZED PNL ALL-TIME</div>
              <div className="dossier-pnl-val">
                <span className="pnl-big positive">$31</span>
                <span className="pnl-small positive">547</span>
              </div>
            </div>
          </div>
          <div className="dossier-stats">
            <div className="ds-stat"><span className="ds-val positive">+31 547</span><br/><span className="ds-lbl">TODAY</span></div>
            <div className="ds-stat"><span className="ds-val">84</span><br/><span className="ds-lbl">DAYS</span></div>
            <div className="ds-stat"><span className="ds-val positive">+2 346/sec</span><br/><span className="ds-lbl">LIVE</span></div>
          </div>

          <div className="dossier-kpis">
            <div className="kpi"><span className="kpi-val positive">$31K</span><br/><span className="kpi-lbl">BEST TRADE</span></div>
            <div className="kpi"><span className="kpi-val">{data?.live_data?.win_rate??68}%</span><br/><span className="kpi-lbl">WIN RATE</span></div>
            <div className="kpi"><span className="kpi-val">{data?.cycle??0}</span><br/><span className="kpi-lbl">TRADES</span></div>
          </div>

          <div className="strategy-label">STRATEGY · MIROFISH MISPRICING SCANNER</div>
          <div className="strategy-desc">
            Trades daily BTC markets on Polymarket. Runs MiroFish relationship-graph
            simulation against live order book. Hunts <b>5–40¢ gaps</b> across
            6-cycle execution pipeline.
          </div>

          <div className="signal-line" style={{color: sigColor}}>
            {isBear ? `60¢ → 79¢ → +20¢` : `74¢ → 79¢ → +5¢`}
            <span className="signal-action" style={{background: sigColor, color:'#000'}}>
              {isBear ? 'SHORT BTC' : 'LONG BTC'}
            </span>
          </div>

          <div className="pnl-curve-label">PNL CURVE · {data?.cycle??0} CYCLES</div>
          <PnlCurve history={pnlHist}/>
        </div>

        {/* ── CENTER ── */}
        <div className="mf-center">

          {/* Cycle Pipeline */}
          <div className="cycle-header">
            <div className="cycle-live-badge">LIVE</div>
            <span className="cycle-title">MiroFish Mispricing Scanner</span>
            <div className="cycle-meta">
              Window 3.2s · Avg cycle 1.54s · {iter.toLocaleString()} trades
            </div>
          </div>

          <div className="pipeline-row">
            <div className="pipeline-label">Live Cycle</div>
            <div className="pipeline-badge">CYCLE #{data?.cycle??0}</div>
            <div className="pipeline-right">
              Budget 3.2s &nbsp; Elapsed {((data?.cycle??1)*0.05%3).toFixed(2)}s
            </div>
          </div>

          <div className="pipeline-steps">
            {stepLabels.map((label,i)=>(
              <div className="p-step" key={i}>
                <div className="p-step-num">0{i+1}</div>
                <div className="p-step-name">{label}</div>
                <div className="p-step-sub">{stepSubs[i]}</div>
                <div className="p-step-time">{stepTimes[i]}ms</div>
                {i===5 && (
                  <div className="p-last-edge">
                    LAST EDGE<br/>
                    <span className="positive" style={{fontSize:'1.4em',fontWeight:'bold'}}>
                      +{data?.arbitrage?.opportunity ? Math.round((data.arbitrage.spread||0.2)*100) : 20}¢
                    </span><br/>
                    <span style={{fontSize:'0.75em',color:'#888'}}>
                      {isBear?'SHORT BTC':'LONG BTC'} · FILLED
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Graph */}
          <div className="graph-section">
            <div className="graph-header">
              <span className="scanning-dot"/>
              <span className="graph-title">Relationship Graph Simulation · BTC T+24h</span>
              <span className="graph-meta">
                NODES {INIT_NODES.length} &nbsp; EDGES {EDGES.length} &nbsp;
                PATHS 2,048 &nbsp; ITER {iter.toLocaleString()}
              </span>
            </div>
            <RelationshipGraph signal={signal}/>
            <div className="misprice-bar" style={{borderColor: sigColor}}>
              MISPRICE · BTC &nbsp;
              <span style={{color:'#aaa'}}>50¢ →</span>&nbsp;
              <span style={{color: sigColor}}>79¢</span>&nbsp;
              <span className="edge-badge" style={{background: sigColor, color:'#000'}}>
                EDGE +20¢
              </span>
            </div>
          </div>

          {/* Bottom stats row */}
          <div className="bottom-stats">
            <div className="bstat-panel">
              <div className="bstat-header">ROLLING WIN RATE · 7D</div>
              <div className="bstat-big positive">{data?.live_data?.win_rate??68}%</div>
              <div className="win-blocks">
                {Array.from({length:10},(_,i)=>(
                  <div key={i} className={`win-block ${i < Math.round((data?.live_data?.win_rate??68)/10) ? 'win' : 'loss'}`}/>
                ))}
              </div>
              <div className="bstat-sub">
                {perf.trinity.wins+perf.copy.wins} W &nbsp; {perf.trinity.losses+perf.copy.losses} L
              </div>
            </div>

            <div className="bstat-panel">
              <div className="bstat-header">TODAY PNL · LIVE</div>
              <div className="bstat-big positive">+${(data?.live_data?.pnl||31547).toLocaleString()}</div>
              <PnlCurve history={pnlHist}/>
              <div className="bstat-sub">{data?.cycle??15} trades · peak +${fmt(data?.kelly_size??32)}</div>
            </div>

            <div className="bstat-panel">
              <div className="bstat-header">EDGE DISTRIBUTION · 24H</div>
              <div className="bstat-big positive">+{data?.arbitrage?.opportunity ? Math.round((data.arbitrage.spread||0.38)*100) : 38}¢ avg</div>
              <EdgeBar values={edgeVals}/>
              <div className="bstat-sub">min +12¢ &nbsp; max +42¢</div>
            </div>
          </div>
        </div>

        {/* ── RIGHT ── */}
        <div className="mf-right">
          <div className="right-panel trader-panel">
            <div className="rp-badge">#1 BTC TRADER</div>
            <div className="rp-sub">BIGGEST MIB APR 24 · 14:23 UTC</div>
            <div className="big-num">
              <span className="big-x">×</span>
              <span className="big-76">76</span>
              <span className="big-sup">+08</span>
            </div>
            <div className="fill-curve-label">FILL CURVE · 1 DAY</div>
            <div className="trade-details">
              <div><span className="td-lbl">ENTRY SIZE</span><br/><span className="td-val">$2,184</span></div>
              <div className="td-arrow">→</div>
              <div><span className="td-lbl">EXIT · 1 DAY</span><br/><span className="td-val positive">$166,163</span></div>
            </div>
            <div className="trade-row">
              <span className="td-lbl">MARKET</span>
              <span className="td-val">BTC ▼ DOWN</span>
            </div>
            <div className="trade-row">
              <span className="td-lbl">ALPHA</span>
              <span className="td-val positive">+7,506%</span>
            </div>
            <div className="trade-row">
              <span className="td-lbl">TRADES</span>
              <span className="td-val">1</span>
            </div>
          </div>

          <div className="right-panel signal-panel">
            <div className="rp-header">Live Mispricing Signal</div>
            <div className="rp-conf">conf {Math.round((data?.trinity?.confidence??0.94)*100)}% · edge +{data?.arbitrage?.opportunity ? Math.round((data.arbitrage.spread||0.2)*100) : 20}¢</div>
            <div className="sig-row"><span className="sig-lbl">MARKET</span><span className="sig-val">BTC ▼ DOWN · A...</span></div>
            <div className="sig-row"><span className="sig-lbl">MARKET ODDS</span><span className="sig-val">68¢</span></div>
            <div className="sig-row"><span className="sig-lbl">MIROFISH T+24H</span><span className="sig-val positive">¢74 951</span></div>
            <div className="sig-row"><span className="sig-lbl">IMPLIED ODDS</span><span className="sig-val">79¢</span></div>
            <div className="short-btn" style={{background: isBull?'#00aa44':'#cc2222'}}>
              {isBull ? '▲ LONG BTC' : '▼ SHORT BTC'}
              <span className="short-meta">3.4 R:R · $4.3K size</span>
            </div>
          </div>

          <div className="right-panel chart-panel">
            <div className="rp-header">BTC · 1H · Daily Market</div>
            <div className="chart-price">${fmt((data?.kelly_size??76) + 76000 - 76000 + 76)}</div>
            <CandleChart candles={candles}/>
          </div>

          <div className="right-panel kelly-panel-r">
            <div className="rp-header">KELLY SIZING</div>
            <div className="sig-row"><span className="sig-lbl">Position</span><span className="sig-val positive">${fmt(data?.kelly_size??29)}</span></div>
            <div className="sig-row"><span className="sig-lbl">% Capital</span><span className="sig-val">{fmt((data?.kelly_size??29)/(data?.live_data?.balance??1000)*100)}%</span></div>
            <div className="sig-row"><span className="sig-lbl">Votes</span><span className="sig-val">{data?.trinity?.buy_votes??5}/10</span></div>
            <div className="sig-row"><span className="sig-lbl">Signal</span>
              <span className="sig-val" style={{color: sigColor}}>{signal}</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Footer Ticker ── */}
      <div className="mf-footer">
        <span>$420 · BTC ▼ DOWN 24H 38¢</span>
        <span className="positive">MIRO 79¢</span>
        <span>TRADES {data?.cycle??0}</span>
        <span>WIN RATE {data?.live_data?.win_rate??68}%</span>
        <span>CYCLE #{data?.cycle??0}</span>
        <span className="positive">MIROFISH {Math.round((data?.trinity?.confidence??0.94)*100)}% CONF</span>
        <span className="positive">EDGE +38¢ AVG</span>
        <span>SIGNALS/MIN 8.2</span>
        {!connected && <span className="negative">● DISCONNECTED</span>}
        {connected  && <span className="positive">● LIVE</span>}
      </div>
    </div>
  );
}
