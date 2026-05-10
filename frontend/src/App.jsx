import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

// ── Flash hook: fires CSS class on value change ───────────────────────────────
function useFlash(value) {
  const [flash, setFlash] = useState('');
  const prev = useRef(value);
  useEffect(() => {
    if (prev.current !== value) {
      const dir = value > prev.current ? 'flash-up' : 'flash-dn';
      setFlash(dir);
      const t = setTimeout(() => setFlash(''), 400);
      prev.current = value;
      return () => clearTimeout(t);
    }
  }, [value]);
  return flash;
}

// ── Num: tabular, flashing ────────────────────────────────────────────────────
function Num({ v, prefix = '', suffix = '', cls = '' }) {
  const flash = useFlash(v);
  const fmt = typeof v === 'number' ? v.toLocaleString('en-US', { maximumFractionDigits: 2 }) : v;
  return <span className={`num ${flash} ${cls}`}>{prefix}{fmt}{suffix}</span>;
}

// ── Ticker Tape ───────────────────────────────────────────────────────────────
const TICKS = [
  { t: 'BTC ▼ DOWN · 1H', v: '+$2890', hi: false },
  { t: 'BTC ▲ UP · APR 24', v: '+$294', hi: false },
  { t: '★ FILL EXECUTED +7', v: '03¢', hi: true },
  { t: 'BTC ▼ DOWN · APR 24', v: '+$331', hi: false },
  { t: 'BTC ▲ UP · 1H', v: '+$545', hi: false },
  { t: 'MISPRICE · BTC +27¢', v: 'EDGE', hi: true },
  { t: 'SESSION +31 547', v: '', hi: false },
  { t: '8.2 SIGNALS/MIN', v: '', hi: false },
];
function TickerTape() {
  const items = [...TICKS, ...TICKS];
  return (
    <div className="ticker">
      <div className="ticker-inner">
        {items.map((x, i) => (
          <span key={i} className={x.hi ? 'tick tick-hi' : 'tick'}>
            {x.t}{x.v ? <b> {x.v}</b> : ''}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── SVG Relationship Graph ────────────────────────────────────────────────────
const NODES = [
  { id:0,  lbl:'CONSENSUS', x:50, y:18, role:'hub'     },
  { id:1,  lbl:'CORE',      x:68, y:32, role:'core'    },
  { id:2,  lbl:'HUB',       x:75, y:50, role:'hub'     },
  { id:3,  lbl:'MIRO',      x:62, y:65, role:'core'    },
  { id:4,  lbl:'CLUSTER',   x:42, y:58, role:'cluster' },
  { id:5,  lbl:'NEXUS',     x:30, y:70, role:'node'    },
  { id:6,  lbl:'SUPPORT',   x:20, y:52, role:'node'    },
  { id:7,  lbl:'SUPPLY',    x:25, y:35, role:'node'    },
  { id:8,  lbl:'LONG',      x:55, y:42, role:'node'    },
  { id:9,  lbl:'SHORT',     x:38, y:28, role:'node'    },
  { id:10, lbl:'PATH',      x:15, y:68, role:'node'    },
  { id:11, lbl:'BREAKOUT',  x:82, y:68, role:'node'    },
  { id:12, lbl:'ABOVE',     x:70, y:20, role:'node'    },
  { id:13, lbl:'SAVES',     x:35, y:45, role:'node'    },
  { id:14, lbl:'FUND',      x:55, y:78, role:'node'    },
  { id:15, lbl:'CRI_SAP',   x:12, y:40, role:'node'    },
];
const EDGES = [
  [0,1],[0,7],[0,9],[1,2],[1,8],[2,3],[2,11],[3,4],[3,14],
  [4,5],[4,13],[5,10],[6,7],[6,13],[6,15],[7,9],[8,4],[8,3],[9,13],[11,3],
];
const MEDIAN = [0,9,13,4,3,2,11]; // dashed path

const NODE_COLOR = { hub:'#f5c518', core:'#00ffcc', cluster:'#ff6b35', node:'#555' };
const NODE_R     = { hub:4, core:3.5, cluster:3, node:2 };

function RelGraph({ signal }) {
  const [flares, setFlares] = useState([]);
  const [activeEdge, setActiveEdge] = useState(0);
  // slow drift offsets
  const [drift, setDrift] = useState(() => NODES.map(() => ({ dx:0, dy:0 })));
  const tick = useRef(0);

  useEffect(() => {
    const t = setInterval(() => {
      tick.current++;
      // drift
      setDrift(d => d.map(o => ({
        dx: o.dx + (Math.random() - 0.5) * 0.3,
        dy: o.dy + (Math.random() - 0.5) * 0.3,
      })));
      // edge pulse
      setActiveEdge(e => (e + 1) % EDGES.length);
      // occasional flare
      if (tick.current % 4 === 0) {
        const id = Math.floor(Math.random() * NODES.length);
        setFlares(f => [...f.filter(x => x.id !== id), { id, t: Date.now() }]);
        setTimeout(() => setFlares(f => f.filter(x => x.id !== id || Date.now() - x.t < 800)), 900);
      }
    }, 600);
    return () => clearInterval(t);
  }, []);

  const isBull = signal === 'STRONG_BUY' || signal === 'BUY';
  const pathCol = isBull ? '#00ff88' : '#ff4444';

  const nx = (n, i) => Math.min(Math.max(n.x + drift[i].dx, 5), 95);
  const ny = (n, i) => Math.min(Math.max(n.y + drift[i].dy, 5), 95);

  return (
    <svg viewBox="0 0 100 100" className="rel-graph" preserveAspectRatio="xMidYMid meet">
      {/* dim grid */}
      {[20,40,60,80].map(v=>(
        <g key={v}>
          <line x1={v} y1={0} x2={v} y2={100} stroke="#111" strokeWidth="0.3"/>
          <line x1={0} y1={v} x2={100} y2={v} stroke="#111" strokeWidth="0.3"/>
        </g>
      ))}
      {/* edges */}
      {EDGES.map(([a,b],i) => (
        <line key={i}
          x1={nx(NODES[a],a)} y1={ny(NODES[a],a)}
          x2={nx(NODES[b],b)} y2={ny(NODES[b],b)}
          stroke={i===activeEdge ? '#00ffcc' : '#1c2c2c'}
          strokeWidth={i===activeEdge ? 0.7 : 0.35} opacity="0.9"/>
      ))}
      {/* median dashed path */}
      <polyline
        points={MEDIAN.map(i=>`${nx(NODES[i],i)},${ny(NODES[i],i)}`).join(' ')}
        fill="none" stroke={pathCol} strokeWidth="0.5"
        strokeDasharray="2 1.2" opacity="0.7"/>
      {/* nodes */}
      {NODES.map((n,i) => {
        const cx = nx(n,i), cy = ny(n,i);
        const col = NODE_COLOR[n.role];
        const r   = NODE_R[n.role];
        const flt = flares.some(f=>f.id===n.id);
        return (
          <g key={n.id}>
            {flt && <circle cx={cx} cy={cy} r={r+4} fill="none" stroke={col} strokeWidth="0.5" opacity="0.5"/>}
            {flt && <circle cx={cx} cy={cy} r={r+2} fill="none" stroke={col} strokeWidth="0.3" opacity="0.3"/>}
            <circle cx={cx} cy={cy} r={r} fill={col} opacity={flt?1:0.8}/>
            <text x={cx} y={cy-r-1} textAnchor="middle" fontSize="2.2" fill="#777" fontFamily="monospace">{n.lbl}</text>
          </g>
        );
      })}
      {/* legend */}
      {[['#ff4444','BEAR SIGNAL'],['#00ff88','BULL SIGNAL'],['#888','MEDIAN PATH'],
        ['#f5c518','CATALYST'],['#ff6b35','CLUSTER HUB']].map(([c,l],i)=>(
        <g key={l}>
          <rect x="1" y={3+i*4.5} width="2" height="2" fill={c}/>
          <text x="4.5" y={4.8+i*4.5} fontSize="2.2" fill="#555" fontFamily="monospace">{l}</text>
        </g>
      ))}
    </svg>
  );
}

// ── PnL Area Chart ────────────────────────────────────────────────────────────
function PnlArea({ history, width = 120, height = 36 }) {
  if (history.length < 2) return <svg viewBox={`0 0 ${width} ${height}`} className="pnl-svg"/>;
  const min = Math.min(...history), max = Math.max(...history);
  const r = max - min || 1;
  const pts = history.map((v,i)=>[
    (i/(history.length-1))*width,
    height - ((v-min)/r)*(height-2) - 1
  ]);
  const poly = pts.map(p=>p.join(',')).join(' ');
  const area = `${pts[0][0]},${height} ` + poly + ` ${pts[pts.length-1][0]},${height}`;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="pnl-svg" preserveAspectRatio="none">
      <defs>
        <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00ff88" stopOpacity="0.35"/>
          <stop offset="100%" stopColor="#00ff88" stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={area} fill="url(#pnlGrad)"/>
      <polyline points={poly} fill="none" stroke="#00ff88" strokeWidth="1.2"/>
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="2" fill="#f5c518"/>
    </svg>
  );
}

// ── Candle chart ──────────────────────────────────────────────────────────────
function CandleChart({ candles }) {
  const W=140,H=52;
  const prices = candles.flatMap(c=>[c.h,c.l]);
  const mn=Math.min(...prices),mx=Math.max(...prices),rng=mx-mn||1;
  const cw = W/candles.length;
  const py = v => H - ((v-mn)/rng)*H;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="candle-svg" preserveAspectRatio="none">
      {candles.map((c,i)=>{
        const up = c.c >= c.o;
        const col = up ? '#00ff88' : '#ff4444';
        const x = i*cw + cw*0.15;
        return (
          <g key={i}>
            <line x1={x+cw*0.35} y1={py(c.h)} x2={x+cw*0.35} y2={py(c.l)} stroke={col} strokeWidth="0.4"/>
            <rect x={x} y={Math.min(py(c.o),py(c.c))} width={cw*0.7}
              height={Math.max(Math.abs(py(c.c)-py(c.o)),0.6)} fill={col}/>
          </g>
        );
      })}
    </svg>
  );
}

// ── Edge Dist bars ────────────────────────────────────────────────────────────
function EdgeDist({ vals }) {
  const mx = Math.max(...vals,1);
  return (
    <div className="edge-dist">
      {vals.map((v,i)=>(
        <div key={i} className="ed-col"
          style={{height:`${(v/mx)*100}%`,
            background: v>mx*.7?'#f5c518':v>mx*.4?'#00ffcc':'#1e3a3a'}}/>
      ))}
    </div>
  );
}

// ── Win blocks ────────────────────────────────────────────────────────────────
function WinBlocks({ rate }) {
  const filled = Math.round(rate / 10);
  return (
    <div className="win-blocks">
      {Array.from({length:10},(_,i)=>(
        <div key={i} className={`wb ${i<filled?'wb-on':''}`}/>
      ))}
    </div>
  );
}

// ── Candle generator ──────────────────────────────────────────────────────────
function genCandles(n=35) {
  let p=76;
  return Array.from({length:n},()=>{
    const o=p,c=o+(Math.random()-.49)*1.4;
    p=c;
    return {o,c,h:Math.max(o,c)+Math.random()*.7,l:Math.min(o,c)-Math.random()*.7};
  });
}

// ── Confirm modal ─────────────────────────────────────────────────────────────
function ConfirmModal({ side, size, onConfirm, onCancel }) {
  return (
    <div className="modal-overlay">
      <div className="modal">
        <div className="modal-title">CONFIRM ORDER</div>
        <div className="modal-row"><span>Action</span><span className={side==='SHORT'?'negative':'positive'}>{side} BTC</span></div>
        <div className="modal-row"><span>Size</span><span>${size}</span></div>
        <div className="modal-row"><span>R:R</span><span>3.4</span></div>
        <div className="modal-btns">
          <button className="modal-confirm" onClick={onConfirm}>CONFIRM</button>
          <button className="modal-cancel"  onClick={onCancel}>CANCEL</button>
        </div>
      </div>
    </div>
  );
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function Toast({ msg, onDone }) {
  useEffect(()=>{const t=setTimeout(onDone,2500);return()=>clearTimeout(t);},[]);
  return <div className="toast">{msg}</div>;
}

// ── Live YES-price mini chart ─────────────────────────────────────────────────
function MarketChart({ path, yesPrice, outcome }) {
  if (!path || path.length < 2) return null;
  const W = 100, H = 40;
  const mn = Math.min(...path, 0), mx = Math.max(...path, 1);
  const rng = mx - mn || 1;
  const pts = path.map((v, i) =>
    `${(i / (path.length - 1)) * W},${H - ((v - mn) / rng) * (H - 4) - 2}`
  ).join(' ');
  const col = outcome === 'YES' ? '#00e87a' : outcome === 'NO' ? '#e84040' : '#00d4b8';
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mkt-chart" preserveAspectRatio="none">
      <defs>
        <linearGradient id="mg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={col} stopOpacity="0.3"/>
          <stop offset="100%" stopColor={col} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={`0,${H} ${pts} ${W},${H}`} fill="url(#mg)"/>
      <polyline points={pts} fill="none" stroke={col} strokeWidth="1.2"/>
      {/* current price line */}
      <line x1="0" y1={H - ((yesPrice - mn) / rng) * (H - 4) - 2}
            x2={W} y2={H - ((yesPrice - mn) / rng) * (H - 4) - 2}
            stroke={col} strokeWidth="0.4" strokeDasharray="2 1" opacity="0.5"/>
    </svg>
  );
}

// ── Countdown display ─────────────────────────────────────────────────────────
function Countdown({ timeLeftMin }) {
  const total = Math.max(0, timeLeftMin);
  const m = Math.floor(total);
  const s = Math.floor((total - m) * 60);
  return (
    <span className="mkt-countdown">
      {String(m).padStart(2,'0')}:{String(s).padStart(2,'0')}
    </span>
  );
}

// ── Paper Trading Panel ───────────────────────────────────────────────────────
const STRATEGIES = ['MiroFish Consensus','Temporal Arbitrage','Copy Trading','Kelly Only','Manual'];
const SPEEDS     = [1, 10, 100];

function PaperPanel({ onClose }) {
  const [side,      setSide]     = useState('YES');
  const [sizeUsd,   setSizeUsd]  = useState('500');
  const [strategy,  setStrategy] = useState('MiroFish Consensus');
  const [duration,  setDuration] = useState(5);
  const [speed,     setSpeed]    = useState(10);
  const [queueCount,setQueue]    = useState(1);
  const [busy,      setBusy]     = useState(false);
  const [msg,       setMsg]      = useState('');
  const [autoOn,    setAutoOn]   = useState(false);
  const [paper,     setPaper]    = useState(null);
  const prevHistLen = useRef(0);
  const [newTrade,  setNewTrade] = useState(false);

  // Independent polling — doesn't rely on WebSocket
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch('http://localhost:8000/api/paper/snapshot');
        if (r.ok) {
          const d = await r.json();
          setPaper(d);
          setAutoOn(d.auto_trade ?? false);
          const len = d.history?.length ?? 0;
          if (len > prevHistLen.current) {
            setNewTrade(true);
            setTimeout(() => setNewTrade(false), 800);
            prevHistLen.current = len;
          }
        }
      } catch {}
    };
    poll();
    const id = setInterval(poll, 1000);
    return () => clearInterval(id);
  }, []);

  const notify = (m) => { setMsg(m); setTimeout(()=>setMsg(''),3500); };

  const startMarket = async () => {
    setBusy(true);
    try {
      const r = await fetch('http://localhost:8000/api/paper/market/start', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ duration_min: duration, speed, queue_count: queueCount }),
      });
      const d = await r.json();
      if (d.market_id) notify(`✓ BTC ${duration}MIN MARKET STARTED @ ${speed}x · "${d.name}"`);
      else notify('✗ ' + (d.error ?? 'error'));
    } catch { notify('✗ server error'); }
    setBusy(false);
  };

  const toggleAuto = async () => {
    const next = !autoOn;
    setAutoOn(next);
    await fetch('http://localhost:8000/api/paper/auto', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ enabled: next }),
    });
    notify(next ? '✓ AUTO-TRADER ON — MiroFish+Kelly firing trades' : '✓ AUTO-TRADER OFF');
  };

  const openTrade = async () => {
    setBusy(true);
    try {
      const r = await fetch('http://localhost:8000/api/paper/open', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ side, size_usd: parseFloat(sizeUsd), strategy }),
      });
      const d = await r.json();
      if (d.error) notify(`✗ ${d.error}`);
      else notify(`✓ ${side} @ ${(d.entry_price*100).toFixed(1)}¢ · ${d.contracts?.toFixed(2)} contracts · ${strategy}`);
    } catch { notify('✗ server error'); }
    setBusy(false);
  };

  const closeTrade = async (id) => {
    const r = await fetch(`http://localhost:8000/api/paper/close/${id}`, { method:'POST' });
    const d = await r.json();
    if (d.pnl !== undefined)
      notify(`✓ CLOSED #${id} · PNL ${d.pnl>=0?'+':''}$${d.pnl?.toFixed(2)}`);
  };

  const resetAll = async () => {
    await fetch('http://localhost:8000/api/paper/reset', { method:'POST' });
    notify('✓ PAPER ACCOUNT RESET · $10,000');
  };

  const mkt       = paper?.market;
  const positions = paper?.positions ?? [];
  const history   = (paper?.history ?? []).slice(-15).reverse();
  const totalPnl  = paper?.total_pnl ?? 0;
  const wr        = paper?.win_rate ?? 0;
  const balance   = paper?.balance ?? 10000;
  const queueLen  = paper?.queue_len ?? 0;
  const hasMarket = mkt && !mkt.resolved;
  const mktColor  = mkt?.outcome==='YES' ? '#00e87a' : mkt?.outcome==='NO' ? '#e84040' : '#00d4b8';

  return (
    <div className="paper-overlay">
      <div className="paper-panel">

        {/* ── header ── */}
        <div className="pp-header">
          <span className="pp-badge">PAPER</span>
          <span className="pp-title">PAPER TRADING · TIME-COMPRESSED STRATEGY TESTER</span>
          <button className="pp-close" onClick={onClose}>✕ CLOSE</button>
        </div>

        {/* ── account summary bar ── */}
        <div className="pp-summary">
          {[
            ['BALANCE',   `$${balance.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`],
            ['TOTAL PNL', `${totalPnl>=0?'+':''}$${totalPnl.toFixed(2)}`],
            ['WIN RATE',  `${wr}%`],
            ['OPEN',      positions.length],
            ['CLOSED',    paper?.history?.length ?? 0],
            ['QUEUED',    queueLen],
          ].map(([l,v],i)=>(
            <div className="pp-stat" key={l}>
              <div className="pp-sl">{l}</div>
              <div className={`pp-sv num ${l==='TOTAL PNL'?(totalPnl>=0?'positive':'negative'):''}`}>{v}</div>
            </div>
          ))}
          <button className="pp-reset" onClick={resetAll}>RESET</button>
        </div>

        <div className="pp-body">

          {/* ── LEFT: market setup + order form ── */}
          <div className="pp-form-col">

            {/* market controls */}
            <div className="panel-label">MARKET SETUP</div>
            <div className="pp-row-label">BTC MARKET DURATION</div>
            <div className="pp-seg">
              {[5, 15].map(d=>(
                <button key={d} className={`pp-seg-btn ${duration===d?'pp-seg-on':''}`}
                  onClick={()=>setDuration(d)}>{d} MIN</button>
              ))}
            </div>

            <div className="pp-row-label">SPEED MULTIPLIER</div>
            <div className="pp-seg">
              {SPEEDS.map(s=>(
                <button key={s} className={`pp-seg-btn ${speed===s?'pp-seg-on':''}`}
                  onClick={()=>setSpeed(s)}>{s}×</button>
              ))}
            </div>
            <div className="pp-speed-hint">
              At {speed}×: {duration}min market resolves in{' '}
              <b>{speed===1?`${duration} min`:speed===10?`${duration*6} sec`:`${Math.round(duration*60/speed)} sec`}</b>
            </div>

            <div className="pp-row-label">AUTO-QUEUE (markets back-to-back)</div>
            <div className="pp-seg">
              {[1,3,5,10].map(n=>(
                <button key={n} className={`pp-seg-btn ${queueCount===n?'pp-seg-on':''}`}
                  onClick={()=>setQueue(n)}>{n}</button>
              ))}
            </div>

            <button className="pp-start-mkt" onClick={startMarket} disabled={busy}>
              {busy ? 'STARTING…' : hasMarket ? '↺ NEW MARKET' : '▶ START BTC MARKET'}
            </button>

            {/* auto-trader toggle */}
            <button className={`pp-auto-btn ${autoOn ? 'pp-auto-on' : ''}`} onClick={toggleAuto}>
              <span>{autoOn ? '● AUTO-TRADER ACTIVE' : '○ AUTO-TRADER OFF'}</span>
              <span className="pp-auto-sub">MiroFish + Kelly sizing</span>
            </button>

            {/* auto log */}
            {paper?.auto_log?.length > 0 && (
              <div className="pp-auto-log">
                {paper.auto_log.slice(0,5).map((l,i)=>(
                  <div key={i} className={`pp-log-row ${l.msg.startsWith('TRADE')?'pp-log-trade':l.msg.startsWith('ERROR')?'pp-log-err':'pp-log-skip'}`}>
                    {l.msg}
                  </div>
                ))}
              </div>
            )}

            {/* manual order form */}
            <div className="panel-label" style={{marginTop:6}}>MANUAL ORDER</div>
            <div className="pp-side-toggle">
              <button className={`pst-btn ${side==='YES'?'pst-long':''}`}  onClick={()=>setSide('YES')}>▲ BUY YES</button>
              <button className={`pst-btn ${side==='NO'?'pst-short':''}`}  onClick={()=>setSide('NO')}>▼ BUY NO</button>
            </div>

            <div className="pp-quick">
              {[100,250,500,1000].map(v=>(
                <button key={v} className="pp-quick-btn" onClick={()=>setSizeUsd(String(v))}>
                  ${v}
                </button>
              ))}
            </div>
            <input className="pp-input" type="number" value={sizeUsd}
              onChange={e=>setSizeUsd(e.target.value)} min="10" step="50"/>

            <div className="pp-field">
              <label className="pp-label">STRATEGY</label>
              <select className="pp-input" value={strategy} onChange={e=>setStrategy(e.target.value)}>
                {STRATEGIES.map(s=><option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <button className={`pp-execute ${side==='YES'?'pp-long':'pp-short'}`}
              onClick={openTrade} disabled={busy || !hasMarket}>
              {!hasMarket ? 'START A MARKET FIRST' : busy ? 'PLACING…' : `PAPER ${side} · $${sizeUsd}`}
            </button>

            {msg && <div className={`pp-msg ${msg.startsWith('✓')?'pp-msg-ok':'pp-msg-err'}`}>{msg}</div>}
          </div>

          {/* ── CENTER: live market view ── */}
          <div className="pp-market-col">
            <div className="panel-label">LIVE MARKET</div>
            {!mkt
              ? <div className="pp-empty pp-empty-lg">No market running — click START MARKET</div>
              : (
                <>
                  <div className="mkt-name">{mkt.name}</div>
                  <div className="mkt-status-row">
                    {mkt.resolved
                      ? <span className="mkt-resolved" style={{color: mktColor}}>
                          RESOLVED · {mkt.outcome} · {(mkt.final_price*100).toFixed(1)}¢
                        </span>
                      : <span className="mkt-live-dot">● LIVE</span>
                    }
                    <span className="mkt-speed">{mkt.speed}× SPEED</span>
                    {queueLen > 0 && <span className="mkt-queue">{queueLen} QUEUED</span>}
                  </div>

                  {/* big price display */}
                  <div className="mkt-prices">
                    <div className={`mkt-price-box ${side==='YES'?'mpb-sel':''}`} onClick={()=>setSide('YES')}>
                      <div className="mkt-price-lbl">YES</div>
                      <div className="mkt-price-val positive">{(mkt.yes_price*100).toFixed(1)}¢</div>
                    </div>
                    <div className={`mkt-price-box ${side==='NO'?'mpb-sel':''}`} onClick={()=>setSide('NO')}>
                      <div className="mkt-price-lbl">NO</div>
                      <div className="mkt-price-val negative">{(mkt.no_price*100).toFixed(1)}¢</div>
                    </div>
                  </div>

                  {/* progress bar + countdown */}
                  <div className="mkt-timer-row">
                    <Countdown timeLeftMin={mkt.time_left_min}/>
                    <span className="mkt-timer-label">remaining of {mkt.duration_min}min</span>
                    <span className="mkt-speed-tag">{mkt.speed}×</span>
                  </div>
                  <div className="mkt-progress-bar">
                    <div className="mkt-progress-fill" style={{
                      width:`${mkt.progress*100}%`,
                      background: mkt.resolved ? mktColor : '#00d4b8'
                    }}/>
                  </div>

                  {/* price chart */}
                  <MarketChart path={mkt.price_path} yesPrice={mkt.yes_price} outcome={mkt.outcome}/>

                  {/* market stats */}
                  <div className="mkt-stats-row">
                    <div className="mkt-stat"><div className="mkt-sl">PROGRESS</div><div className="mkt-sv">{(mkt.progress*100).toFixed(1)}%</div></div>
                    <div className="mkt-stat"><div className="mkt-sl">DURATION</div><div className="mkt-sv">{mkt.duration_min} MIN</div></div>
                    <div className="mkt-stat"><div className="mkt-sl">OPEN POS.</div><div className="mkt-sv">{positions.filter(p=>p.market_id===mkt.market_id).length}</div></div>
                  </div>
                </>
              )
            }
          </div>

          {/* ── RIGHT: live trades table ── */}
          <div className="pp-right-col">

            {/* open positions — compact */}
            {positions.length > 0 && (
              <div className="pp-open-positions">
                <div className="open-pos-hdr">
                  <span>SIDE</span><span>ENTRY</span><span>SIZE</span><span>STRATEGY</span><span></span>
                </div>
                {positions.map(p=>(
                  <div className="open-pos-row" key={p.id}>
                    <span className={p.side==='YES'?'positive':'negative'}>{p.side}</span>
                    <span>{(p.entry_price*100).toFixed(1)}¢</span>
                    <span>${p.size_usd}</span>
                    <span className="trades-strat">{p.strategy.split(' ')[0]}</span>
                    <button className="pp-close-pos" onClick={()=>closeTrade(p.id)}>EXIT</button>
                  </div>
                ))}
              </div>
            )}

            {/* all trades history */}
            <div className={`trades-section-hdr ${newTrade ? 'trades-flash' : ''}`}>
              <span>TRADE HISTORY</span>
              <span className="trades-count">{paper?.history?.length ?? 0}</span>
              {(paper?.history?.length ?? 0) > 0 &&
                <span className={`wr-tag ${wr>=50?'positive':'negative'}`}>{wr}% WIN RATE</span>
              }
            </div>
            {history.length === 0
              ? <div className="pp-empty-trades">
                  <div className="pp-empty-icon">▷</div>
                  <div>No trades yet</div>
                  <div style={{fontSize:'9px',color:'#3a3a3a',marginTop:4}}>Start a market → enable AUTO-TRADER</div>
                </div>
              : <div className="trades-scroll">
                  <div className="hist-hdr">
                    <span>#</span><span>SIDE</span><span>ENTRY</span>
                    <span>SIZE</span><span>OUT</span><span>PNL</span>
                  </div>
                  {history.map(p=>{
                    const pnl = p.pnl ?? 0;
                    const won = pnl >= 0;
                    return (
                      <div className={`hist-row ${won ? 'hr-win' : 'hr-loss'}`} key={p.id}>
                        <span className="hr-id">#{p.id}</span>
                        <span className={p.side==='YES'?'positive':'negative'}>{p.side}</span>
                        <span className="hr-price">{(p.entry_price*100).toFixed(1)}¢</span>
                        <span className="hr-size">${p.size_usd}</span>
                        <span className={p.outcome==='YES'?'positive':'negative'}>{p.outcome??'—'}</span>
                        <span className={`hr-pnl ${won?'positive':'negative'}`}>
                          {won?'+':''}{pnl.toFixed(2)}
                        </span>
                      </div>
                    );
                  })}
                </div>
            }
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Live Kalshi Panel ─────────────────────────────────────────────────────────
function KalshiLivePanel({ onClose }) {
  const [data, setData] = useState(null);
  const [newTrade, setNewTrade] = useState(false);
  const prevCount = useRef(0);

  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch('http://localhost:8000/api/kalshi/dashboard');
        if (r.ok) {
          const d = await r.json();
          setData(d);
          const count = d.trade_history?.length ?? 0;
          if (count > prevCount.current) {
            setNewTrade(true);
            setTimeout(() => setNewTrade(false), 800);
            prevCount.current = count;
          }
        }
      } catch {}
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  if (!data) return null;

  const bal      = data.balance_usd ?? 0;
  const fills    = data.trade_history ?? [];
  const openPos  = data.open_positions ?? [];
  const slEvents = data.stop_loss_events ?? [];
  const stats    = data.stats ?? {};

  return (
    <div className="pp-overlay" onClick={onClose}>
      <div className="pp-panel" style={{maxWidth:760}} onClick={e=>e.stopPropagation()}>

        {/* header */}
        <div className="pp-header">
          <span className="pp-badge" style={{background:'#00ff88',color:'#000'}}>LIVE</span>
          <span className="pp-title">KALSHI LIVE · BTC 15-MIN MARKETS</span>
          <button className="pp-close" onClick={onClose}>✕ CLOSE</button>
        </div>

        {/* summary bar */}
        <div className="pp-summary">
          {[
            ['BALANCE',    `$${bal.toFixed(2)}`],
            ['TRADES',     stats.total_trades ?? 0],
            ['OPEN',       stats.open_count ?? 0],
            ['STOP LOSSES',stats.stop_losses ?? 0],
            ['TAKE PROFITS',stats.take_profits ?? 0],
            ['MONITOR',    data.monitor_active ? 'ON' : 'OFF'],
          ].map(([l,v])=>(
            <div className="pp-stat" key={l}>
              <div className="pp-sl">{l}</div>
              <div className={`pp-sv num ${l==='MONITOR'?(data.monitor_active?'positive':'negative'):''}`}>{v}</div>
            </div>
          ))}
        </div>

        <div className="pp-body">
          <div className="pp-right-col" style={{width:'100%'}}>

            {/* open positions */}
            {openPos.length > 0 && (
              <div className="pp-open-positions">
                <div className="panel-label" style={{marginBottom:6}}>OPEN POSITIONS — STOP LOSS WATCHING</div>
                <div className="open-pos-hdr">
                  <span>TICKER</span><span>SIDE</span><span>ENTRY</span><span>COST</span><span>STOP AT</span>
                </div>
                {openPos.map((p,i)=>(
                  <div className="open-pos-row" key={i}>
                    <span style={{fontSize:10,opacity:.7}}>{p.ticker?.split('-').slice(-1)[0]}</span>
                    <span className={p.side==='yes'?'positive':'negative'}>{p.side?.toUpperCase()}</span>
                    <span>{Math.round(p.entry_price*100)}¢</span>
                    <span>${p.entry_usd}</span>
                    <span className="negative">{Math.round(p.stop_at*100)}¢</span>
                  </div>
                ))}
              </div>
            )}

            {/* stop loss events */}
            {slEvents.length > 0 && (
              <div style={{marginBottom:12}}>
                <div className="panel-label" style={{marginBottom:6}}>STOP LOSS / TAKE PROFIT EVENTS</div>
                {slEvents.map((e,i)=>(
                  <div key={i} style={{fontSize:11,padding:'3px 0',borderBottom:'1px solid #ffffff08',display:'flex',gap:12}}>
                    <span className={e.reason?.includes('STOP')?'negative':'positive'}>
                      {e.reason?.includes('STOP') ? '⛔ SL' : '✅ TP'}
                    </span>
                    <span style={{opacity:.7}}>{e.ticker?.split('-').slice(-1)[0]}</span>
                    <span>{e.side?.toUpperCase()} @ {Math.round(e.entry_price*100)}¢ → {Math.round(e.exit_price*100)}¢</span>
                    <span className={e.net_loss_usd>0?'negative':'positive'}>
                      {e.net_loss_usd>0?`-$${e.net_loss_usd}`:`saved $${e.saved_usd}`}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* fills / trade history */}
            <div className={`trades-section-hdr ${newTrade?'trades-flash':''}`}>
              <span>LIVE FILL HISTORY</span>
              <span className="trades-count">{fills.length}</span>
            </div>
            {fills.length === 0
              ? <div className="pp-empty-trades">Waiting for first live trade to fill…</div>
              : <div className="trades-scroll">
                  <div className="hist-hdr">
                    <span>TICKER</span><span>SIDE</span><span>PRICE</span><span>CONTRACTS</span><span>COST</span>
                  </div>
                  {fills.map((f,i)=>(
                    <div className="hist-row" key={i}>
                      <span style={{fontSize:10}}>{f.ticker?.split('-').slice(-1)[0]}</span>
                      <span className={f.side==='yes'?'positive':'negative'}>{f.side?.toUpperCase()}</span>
                      <span>{Math.round(f.price*100)}¢</span>
                      <span>{f.count}</span>
                      <span>${f.cost}</span>
                    </div>
                  ))}
                </div>
            }
          </div>
        </div>
      </div>
    </div>
  );
}


// ── MAIN ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [data,    setData]    = useState(null);
  const [conn,    setConn]    = useState(false);
  const [pnlHist, setPnl]     = useState([0]);
  const [candles, setCandles] = useState(genCandles());
  const [edgeV,   setEdgeV]   = useState(()=>Array.from({length:20},()=>Math.random()));
  const [clock,   setClock]   = useState(new Date());
  const [modal,   setModal]   = useState(false);
  const [toast,   setToast]   = useState('');
  const [filling, setFilling] = useState(false);
  const [paperOpen, setPaperOpen] = useState(false);
  const [liveOpen,  setLiveOpen]  = useState(false);

  useEffect(()=>{
    const ws=new WebSocket('ws://localhost:8000/ws');
    ws.onopen=()=>setConn(true);
    ws.onclose=()=>setConn(false);
    ws.onmessage=e=>{
      const d=JSON.parse(e.data);
      setData(d);
      setPnl(h=>[...h.slice(-80), d.live_data.pnl||0]);
      setCandles(c=>{
        const last=c[c.length-1];
        const nc={o:last.c,c:last.c+(Math.random()-.49)*1.4};
        nc.h=Math.max(nc.o,nc.c)+Math.random()*.7;
        nc.l=Math.min(nc.o,nc.c)-Math.random()*.7;
        return [...c.slice(1),nc];
      });
      setEdgeV(Array.from({length:20},()=>Math.random()));
    };
    return()=>ws.close();
  },[]);

  useEffect(()=>{const t=setInterval(()=>setClock(new Date()),1000);return()=>clearInterval(t);},[]);

  const handleShort = () => setModal(true);
  const handleConfirm = () => {
    setModal(false);
    setFilling(true);
    setTimeout(()=>{
      setFilling(false);
      setToast('✓ ORDER FILLED · SHORT BTC · $4.3K');
    },1200);
  };

  const sig   = data?.trinity?.signal ?? 'SCANNING';
  const isBull= sig==='STRONG_BUY'||sig==='BUY';
  const conf  = Math.round((data?.trinity?.confidence??0.94)*100);
  const wr    = data?.live_data?.win_rate??78;
  const bal   = data?.live_data?.balance??1000;
  const cycle = data?.cycle??0;
  const ksize = data?.kelly_size??29.44;
  const perf  = data?.live_data?.performance??{trinity:{wins:45,losses:24,pnl:12340},copy:{wins:32,losses:14,pnl:8960},discovered:{wins:28,losses:11,pnl:10247}};

  const hhmm = clock.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit'});

  const stepLabels = ['Scan','Signal','Predict','Compare','Size','Execute'];
  const stepSubs   = ['BTC tick · OS','graph state · 60+ nodes','median path · 3k','market odds vs MIRO','edge · Kelly · capital','SHORT/LONG · fill'];
  const stepMs     = [131,81,239,62,460,590];

  return (
    <div className="root">
      {/* ── Ticker ── */}
      <TickerTape/>

      {/* ── Top Bar ── */}
      <header className="topbar">
        <div className="tb-brand">
          <span className="tb-tag">POLYMARKET · LIVE · @apexbot</span>
          <span className="tb-name">MiroFish Simulation Engine</span>
          <span className="tb-sub">BTC DAILY · EDGE DETECTION · LIVE</span>
        </div>
        <div className="tb-stats">
          {[['WALLET','0x0fe···1b7'],['ALL-TIME','+$369,000'],['BEST','+$166K'],['TRADES','1,262'],['WIN RATE',`${wr}%`],['CYCLE',`#${cycle}`]].map(([l,v])=>(
            <div className="tb-stat" key={l}>
              <div className="tb-sl">{l}</div>
              <div className="tb-sv">{v}</div>
            </div>
          ))}
        </div>
        <button className={`paper-toggle ${liveOpen?'pt-active':''}`}
          style={liveOpen?{background:'#00ff88',color:'#000'}:{background:'#ff3366',color:'#fff'}}
          onClick={()=>setLiveOpen(o=>!o)}>
          {liveOpen ? '● LIVE ON' : '● LIVE TRADES'}
        </button>
        <button className={`paper-toggle ${paperOpen?'pt-active':''}`} onClick={()=>setPaperOpen(o=>!o)}>
          {paperOpen ? '▣ PAPER MODE ON' : '▷ PAPER TRADE'}
        </button>
        <div className="tb-clock">{hhmm}</div>
      </header>

      {/* ── Body ── */}
      <div className="body">

        {/* LEFT */}
        <aside className="left-col">
          <div className="panel-label">ON-CHAIN DOSSIER</div>
          <div className="dossier-verified">
            <span className="dot dot-green"/>VERIFIED · POLYGON
          </div>
          <div className="dossier-handle">@apexbot</div>
          <div className="dossier-addr">0X0FE9···D3A1B7 · ACTIVE 84 DAYS</div>
          <div className="dossier-row3">
            <div className="dr3">
              <Num v={166} prefix="$" suffix="K" cls="positive dr3-big"/>
              <div className="dr3-lbl">BEST TRADE</div>
            </div>
            <div className="dr3">
              <Num v={wr} suffix="%" cls="dr3-big"/>
              <div className="dr3-lbl">WIN RATE</div>
            </div>
            <div className="dr3">
              <Num v={1262} cls="dr3-big"/>
              <div className="dr3-lbl">TRADES</div>
            </div>
          </div>

          <div className="panel-label" style={{marginTop:8}}>REALIZED PNL ALL-TIME</div>
          <div className="pnl-alltime">
            <Num v={385338} prefix="$" cls="positive pnl-big-num"/>
          </div>
          <div className="pnl-sub-row">
            <span className="positive">+$31,547 TODAY</span>
            <span className="dim">·</span>
            <span className="positive">+2 346/sec LIVE</span>
          </div>

          <div className="panel-label" style={{marginTop:8}}>STRATEGY</div>
          <div className="strategy-txt">
            MIROFISH MISPRICING SCANNER<br/>
            <span className="dim">Trades daily BTC markets on Polymarket. Runs MiroFish relationship-graph simulation against live order book. Hunts </span>
            <span className="positive">5–40¢ gaps</span>
            <span className="dim"> across 6-cycle execution pipeline.</span>
          </div>

          <div className="sig-eq">
            {isBull ? '74¢ → 79¢' : '60¢ → 79¢'}
            <span className="sig-arrow">=</span>
            <span className="positive">+{isBull?'5':'19'}¢</span>
          </div>

          <button
            className={`trade-btn ${isBull?'trade-btn-long':'trade-btn-short'} ${filling?'trade-btn-filling':''}`}
            onClick={handleShort}
            disabled={filling}
          >
            {filling ? 'FILLING…' : isBull ? '▲ LONG BTC' : '▼ SHORT BTC'}
          </button>

          <div className="panel-label" style={{marginTop:8}}>PNL CURVE</div>
          <PnlArea history={pnlHist} width={160} height={44}/>
        </aside>

        {/* CENTER */}
        <main className="center-col">
          {/* scanner header */}
          <div className="scanner-hdr">
            <span className="live-pill">LIVE</span>
            <span className="scanner-title">MiroFish Mispricing Scanner</span>
            <span className="scanner-meta">Window 3.2s · Avg cycle 1.54s · {(1200+cycle).toLocaleString()} trades</span>
          </div>

          {/* cycle row */}
          <div className="cycle-row">
            <span className="cycle-lbl">Live Cycle</span>
            <span className="cycle-badge">CYCLE #{cycle}</span>
            <span className="cycle-right">Budget 3.2s &nbsp; Elapsed {((cycle*0.05)%3).toFixed(2)}s</span>
          </div>

          {/* pipeline */}
          <div className="pipeline">
            {stepLabels.map((lbl,i)=>(
              <div className="p-step" key={i}>
                <div className="p-n">0{i+1}</div>
                <div className="p-lbl">{lbl}</div>
                <div className="p-sub">{stepSubs[i]}</div>
                <div className="p-ms">{stepMs[i]}ms</div>
                {i===5 &&
                  <div className="p-edge">
                    LAST EDGE<br/>
                    <span className="positive p-edge-val">+{data?.arbitrage?.opportunity?Math.round((data.arbitrage.spread||.2)*100):20}¢</span><br/>
                    <span className="dim" style={{fontSize:'0.72em'}}>{isBull?'LONG BTC':'SHORT BTC'} · FILLED</span>
                  </div>
                }
              </div>
            ))}
          </div>

          {/* graph */}
          <div className="graph-wrap">
            <div className="graph-hdr">
              <span className="scan-pill"/>
              <span className="gh-title">RELATIONSHIP GRAPH SIMULATION · BTC T+24H</span>
              <span className="gh-meta">NODES {NODES.length} EDGES {EDGES.length} PATHS 2,048 ITER {(54237+cycle*3).toLocaleString()}</span>
            </div>
            <RelGraph signal={sig}/>
            <div className={`misprice-bar ${isBull?'mpb-bull':'mpb-bear'}`}>
              MISPRICE · BTC &nbsp;
              <span className="dim">50¢ →</span>&nbsp;
              <span className="positive">79¢</span>&nbsp;
              <span className={`edge-tag ${isBull?'et-bull':'et-bear'}`}>EDGE +20¢</span>
            </div>
          </div>

          {/* bottom 3 */}
          <div className="b3">
            <div className="b3-panel">
              <div className="panel-label">ROLLING WIN RATE · 7D</div>
              <Num v={wr} suffix="%" cls="b3-big positive"/>
              <WinBlocks rate={wr}/>
              <div className="b3-sub">{perf.trinity.wins+perf.copy.wins} W &nbsp; {perf.trinity.losses+perf.copy.losses} L</div>
            </div>
            <div className="b3-panel">
              <div className="panel-label">TODAY PNL · LIVE</div>
              <Num v={31547} prefix="+$" cls="b3-big positive"/>
              <PnlArea history={pnlHist} width={140} height={28}/>
              <div className="b3-sub">{cycle} trades · peak +${Math.round(ksize)}</div>
            </div>
            <div className="b3-panel">
              <div className="panel-label">EDGE DISTRIBUTION · 24H</div>
              <Num v={38} prefix="+" suffix="¢ avg" cls="b3-big positive"/>
              <EdgeDist vals={edgeV}/>
              <div className="b3-sub">min +12¢ &nbsp; max +42¢</div>
            </div>
          </div>
        </main>

        {/* RIGHT */}
        <aside className="right-col">
          {/* trader */}
          <div className="r-panel">
            <div className="rp-tag">#1 BTC TRADER</div>
            <div className="rp-sub2">BIGGEST MIB APR 24 · 14:23 UTC</div>
            <div className="big-x-row">
              <span className="bx-x">×</span>
              <span className="bx-num">60</span>
              <span className="bx-sup positive">+08</span>
            </div>
            <div className="panel-label">FILL CURVE · 1 DAY</div>
            <CandleChart candles={candles}/>
            <div className="trade-kv-row">
              <div className="tkv"><div className="tkv-l">ENTRY SIZE</div><div className="tkv-v">$2,184</div></div>
              <div className="tkv-arrow">→</div>
              <div className="tkv"><div className="tkv-l">EXIT · 1 DAY</div><Num v={166163} prefix="$" cls="tkv-v positive"/></div>
            </div>
            {[['MARKET','BTC ▼ DOWN'],['ALPHA','+7,506%'],['TRADES','1']].map(([l,v])=>(
              <div className="kv-row" key={l}><span className="kv-l">{l}</span><span className="kv-v">{v}</span></div>
            ))}
          </div>

          {/* signal */}
          <div className="r-panel">
            <div className="panel-label">LIVE MISPRICING SIGNAL</div>
            <div className="sig-conf">conf <span className="positive">{conf}%</span> · edge +{data?.arbitrage?.opportunity?Math.round((data.arbitrage.spread||.2)*100):20}¢</div>
            {[['MARKET','BTC ▼ DOWN · A…'],['MARKET ODDS','68¢'],['MIROFISH T+24H','¢74 951'],['IMPLIED ODDS','79¢']].map(([l,v])=>(
              <div className="kv-row" key={l}><span className="kv-l">{l}</span><span className={`kv-v ${l==='MIROFISH T+24H'?'positive':''}`}>{v}</span></div>
            ))}
            <button
              className={`trade-btn ${isBull?'trade-btn-long':'trade-btn-short'} ${filling?'trade-btn-filling':''}`}
              onClick={handleShort} disabled={filling}
            >
              <span>{filling?'FILLING…':isBull?'▲ LONG BTC':'▼ SHORT BTC'}</span>
              <span className="tb-meta">3.4 R:R · $4.3K size</span>
            </button>
          </div>

          {/* chart */}
          <div className="r-panel">
            <div className="panel-label">BTC · 1H · DAILY MARKET</div>
            <Num v={76381} prefix="$" cls="chart-price"/>
            <CandleChart candles={candles}/>
          </div>

          {/* kelly */}
          <div className="r-panel">
            <div className="panel-label">KELLY SIZING</div>
            {[
              ['POSITION',  `$${ksize.toFixed(2)}`],
              ['% CAPITAL', `${((ksize/bal)*100).toFixed(2)}%`],
              ['VOTES',      `${data?.trinity?.buy_votes??5} / 10`],
              ['SIGNAL',    sig],
            ].map(([l,v])=>(
              <div className="kv-row" key={l}>
                <span className="kv-l">{l}</span>
                <span className={`kv-v ${l==='SIGNAL'?(isBull?'positive':'negative'):''}`}>{v}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>

      {/* ── Footer ── */}
      <footer className="foot">
        {[
          '$420 · BTC ▼ DOWN 24H 38¢',
          `MIRO 79¢`,
          `TRADES ${cycle}`,
          `WIN RATE ${wr}%`,
          `CYCLE #${cycle}`,
          `MIROFISH ${conf}% CONF`,
          'EDGE +38¢ AVG',
          'SIGNALS/MIN 8.2',
          conn ? '● LIVE' : '● DISCONNECTED',
        ].map((s,i)=>(
          <span key={i} className={s.includes('DISCONNECTED')?'negative':s==='● LIVE'?'positive':''}>{s}</span>
        ))}
      </footer>

      {/* ── Modal ── */}
      {modal && <ConfirmModal side={isBull?'LONG':'SHORT'} size="4,300" onConfirm={handleConfirm} onCancel={()=>setModal(false)}/>}

      {/* ── Toast ── */}
      {toast && <Toast msg={toast} onDone={()=>setToast('')}/>}

      {/* ── Paper Trading Panel ── */}
      {liveOpen  && <KalshiLivePanel onClose={()=>setLiveOpen(false)}/>}
      {paperOpen && <PaperPanel onClose={()=>setPaperOpen(false)}/>}
    </div>
  );
}
