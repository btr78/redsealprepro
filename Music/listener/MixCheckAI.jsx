import { useState, useRef, useCallback, useEffect } from "react";

const COLORS = {
  bg: "#0a0b0f",
  surface: "#12141a",
  surfaceHover: "#1a1d25",
  border: "#2a2d38",
  borderActive: "#4a7cff",
  primary: "#4a7cff",
  primaryDim: "#3a5cc0",
  accent: "#00e5a0",
  accentDim: "#00b880",
  warning: "#ffb347",
  danger: "#ff5757",
  text: "#e8eaf0",
  textDim: "#8a8fa0",
  textMuted: "#5a5f70",
};

const analyzeAudio = (audioBuffer) => {
  const sampleRate = audioBuffer.sampleRate;
  const duration = audioBuffer.duration;
  const channels = audioBuffer.numberOfChannels;
  const totalSamples = audioBuffer.length;

  // Get channel data
  const leftChannel = audioBuffer.getChannelData(0);
  const rightChannel = channels > 1 ? audioBuffer.getChannelData(1) : leftChannel;

  // RMS and Peak
  let sumSquares = 0;
  let peak = 0;
  for (let i = 0; i < totalSamples; i++) {
    const mono = (leftChannel[i] + rightChannel[i]) / 2;
    sumSquares += mono * mono;
    const absSample = Math.abs(mono);
    if (absSample > peak) peak = absSample;
  }
  const rms = Math.sqrt(sumSquares / totalSamples);
  const rmsDb = 20 * Math.log10(rms + 1e-10);
  const peakDb = 20 * Math.log10(peak + 1e-10);

  // Estimated LUFS (simplified)
  const estimatedLUFS = rmsDb - 0.691;

  // Crest factor (dynamic range indicator)
  const crestFactor = peakDb - rmsDb;

  // Frequency analysis using FFT on multiple segments
  const fftSize = 4096;
  const offlineCtx = new OfflineAudioContext(1, totalSamples, sampleRate);
  
  // Simple frequency band analysis
  const bands = {
    sub: { low: 20, high: 60, energy: 0, label: "Sub Bass (20-60 Hz)" },
    bass: { low: 60, high: 250, energy: 0, label: "Bass (60-250 Hz)" },
    lowMid: { low: 250, high: 500, energy: 0, label: "Low Mid (250-500 Hz)" },
    mid: { low: 500, high: 2000, energy: 0, label: "Mid (500-2k Hz)" },
    upperMid: { low: 2000, high: 4000, energy: 0, label: "Upper Mid (2k-4k Hz)" },
    presence: { low: 4000, high: 6000, energy: 0, label: "Presence (4k-6k Hz)" },
    brilliance: { low: 6000, high: 12000, energy: 0, label: "Brilliance (6k-12k Hz)" },
    air: { low: 12000, high: 20000, energy: 0, label: "Air (12k-20k Hz)" },
  };

  // Analyze segments
  const segmentSize = fftSize;
  const numSegments = Math.floor(totalSamples / segmentSize);
  const avgSpectrum = new Float32Array(segmentSize / 2);

  for (let seg = 0; seg < Math.min(numSegments, 50); seg++) {
    const offset = seg * segmentSize;
    const segment = new Float32Array(segmentSize);
    for (let i = 0; i < segmentSize && offset + i < totalSamples; i++) {
      const mono = (leftChannel[offset + i] + rightChannel[offset + i]) / 2;
      // Hanning window
      const window = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (segmentSize - 1)));
      segment[i] = mono * window;
    }

    // Simple DFT for key frequencies (approximate)
    const freqResolution = sampleRate / segmentSize;
    for (const key in bands) {
      const band = bands[key];
      const binLow = Math.floor(band.low / freqResolution);
      const binHigh = Math.min(Math.ceil(band.high / freqResolution), segmentSize / 2);
      let bandEnergy = 0;
      for (let bin = binLow; bin < binHigh; bin++) {
        bandEnergy += segment[bin] * segment[bin];
      }
      band.energy += bandEnergy / (binHigh - binLow + 1);
    }
  }

  // Normalize band energies
  const totalEnergy = Object.values(bands).reduce((sum, b) => sum + b.energy, 0);
  const bandAnalysis = {};
  for (const key in bands) {
    const band = bands[key];
    const pct = totalEnergy > 0 ? (band.energy / totalEnergy) * 100 : 0;
    const db = 10 * Math.log10(band.energy / Math.max(numSegments, 1) + 1e-10);
    bandAnalysis[key] = {
      label: band.label,
      percentage: pct.toFixed(1),
      db: db.toFixed(1),
    };
  }

  // Dynamic range - analyze in chunks
  const chunkDuration = 0.4; // 400ms chunks
  const chunkSamples = Math.floor(sampleRate * chunkDuration);
  const numChunks = Math.floor(totalSamples / chunkSamples);
  const chunkLoudness = [];

  for (let i = 0; i < numChunks; i++) {
    let chunkSum = 0;
    const offset = i * chunkSamples;
    for (let j = 0; j < chunkSamples; j++) {
      const mono = (leftChannel[offset + j] + rightChannel[offset + j]) / 2;
      chunkSum += mono * mono;
    }
    const chunkRms = Math.sqrt(chunkSum / chunkSamples);
    const chunkDb = 20 * Math.log10(chunkRms + 1e-10);
    chunkLoudness.push(chunkDb);
  }

  // Sort for LRA estimation
  const sorted = [...chunkLoudness].filter(d => d > -60).sort((a, b) => a - b);
  const p10 = sorted[Math.floor(sorted.length * 0.1)] || -60;
  const p95 = sorted[Math.floor(sorted.length * 0.95)] || 0;
  const estimatedLRA = p95 - p10;

  // Stereo width
  let midEnergy = 0;
  let sideEnergy = 0;
  for (let i = 0; i < totalSamples; i++) {
    const mid = (leftChannel[i] + rightChannel[i]) / 2;
    const side = (leftChannel[i] - rightChannel[i]) / 2;
    midEnergy += mid * mid;
    sideEnergy += side * side;
  }
  const stereoWidth = midEnergy > 0 ? (sideEnergy / midEnergy) * 100 : 0;

  // Loudness over time for waveform display (downsample)
  const displayPoints = 200;
  const pointSize = Math.floor(totalSamples / displayPoints);
  const waveform = [];
  for (let i = 0; i < displayPoints; i++) {
    let maxVal = 0;
    const offset = i * pointSize;
    for (let j = 0; j < pointSize && offset + j < totalSamples; j++) {
      const mono = Math.abs((leftChannel[offset + j] + rightChannel[offset + j]) / 2);
      if (mono > maxVal) maxVal = mono;
    }
    waveform.push(maxVal);
  }

  return {
    duration: duration.toFixed(1),
    sampleRate,
    channels,
    bitDepth: "32-bit float",
    rmsDb: rmsDb.toFixed(1),
    peakDb: peakDb.toFixed(1),
    estimatedLUFS: estimatedLUFS.toFixed(1),
    estimatedLRA: estimatedLRA.toFixed(1),
    crestFactor: crestFactor.toFixed(1),
    stereoWidth: stereoWidth.toFixed(1),
    bandAnalysis,
    waveform,
    chunkLoudness,
    isClipping: peak >= 0.99,
    isTooLoud: estimatedLUFS > -10,
    isTooQuiet: estimatedLUFS < -18,
    isOverCompressed: estimatedLRA < 4,
    isUnderCompressed: estimatedLRA > 14,
    hasExcessSub: bandAnalysis.sub && parseFloat(bandAnalysis.sub.percentage) > 20,
    lacksPresence: bandAnalysis.upperMid && parseFloat(bandAnalysis.upperMid.percentage) < 8,
  };
};

const getAISuggestions = async (analysis, fileName, apiKey = "") => {
  const prompt = `You are an expert audio engineer specializing in worship/church livestream mixes. Analyze this audio file and give specific, actionable mixing suggestions.

File: ${fileName}
Duration: ${analysis.duration}s
Sample Rate: ${analysis.sampleRate} Hz
Channels: ${analysis.channels}

LEVELS:
- RMS: ${analysis.rmsDb} dBFS
- Peak: ${analysis.peakDb} dBFS
- Estimated LUFS: ${analysis.estimatedLUFS}
- Estimated LRA: ${analysis.estimatedLRA} LU
- Crest Factor: ${analysis.crestFactor} dB
- Stereo Width: ${analysis.stereoWidth}%

FREQUENCY BANDS:
${Object.values(analysis.bandAnalysis).map(b => `- ${b.label}: ${b.percentage}% energy, ${b.db} dB`).join("\n")}

FLAGS:
- Clipping: ${analysis.isClipping}
- Too Loud (>-10 LUFS): ${analysis.isTooLoud}
- Too Quiet (<-18 LUFS): ${analysis.isTooQuiet}
- Over-compressed (LRA <4): ${analysis.isOverCompressed}
- Under-compressed (LRA >14): ${analysis.isUnderCompressed}
- Excess Sub Bass: ${analysis.hasExcessSub}
- Lacks Presence: ${analysis.lacksPresence}

Give your response as JSON only, no markdown, no backticks. Use this exact structure:
{
  "overallScore": <number 1-10>,
  "overallVerdict": "<one sentence summary>",
  "issues": [
    {"severity": "critical|warning|info", "title": "<short title>", "description": "<1-2 sentences>", "fix": "<specific fix with exact numbers/settings>"}
  ],
  "eqSuggestions": [
    {"frequency": "<freq>", "action": "boost|cut", "amount": "<dB>", "reason": "<why>"}
  ],
  "compressionNotes": "<2-3 sentences about dynamics>",
  "streamReadiness": "<ready|needs work|not ready>",
  "logicProTips": ["<specific Logic Pro X tip>", "<another tip>"]
}`;

  const payload = {
    model: "claude-sonnet-4-6",
    max_tokens: 1000,
    messages: [{ role: "user", content: prompt }],
  };

  try {
    // Route through local proxy to avoid CORS
    const response = await fetch("http://127.0.0.1:8742/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apiKey, payload }),
    });
    const data = await response.json();
    if (data.error) throw new Error(data.error.message || JSON.stringify(data.error));
    const text = data.content
      .filter((item) => item.type === "text")
      .map((item) => item.text)
      .join("");
    const clean = text.replace(/```json|```/g, "").trim();
    return JSON.parse(clean);
  } catch (err) {
    console.error("AI error:", err);
    return null;
  }
};

// Components
const Waveform = ({ data, width = 540, height = 100 }) => {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data, 0.01);
  const barWidth = width / data.length;
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: "block" }}>
      {data.map((v, i) => {
        const h = (v / max) * (height / 2);
        const intensity = v / max;
        const color = intensity > 0.9 ? COLORS.danger : intensity > 0.7 ? COLORS.warning : COLORS.primary;
        return (
          <g key={i}>
            <rect x={i * barWidth} y={height / 2 - h} width={Math.max(barWidth - 0.5, 0.5)} height={h} fill={color} opacity={0.8} rx={0.5} />
            <rect x={i * barWidth} y={height / 2} width={Math.max(barWidth - 0.5, 0.5)} height={h} fill={color} opacity={0.5} rx={0.5} />
          </g>
        );
      })}
      <line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke={COLORS.textMuted} strokeWidth={0.5} opacity={0.3} />
    </svg>
  );
};

const FrequencyBars = ({ bandAnalysis }) => {
  const bands = Object.entries(bandAnalysis);
  const maxPct = Math.max(...bands.map(([, b]) => parseFloat(b.percentage)), 1);
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 120, padding: "0 4px" }}>
      {bands.map(([key, band]) => {
        const pct = parseFloat(band.percentage);
        const height = Math.max((pct / maxPct) * 100, 4);
        const isHigh = pct > 20;
        const isLow = pct < 5;
        const color = isHigh ? COLORS.warning : isLow ? COLORS.textMuted : COLORS.accent;
        return (
          <div key={key} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
            <span style={{ fontSize: 9, color: COLORS.textDim }}>{pct}%</span>
            <div style={{ width: "100%", height: height, background: color, borderRadius: 3, opacity: 0.8, transition: "height 0.5s ease" }} />
            <span style={{ fontSize: 8, color: COLORS.textMuted, textAlign: "center", lineHeight: 1.1 }}>
              {band.label.split(" (")[0]}
            </span>
          </div>
        );
      })}
    </div>
  );
};

const MetricCard = ({ label, value, unit, status }) => {
  const statusColor = status === "good" ? COLORS.accent : status === "warning" ? COLORS.warning : status === "danger" ? COLORS.danger : COLORS.textDim;
  return (
    <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 10, padding: "12px 14px", flex: 1, minWidth: 100 }}>
      <div style={{ fontSize: 10, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span style={{ fontSize: 22, fontWeight: 700, color: statusColor, fontFamily: "'JetBrains Mono', 'SF Mono', monospace" }}>{value}</span>
        {unit && <span style={{ fontSize: 11, color: COLORS.textMuted }}>{unit}</span>}
      </div>
    </div>
  );
};

const IssueCard = ({ issue }) => {
  const colors = { critical: COLORS.danger, warning: COLORS.warning, info: COLORS.primary };
  const icons = { critical: "!!", warning: "!", info: "i" };
  const color = colors[issue.severity] || COLORS.textDim;
  return (
    <div style={{ background: COLORS.surface, border: `1px solid ${color}30`, borderLeft: `3px solid ${color}`, borderRadius: 8, padding: 14, marginBottom: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ background: `${color}20`, color, fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, textTransform: "uppercase" }}>
          {icons[issue.severity]} {issue.severity}
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: COLORS.text }}>{issue.title}</span>
      </div>
      <p style={{ fontSize: 12, color: COLORS.textDim, margin: "0 0 8px 0", lineHeight: 1.5 }}>{issue.description}</p>
      <div style={{ background: `${COLORS.accent}10`, border: `1px solid ${COLORS.accent}20`, borderRadius: 6, padding: "8px 10px" }}>
        <span style={{ fontSize: 10, color: COLORS.accent, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>Fix: </span>
        <span style={{ fontSize: 12, color: COLORS.text }}>{issue.fix}</span>
      </div>
    </div>
  );
};

const ScoreRing = ({ score }) => {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 10) * circumference;
  const color = score >= 7 ? COLORS.accent : score >= 4 ? COLORS.warning : COLORS.danger;
  return (
    <div style={{ position: "relative", width: 100, height: 100 }}>
      <svg width={100} height={100} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={50} cy={50} r={radius} fill="none" stroke={COLORS.border} strokeWidth={6} />
        <circle cx={50} cy={50} r={radius} fill="none" stroke={color} strokeWidth={6} strokeDasharray={circumference} strokeDashoffset={circumference - progress} strokeLinecap="round" style={{ transition: "stroke-dashoffset 1s ease" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: 28, fontWeight: 800, color, fontFamily: "'JetBrains Mono', monospace" }}>{score}</span>
        <span style={{ fontSize: 9, color: COLORS.textMuted }}>/10</span>
      </div>
    </div>
  );
};

export default function AudioAnalyzer() {
  const [audioFile, setAudioFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [aiSuggestions, setAiSuggestions] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isGettingAI, setIsGettingAI] = useState(false);
  const [progress, setProgress] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleFile = useCallback(async (file) => {
    if (!file) return;
    setAudioFile(file);
    setAnalysis(null);
    setAiSuggestions(null);
    setIsAnalyzing(true);
    setProgress("Decoding audio...");

    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const arrayBuffer = await file.arrayBuffer();
      setProgress("Analyzing frequencies & levels...");
      const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
      
      const result = analyzeAudio(audioBuffer);
      setAnalysis(result);
      setProgress("Getting AI suggestions...");
      setIsAnalyzing(false);
      setIsGettingAI(true);

      const suggestions = await getAISuggestions(result, file.name);
      setAiSuggestions(suggestions);
      setIsGettingAI(false);
      setProgress("");
      audioCtx.close();
    } catch (err) {
      console.error("Analysis error:", err);
      setProgress("Error analyzing audio. Try a different file format.");
      setIsAnalyzing(false);
      setIsGettingAI(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("audio/")) handleFile(file);
  }, [handleFile]);

  const getLUFSStatus = (lufs) => {
    const v = parseFloat(lufs);
    if (v > -10) return "danger";
    if (v > -12) return "warning";
    if (v < -18) return "warning";
    return "good";
  };

  const getLRAStatus = (lra) => {
    const v = parseFloat(lra);
    if (v < 4) return "danger";
    if (v > 14) return "warning";
    return "good";
  };

  const getPeakStatus = (peak) => {
    const v = parseFloat(peak);
    if (v > -0.5) return "danger";
    if (v > -1) return "warning";
    return "good";
  };

  return (
    <div style={{ minHeight: "100vh", background: COLORS.bg, color: COLORS.text, fontFamily: "'DM Sans', 'SF Pro Display', -apple-system, sans-serif" }}>
      {/* Header */}
      <div style={{ background: `linear-gradient(135deg, ${COLORS.surface} 0%, ${COLORS.bg} 100%)`, borderBottom: `1px solid ${COLORS.border}`, padding: "20px 24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: `linear-gradient(135deg, ${COLORS.primary}, ${COLORS.accent})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>
            🎛
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, letterSpacing: -0.3 }}>MixCheck AI</h1>
            <p style={{ margin: 0, fontSize: 11, color: COLORS.textMuted }}>Worship Audio Analyzer</p>
          </div>
        </div>
      </div>

      <div style={{ padding: "20px 16px", maxWidth: 640, margin: "0 auto" }}>
        {/* Upload Area */}
        {!analysis && !isAnalyzing && (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `2px dashed ${dragOver ? COLORS.primary : COLORS.border}`,
              borderRadius: 16,
              padding: "48px 24px",
              textAlign: "center",
              cursor: "pointer",
              background: dragOver ? `${COLORS.primary}08` : COLORS.surface,
              transition: "all 0.2s ease",
            }}
          >
            <div style={{ fontSize: 48, marginBottom: 12 }}>🎵</div>
            <p style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>Drop your audio file here</p>
            <p style={{ fontSize: 12, color: COLORS.textMuted }}>MP3, WAV, M4A, AAC — or tap to browse</p>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              onChange={(e) => handleFile(e.target.files[0])}
              style={{ display: "none" }}
            />
          </div>
        )}

        {/* Loading */}
        {(isAnalyzing || isGettingAI) && (
          <div style={{ textAlign: "center", padding: "48px 24px" }}>
            <div style={{
              width: 48, height: 48, border: `3px solid ${COLORS.border}`, borderTop: `3px solid ${COLORS.primary}`,
              borderRadius: "50%", margin: "0 auto 16px",
              animation: "spin 1s linear infinite",
            }} />
            <p style={{ fontSize: 14, color: COLORS.textDim }}>{progress}</p>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {/* Results */}
        {analysis && (
          <div>
            {/* File info bar */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 20 }}>📄</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{audioFile?.name}</div>
                  <div style={{ fontSize: 10, color: COLORS.textMuted }}>{analysis.duration}s • {analysis.sampleRate} Hz • {analysis.channels}ch</div>
                </div>
              </div>
              <button
                onClick={() => { setAnalysis(null); setAiSuggestions(null); setAudioFile(null); }}
                style={{
                  background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 8,
                  color: COLORS.textDim, fontSize: 11, padding: "6px 12px", cursor: "pointer",
                }}
              >
                New File
              </button>
            </div>

            {/* Waveform */}
            <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>Waveform</div>
              <Waveform data={analysis.waveform} />
            </div>

            {/* Metrics Grid */}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
              <MetricCard label="Loudness" value={analysis.estimatedLUFS} unit="LUFS" status={getLUFSStatus(analysis.estimatedLUFS)} />
              <MetricCard label="True Peak" value={analysis.peakDb} unit="dBFS" status={getPeakStatus(analysis.peakDb)} />
              <MetricCard label="LRA" value={analysis.estimatedLRA} unit="LU" status={getLRAStatus(analysis.estimatedLRA)} />
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
              <MetricCard label="Crest Factor" value={analysis.crestFactor} unit="dB" status="neutral" />
              <MetricCard label="Stereo Width" value={analysis.stereoWidth} unit="%" status="neutral" />
              <MetricCard label="RMS" value={analysis.rmsDb} unit="dBFS" status="neutral" />
            </div>

            {/* Quick Flags */}
            {(analysis.isClipping || analysis.isTooLoud || analysis.isTooQuiet || analysis.isOverCompressed || analysis.isUnderCompressed) && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
                {analysis.isClipping && <span style={{ background: `${COLORS.danger}20`, color: COLORS.danger, fontSize: 10, fontWeight: 600, padding: "4px 10px", borderRadius: 20 }}>⚠ CLIPPING</span>}
                {analysis.isTooLoud && <span style={{ background: `${COLORS.warning}20`, color: COLORS.warning, fontSize: 10, fontWeight: 600, padding: "4px 10px", borderRadius: 20 }}>🔊 TOO LOUD</span>}
                {analysis.isTooQuiet && <span style={{ background: `${COLORS.warning}20`, color: COLORS.warning, fontSize: 10, fontWeight: 600, padding: "4px 10px", borderRadius: 20 }}>🔇 TOO QUIET</span>}
                {analysis.isOverCompressed && <span style={{ background: `${COLORS.danger}20`, color: COLORS.danger, fontSize: 10, fontWeight: 600, padding: "4px 10px", borderRadius: 20 }}>💥 OVER-COMPRESSED</span>}
                {analysis.isUnderCompressed && <span style={{ background: `${COLORS.warning}20`, color: COLORS.warning, fontSize: 10, fontWeight: 600, padding: "4px 10px", borderRadius: 20 }}>📈 WIDE DYNAMICS</span>}
              </div>
            )}

            {/* Frequency Spectrum */}
            <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>Frequency Spectrum</div>
              <FrequencyBars bandAnalysis={analysis.bandAnalysis} />
            </div>

            {/* AI Suggestions */}
            {isGettingAI && (
              <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.primary}30`, borderRadius: 12, padding: 24, textAlign: "center", marginBottom: 16 }}>
                <div style={{
                  width: 32, height: 32, border: `2px solid ${COLORS.border}`, borderTop: `2px solid ${COLORS.accent}`,
                  borderRadius: "50%", margin: "0 auto 12px",
                  animation: "spin 1s linear infinite",
                }} />
                <p style={{ fontSize: 13, color: COLORS.textDim }}>AI is analyzing your mix...</p>
              </div>
            )}

            {aiSuggestions && (
              <div>
                {/* Score + Verdict */}
                <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 20, marginBottom: 16, display: "flex", alignItems: "center", gap: 20 }}>
                  <ScoreRing score={aiSuggestions.overallScore} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>AI Mix Score</div>
                    <p style={{ fontSize: 14, color: COLORS.text, margin: 0, lineHeight: 1.5 }}>{aiSuggestions.overallVerdict}</p>
                    <div style={{ marginTop: 8 }}>
                      <span style={{
                        fontSize: 10, fontWeight: 600, padding: "3px 10px", borderRadius: 20,
                        background: aiSuggestions.streamReadiness === "ready" ? `${COLORS.accent}20` : aiSuggestions.streamReadiness === "needs work" ? `${COLORS.warning}20` : `${COLORS.danger}20`,
                        color: aiSuggestions.streamReadiness === "ready" ? COLORS.accent : aiSuggestions.streamReadiness === "needs work" ? COLORS.warning : COLORS.danger,
                      }}>
                        Stream: {aiSuggestions.streamReadiness?.toUpperCase()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Issues */}
                {aiSuggestions.issues?.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 11, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>Issues & Fixes</div>
                    {aiSuggestions.issues.map((issue, i) => (
                      <IssueCard key={i} issue={issue} />
                    ))}
                  </div>
                )}

                {/* EQ Suggestions */}
                {aiSuggestions.eqSuggestions?.length > 0 && (
                  <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
                    <div style={{ fontSize: 11, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>EQ Suggestions</div>
                    {aiSuggestions.eqSuggestions.map((eq, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: i < aiSuggestions.eqSuggestions.length - 1 ? `1px solid ${COLORS.border}` : "none" }}>
                        <span style={{
                          fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, minWidth: 40, textAlign: "center",
                          background: eq.action === "boost" ? `${COLORS.accent}20` : `${COLORS.danger}20`,
                          color: eq.action === "boost" ? COLORS.accent : COLORS.danger,
                        }}>
                          {eq.action === "boost" ? "↑" : "↓"} {eq.amount}
                        </span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: COLORS.primary, minWidth: 60 }}>{eq.frequency}</span>
                        <span style={{ fontSize: 11, color: COLORS.textDim, flex: 1 }}>{eq.reason}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Compression Notes */}
                {aiSuggestions.compressionNotes && (
                  <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.border}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
                    <div style={{ fontSize: 11, color: COLORS.textMuted, textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>Compression Notes</div>
                    <p style={{ fontSize: 12, color: COLORS.textDim, margin: 0, lineHeight: 1.6 }}>{aiSuggestions.compressionNotes}</p>
                  </div>
                )}

                {/* Logic Pro Tips */}
                {aiSuggestions.logicProTips?.length > 0 && (
                  <div style={{ background: COLORS.surface, border: `1px solid ${COLORS.primary}30`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
                    <div style={{ fontSize: 11, color: COLORS.primary, textTransform: "uppercase", letterSpacing: 1, marginBottom: 10, fontWeight: 600 }}>Logic Pro Tips</div>
                    {aiSuggestions.logicProTips.map((tip, i) => (
                      <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8 }}>
                        <span style={{ color: COLORS.accent, fontSize: 12 }}>→</span>
                        <span style={{ fontSize: 12, color: COLORS.textDim, lineHeight: 1.5 }}>{tip}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
