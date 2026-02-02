import { useState, useRef, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open, save } from "@tauri-apps/plugin-dialog";
import "./App.css";

interface ScanResult {
  name: string;
  pattern: string;
  count: number;
  chapters: string[];
  suggested_level?: number;
}

function App() {

  const [txtPath, setTxtPath] = useState("");
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);

  // Advanced Options
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [removeEmptyLines, setRemoveEmptyLines] = useState(false);
  const [fixIndent, setFixIndent] = useState(true);
  const [customRegex, setCustomRegex] = useState("");
  const [disabledPatterns, setDisabledPatterns] = useState<Set<string>>(new Set());

  // Scanning State
  const [isScanning, setIsScanning] = useState(false);
  const [allScanResults, setAllScanResults] = useState<ScanResult[]>([]);  // Raw unfiltered results
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);  // Filtered results (enabled patterns)
  const [selectedPatternIndex, setSelectedPatternIndex] = useState<number>(-1);
  const [patternLevels, setPatternLevels] = useState<Record<string, number>>({});  // Pattern name -> heading level (1-6)

  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Re-filter when disabledPatterns changes (no re-scan needed)
  useEffect(() => {
    if (allScanResults.length > 0) {
      const filtered = allScanResults.filter(r => !disabledPatterns.has(r.name));
      setScanResults(filtered);
    }
  }, [disabledPatterns, allScanResults]);

  function addLog(msg: string) {
    setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  }

  function parseProgress(line: string) {
    // Expected format: "PROGRESS: 10% (Description)"
    const match = line.match(/PROGRESS:\s*(\d+)%/);
    if (match) {
      setProgress(parseInt(match[1]));
    }
  }

  async function scanFile(path: string) {
    setIsScanning(true);
    setScanResults([]);
    setAllScanResults([]);
    setSelectedPatternIndex(-1);
    addLog("正在扫描章节结构...");

    try {
      const jsonResult = await invoke("scan_chapters", { txtPath: path });

      // Try to handle both old and new format
      let results: ScanResult[] = [];

      try {
        const parsed = JSON.parse(jsonResult as string);
        if (Array.isArray(parsed)) {
          // Old format: direct array
          results = parsed;
        } else if (parsed.patterns) {
          // New format: {patterns: [], suggested_hierarchy: []}
          results = parsed.patterns || [];
        }
      } catch (parseErr) {
        addLog(`[ERROR] JSON解析失败: ${parseErr}`);
      }

      // Store ALL results with matches for checkbox display
      const matchedResults = results.filter(r => r.count > 0);
      matchedResults.sort((a, b) => b.count - a.count);
      setAllScanResults(matchedResults);

      // Filter out disabled patterns
      const filteredResults = matchedResults.filter(r => !disabledPatterns.has(r.name));
      setScanResults(filteredResults);

      // Log summary
      const totalChapters = filteredResults.reduce((sum, r) => sum + r.count, 0);
      if (filteredResults.length > 0) {
        addLog(`扫描完成，发现 ${filteredResults.length} 个匹配规则，共 ${totalChapters} 个章节标记`);
      } else {
        addLog("扫描完成，未发现匹配章节。");

      }
    } catch (e) {
      addLog(`扫描失败: ${e}`);
    } finally {
      setIsScanning(false);
    }
  }

  function handlePatternSelect(index: number) {
    setSelectedPatternIndex(index);
    setCustomRegex(scanResults[index].pattern);
  }

  async function selectTxt() {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'Text', extensions: ['txt'] }]
      });
      if (selected) {
        const path = selected as string;
        setTxtPath(path);
        addLog(`已选择文件: ${path}`);

        // Auto-guess title
        const filename = path.split(/[\\/]/).pop()?.replace('.txt', '') || "";
        setTitle(filename);

        // Trigger Scan
        scanFile(path);
      }
    } catch (err) {
      addLog(`选择文件出错: ${err}`);
    }
  }

  async function convert() {
    if (!txtPath || !title) {
      addLog("错误: 请先选择文件并输入标题。");
      return;
    }

    try {
      const epubPath = await save({
        filters: [{ name: 'EPUB', extensions: ['epub'] }],
        defaultPath: `${title}.epub`,
        title: '保存 EPUB 文件'
      });

      if (!epubPath) return;

      setLoading(true);
      setProgress(0);
      addLog(`开始转换...`);
      addLog(`输出路径: ${epubPath}`);

      // Collect ALL enabled patterns with their levels
      // Format: pattern:level|||pattern:level (e.g., ^第.+章:1|||^第.+节:2)
      const patternsWithLevels = scanResults.map(r => {
        const level = patternLevels[r.name] || 1;
        return `${r.pattern}:${level}`;
      });

      if (patternsWithLevels.length > 0) {
        addLog(`使用 ${patternsWithLevels.length} 个规则进行分章:`);
        scanResults.forEach(r => {
          const level = patternLevels[r.name] || 1;
          addLog(`  - ${r.name} → h${level} (${r.count} 章)`);
        });
      } else if (customRegex) {
        addLog(`使用自定义正则: ${customRegex}`);
      }

      const result = await invoke("convert_book", {
        txtPath,
        epubPath,
        title,
        author,
        customRegex: patternsWithLevels.length === 0 ? (customRegex || null) : null,
        patterns: patternsWithLevels.length > 0 ? patternsWithLevels.join("|||") : null,
        removeEmptyLine: removeEmptyLines,
        fixIndent: fixIndent
      });



      const lines = (result as string).split('\n');
      lines.forEach(line => {
        if (line.trim()) {
          if (line.includes("PROGRESS:")) {
            parseProgress(line);
          } else {
            addLog(`> ${line}`);
          }
        }
      });

      addLog("转换任务已完成。");
      setProgress(100);
    } catch (error) {
      addLog(`严重错误: ${error}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-container">
      {/* Left Panel: Operations */}
      <div className="left-panel">
        <h1>TXT 转 EPUB</h1>

        <div>
          <div className="section-title">1. 选择文件</div>
          <div className="file-drop-area" onClick={selectTxt}>
            {txtPath ? (
              <span className="file-name">
                {txtPath.split(/[\\/]/).pop()}
              </span>
            ) : (
              <span>点击选择 .txt 文件</span>
            )}
          </div>
          {txtPath && <div className="file-path">{txtPath}</div>}
        </div>




        <div>
          <div className="section-title">2. 书籍信息</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <input
              placeholder="书籍标题 *"
              value={title}
              onChange={e => setTitle(e.target.value)}
            />
            <input
              placeholder="作者"
              value={author}
              onChange={e => setAuthor(e.target.value)}
            />
          </div>
        </div>

        <div>
          <div
            className="section-title"
            style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            <span>3. 高级选项 & 章节结构</span>
            <span style={{ marginLeft: 'auto', transform: showAdvanced ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.3s' }}>▼</span>
          </div>

          {showAdvanced && (
            <div className="advanced-options-container">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <label style={{ display: 'flex', alignItems: 'center', fontSize: '0.9em' }}>
                  <input
                    type="checkbox"
                    checked={removeEmptyLines}
                    onChange={e => setRemoveEmptyLines(e.target.checked)}
                    style={{ width: 'auto', marginRight: '8px' }}
                  />
                  去除多余空行
                </label>
                <label style={{ display: 'flex', alignItems: 'center', fontSize: '0.9em' }}>
                  <input
                    type="checkbox"
                    checked={fixIndent}
                    onChange={e => setFixIndent(e.target.checked)}
                    style={{ width: 'auto', marginRight: '8px' }}
                  />
                  修正首行缩进
                </label>
                <div style={{ marginTop: '10px' }}>
                  <div className="advanced-section-title">章节识别</div>
                  {txtPath ? (
                    <>
                      <div className="scan-results-inline">
                        {isScanning ? (
                          <div style={{ color: 'var(--text-muted)' }}>扫描中...</div>
                        ) : (
                          scanResults.map((res, idx) => (
                            <div
                              key={idx}
                              onClick={() => handlePatternSelect(idx)}
                              className={`scan-result-item ${selectedPatternIndex === idx ? 'selected' : ''}`}
                            >
                              <span>{res.name}</span>
                              <span style={{ fontWeight: 'bold' }}>{res.count} 章</span>
                            </div>
                          ))
                        )}
                      </div>

                    </>
                  ) : (
                    <div style={{ fontSize: '0.85em', color: 'var(--text-muted)' }}>请先选择文件以扫描章节结构</div>
                  )}
                </div>

                <div style={{ marginTop: '10px' }}>
                  <div className="advanced-section-title">自定义正则表达式</div>
                  <input
                    placeholder="例如: ^第.+章"
                    value={customRegex}
                    onChange={e => {
                      setCustomRegex(e.target.value);
                      setSelectedPatternIndex(-1); // Clear selection if typing manually
                    }}
                    style={{ fontSize: '0.85em' }}
                  />
                </div>

                <div className="advanced-section-divider">
                  <div className="advanced-section-title">匹配到的规则 (设置标题级别)</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {allScanResults.length > 0 ? (
                      allScanResults.map(result => (
                        <div key={result.name} style={{
                          display: 'flex',
                          alignItems: 'center',
                          fontSize: '0.85em',
                          gap: '8px',
                          padding: '4px 0'
                        }}>
                          <input
                            type="checkbox"
                            checked={!disabledPatterns.has(result.name)}
                            onChange={e => {
                              const newSet = new Set(disabledPatterns);
                              if (e.target.checked) {
                                newSet.delete(result.name);
                              } else {
                                newSet.add(result.name);
                              }
                              setDisabledPatterns(newSet);
                            }}
                            style={{ width: 'auto' }}
                          />
                          <select
                            value={patternLevels[result.name] || 1}
                            onChange={e => {
                              setPatternLevels(prev => ({
                                ...prev,
                                [result.name]: parseInt(e.target.value)
                              }));
                            }}
                            disabled={disabledPatterns.has(result.name)}
                            style={{
                              width: '55px',
                              padding: '2px 4px',
                              fontSize: '0.9em',
                              opacity: disabledPatterns.has(result.name) ? 0.5 : 1
                            }}
                          >
                            <option value={1}>h1</option>
                            <option value={2}>h2</option>
                            <option value={3}>h3</option>
                            <option value={4}>h4</option>
                            <option value={5}>h5</option>
                            <option value={6}>h6</option>
                          </select>
                          <span style={{
                            flex: 1,
                            opacity: disabledPatterns.has(result.name) ? 0.5 : 1
                          }}>
                            {result.name}
                          </span>
                          <span style={{
                            color: 'var(--accent)',
                            fontWeight: 'bold',
                            fontSize: '0.9em',
                            opacity: disabledPatterns.has(result.name) ? 0.5 : 1
                          }}>
                            {result.count} 章
                          </span>
                        </div>
                      ))
                    ) : (
                      <div style={{ fontSize: '0.85em', color: 'var(--text-muted)' }}>
                        {txtPath ? '扫描中...' : '请先选择文件'}
                      </div>
                    )}
                  </div>
                </div>


              </div>
            </div>
          )}
        </div>



        <div style={{ marginTop: 'auto' }}>
          {loading && (
            <div style={{ marginBottom: '10px' }}>
              <div className="progress-bar-bg">
                <div className="progress-bar-fill" style={{ width: `${progress}%` }}></div>
              </div>
              <div style={{ textAlign: 'right', fontSize: '0.8em', color: '#666', marginTop: '2px' }}>{progress}%</div>
            </div>
          )}
          <button
            className="primary"
            onClick={convert}
            disabled={loading || !txtPath}
            style={{ width: '100%', padding: '15px', fontSize: '1.1em' }}
          >
            {loading ? "正在转换..." : "开始转换"}
          </button>
        </div>
      </div>

      {/* Right Panel: Logs & Output */}
      <div className="right-panel">
        <div className="section-title">输出日志</div>
        <div className="log-container">
          {logs.length === 0 && <div style={{ color: '#666', fontStyle: 'italic' }}>等待操作...</div>}
          {logs.map((log, i) => (
            <div key={i} className="log-entry">
              {log}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>

        {/* Full Chapter List Section - Moved to Right Panel */}
        {selectedPatternIndex >= 0 && scanResults[selectedPatternIndex] && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div className="section-title">完整章节列表 ({scanResults[selectedPatternIndex].chapters.length})</div>
            <div className="chapter-list-container">
              {scanResults[selectedPatternIndex].chapters.map((chapter, i) => (
                <div key={i} className="chapter-list-item">
                  <span className="chapter-index">{i + 1}.</span>
                  <span className="chapter-title">{chapter}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
