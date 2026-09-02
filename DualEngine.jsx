import React, { useState, useEffect } from 'react';

export default function DualEngineDashboard() {
  // 1. Core input states for morning strategy optimization
  const [velocityPercent, setVelocityPercent] = useState(1.0);
  const [atrMultiplier, setAtrMultiplier] = useState(0.5);
  const [isProcessing, setIsProcessing] = useState(false);
  const [logRecords, setLogRecords] = useState([]);

  // 2. Automatically pulls execution outputs directly from GitHub storage
  const fetchStrategyLogs = async () => {
    try {
      const response = await fetch('https://githubusercontent.com');
      if (!response.ok) return;
      const dataText = await response.text();
      
      const lines = dataText.split('\n').filter(line => line.trim() !== '');
      const parsedData = lines.slice(1).map(line => {
        const columns = line.split(',');
        return {
          date: columns[0], symbol: columns[1], side: columns[2],
          entry: columns[3], exit: columns[4] || '-', pnl: columns[5] || '-', status: columns[6]
        };
      });
      setLogRecords(parsedData.reverse()); // Newest trades first
    } catch (err) {
      console.error("Log fetch processing failure: ", err);
    }
  };

  useEffect(() => { fetchStrategyLogs(); }, []);

  // 3. Triggers your Python backend workflow instantly using user metrics
  const executeScanDispatch = async () => {
    setIsProcessing(true);
    try {
      // Dispatches request directly back to GitHub's automation api runner
      const res = await fetch('https://github.com', {
        method: 'POST',
        headers: {
          'Accept': 'application/vnd.github+json',
          'Authorization': `Bearer ${process.env.NEXT_PUBLIC_GITHUB_PAT}`, 
        },
        body: JSON.stringify({
          ref: 'main',
          inputs: {
            velocity: velocityPercent.toString(),
            atr_mult: atrMultiplier.toString()
          }
        })
      });

      if (res.status === 204) {
        alert('⚡ Parameters synchronized! GitHub Engine is now processing your calculations. The table below will update shortly.');
      } else {
        alert('⚠️ Workflow server accepted message but returned unexpected code.');
      }
    } catch (err) {
      alert('❌ Trigger connection error: ' + err.message);
    }
    setIsProcessing(false);
  };

  return (
    <div style={{ padding: '24px', backgroundColor: '#ffffff', borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
      <h2 style={{ color: '#111827', marginBottom: '6px' }}>🛠️ Dual-Engine Strategy Configuration</h2>
      <p style={{ color: '#6b7280', marginTop: '0', marginBottom: '24px' }}>Adjust your core screening metrics at the start of the day.</p>

      {/* Control Module Card */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '24px', backgroundColor: '#f9fafb', padding: '20px', borderRadius: '8px', border: '1px solid #e5e7eb', marginBottom: '32px' }}>
        <div>
          <label style={{ display: 'block', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>📈 Price Velocity Target: <span style={{ color: '#2563eb' }}>{velocityPercent}%</span></label>
          <input type="range" min="0.5" max="3.0" step="0.1" value={velocityPercent} onChange={(e) => setVelocityPercent(parseFloat(e.target.value))} style={{ width: '100%', cursor: 'pointer' }} />
        </div>
        <div>
          <label style={{ display: 'block', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>📊 ATR Range Threshold: <span style={{ color: '#2563eb' }}>{atrMultiplier}x</span></label>
          <input type="range" min="0.2" max="1.5" step="0.1" value={atrMultiplier} onChange={(e) => setAtrMultiplier(parseFloat(e.target.value))} style={{ width: '100%', cursor: 'pointer' }} />
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button onClick={executeScanDispatch} disabled={isProcessing} style={{ width: '100%', padding: '12px', backgroundColor: '#2563eb', color: '#ffffff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer', opacity: isProcessing ? 0.6 : 1, transition: 'background-color 0.2s' }}>
            {isProcessing ? 'Synchronizing System...' : '⚡ Apply Variables & Run'}
          </button>
        </div>
      </div>

      {/* Dynamic Spreadsheet Output UI */}
      <h3 style={{ color: '#111827', marginBottom: '16px' }}>📋 Real-Time Model Output</h3>
      <div style={{ overflowX: 'auto', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
          <thead>
            <tr style={{ backgroundColor: '#f3f4f6', borderBottom: '1px solid #e5e7eb', color: '#374151' }}>
              <th style={{ padding: '12px 16px' }}>Date</th>
              <th style={{ padding: '12px 16px' }}>Symbol</th>
              <th style={{ padding: '12px 16px' }}>Side</th>
              <th style={{ padding: '12px 16px' }}>Entry Price</th>
              <th style={{ padding: '12px 16px' }}>Exit Price</th>
              <th style={{ padding: '12px 16px' }}>Net P&L Points</th>
              <th style={{ padding: '12px 16px' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {logRecords.length === 0 ? (
              <tr><td colSpan="7" style={{ padding: '24px', textAlign: 'center', color: '#9ca3af' }}>No execution signals logged for this layout config.</td></tr>
            ) : (
              logRecords.map((trade, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #e5e7eb', hover: { backgroundColor: '#f9fafb' } }}>
                  <td style={{ padding: '12px 16px', color: '#4b5563' }}>{trade.date}</td>
                  <td style={{ padding: '12px 16px', fontWeight: '600', color: '#111827' }}>{trade.symbol}</td>
                  <td style={{ padding: '12px 16px' }}><span style={{ padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: '600', backgroundColor: trade.side.includes('BUY') ? '#def7ec' : '#fde8e8', color: trade.side.includes('BUY') ? '#03543f' : '#9b1c1c' }}>{trade.side}</span></td>
                  <td style={{ padding: '12px 16px', color: '#111827' }}>₹{trade.entry}</td>
                  <td style={{ padding: '12px 16px', color: '#111827' }}>{trade.exit !== '-' ? `₹${trade.exit}` : '-'}</td>
                  <td style={{ padding: '12px 16px', fontWeight: '600', color: parseFloat(trade.pnl) > 0 ? '#0e6245' : parseFloat(trade.pnl) < 0 ? '#9b1c1c' : '#111827' }}>{trade.pnl}</td>
                  <td style={{ padding: '12px 16px' }}><span style={{ fontSize: '12px', fontWeight: '500', color: trade.status === 'CLOSED' ? '#6b7280' : '#d97706' }}>● {trade.status}</span></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
