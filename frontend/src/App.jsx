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
    </div>
  );
}
