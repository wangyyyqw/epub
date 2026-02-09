import { useState, useRef, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open, save } from "@tauri-apps/plugin-dialog";
import "./App.css";

interface ScanResult {
  name: string;
  pattern: string;
  count: number;
  chapters: string[];
  suggested_level?: number;
  example?: string;
}

// Start with 'converter' or 'tool'
type ViewMode = 'converter' | 'tool';

function App() {

  const [viewMode, setViewMode] = useState<ViewMode>('converter');
  const [toolOperation, setToolOperation] = useState<string>('reformat');

  // Helper to add paths with deduplication
  const addToolInputPaths = (newPaths: string[]) => {
    setToolInputPaths(prev => {
      const existing = new Set(prev);
      const unique = newPaths.filter(p => !existing.has(p));
      if (unique.length === 0) return prev;
      return [...prev, ...unique];
    });
  };

  const removeToolInputPath = (index: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent ensuring parent click
    setToolInputPaths(prev => prev.filter((_, i) => i !== index));
  };

  const clearToolInputPaths = (e: React.MouseEvent) => {
    e.stopPropagation();
    setToolInputPaths([]);
  };

  useEffect(() => {
    // File Drop handling
    const unlistenPromise = listen<string[]>('tauri://file-drop', (event) => {
      const paths = event.payload;
      if (paths && paths.length > 0) {
        if (viewMode === 'tool') {
          // Filter for EPUBs
          const epubs = paths.filter(p => p.toLowerCase().endsWith('.epub'));
          if (epubs.length > 0) {
            addToolInputPaths(epubs);
            addLog(`已添加拖拽文件: ${epubs.length} 个`);
          }
        } else if (viewMode === 'converter') {
          // Handle TXT drop
          const txt = paths.find(p => p.toLowerCase().endsWith('.txt'));
          if (txt) {
            setTxtPath(txt);
            addLog(`已识别拖拽文件: ${txt}`);
            const filename = txt.split(/[\\/]/).pop()?.replace('.txt', '') || "";
            setTitle(filename);
            scanFile(txt);
          }
        }
      }
    });

    return () => {
      unlistenPromise.then(unlisten => unlisten());
    };
  }, [viewMode]); // Re-bind when viewMode changes to ensure correct logic context

  // Data States
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
  const [allScanResults, setAllScanResults] = useState<ScanResult[]>([]);
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [patternLevels] = useState<Record<string, number>>({});

  // Tool State
  const [toolInputPaths, setToolInputPaths] = useState<string[]>([]);
  const [toolFontPath, setToolFontPath] = useState('');
  const [toolRegexPattern, setToolRegexPattern] = useState('\\[(\\d+)\\]');

  // Batch Processing State
  const [currentFileIndex, setCurrentFileIndex] = useState<number>(-1);
  const [isBatchProcessing, setIsBatchProcessing] = useState(false);

  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  useEffect(() => {
    const unlistenPromise = listen<string>('epub_tool_log', (event) => {
      const message = event.payload.trim();
      if (message) {
        addLog(message);
      }
    });

    return () => {
      unlistenPromise.then(unlisten => unlisten());
    };
  }, []);

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
    const match = line.match(/PROGRESS:\s*(\d+)%/);
    if (match) {
      setProgress(parseInt(match[1]));
    }
  }

  async function scanFile(path: string) {
    setScanResults([]);
    setAllScanResults([]);
    addLog("正在扫描章节结构...");

    try {
      const jsonResult = await invoke("scan_chapters", { txtPath: path });
      let results: ScanResult[] = [];
      try {
        const parsed = JSON.parse(jsonResult as string);
        if (Array.isArray(parsed)) {
          results = parsed;
        } else if (parsed.patterns) {
          results = parsed.patterns || [];
        }
      } catch (parseErr) {
        addLog(`[ERROR] JSON解析失败: ${parseErr}`);
      }

      const matchedResults = results.filter(r => r.count > 0);
      matchedResults.sort((a, b) => b.count - a.count);
      setAllScanResults(matchedResults);
      const filteredResults = matchedResults.filter(r => !disabledPatterns.has(r.name));
      setScanResults(filteredResults);

      const totalChapters = filteredResults.reduce((sum, r) => sum + r.count, 0);
      if (filteredResults.length > 0) {
        addLog(`扫描完成，发现 ${filteredResults.length} 个匹配规则，共 ${totalChapters} 个章节标记`);
      } else {
        addLog("扫描完成，未发现匹配章节。");
      }
    } catch (e) {
      addLog(`扫描失败: ${e}`);
    }
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
        const filename = path.split(/[\\/]/).pop()?.replace('.txt', '') || "";
        setTitle(filename);
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
      setLoading(false);
    }
  }

  async function selectToolEpub() {
    try {
      const selected = await open({
        multiple: true,
        filters: [{ name: 'EPUB', extensions: ['epub'] }]
      });
      if (selected) {
        const paths = Array.isArray(selected) ? selected : [selected];
        addToolInputPaths(paths);
        addLog(`已添加 ${paths.length} 个文件`);
      }
    } catch (err) {
      addLog(`选择文件出错: ${err}`);
    }
  }

  async function selectToolFont() {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: 'Font', extensions: ['ttf', 'otf', 'woff', 'woff2'] }]
      });
      if (selected) {
        const path = selected as string;
        setToolFontPath(path);
        addLog(`已选择字体: ${path}`);
      }
    } catch (err) {
      addLog(`选择文件出错: ${err}`);
    }
  }

  async function runToolOperation() {
    if (toolInputPaths.length === 0) {
      addLog("错误: 请先选择 EPUB 文件。");
      return;
    }
    if (toolOperation === 'encrypt' && !toolFontPath) {
      addLog("提示: 加密操作建议选择字体文件");
    }

    setLoading(true);
    setIsBatchProcessing(true);
    setProgress(0);

    const total = toolInputPaths.length;
    addLog(`开始批量执行 ${toolOperation} 操作，共 ${total} 个文件...`);

    try {
      for (let i = 0; i < total; i++) {
        const inputPath = toolInputPaths[i];
        setCurrentFileIndex(i);
        const filename = inputPath.split(/[\\/]/).pop();
        addLog(`[${i + 1}/${total}] 正在处理: ${filename}...`);

        try {
          const result = await invoke("run_epub_tool", {
            operation: toolOperation,
            inputPath: inputPath,
            fontPath: toolFontPath || null,
            regexPattern: toolRegexPattern || null
          });

          const lines = (result as string).split('\n');
          lines.forEach(line => {
            if (line.trim()) {
              addLog(`> ${line}`);
            }
          });
        } catch (fileErr) {
          addLog(`[ERROR] 文件 ${filename} 处理失败: ${fileErr}`);
        }

        // Update progress bar based on file count
        setProgress(Math.round(((i + 1) / total) * 100));
      }

      addLog(`批量 ${toolOperation} 操作完成。`);
    } catch (error) {
      addLog(`严重系统错误: ${error}`);
    } finally {
      setLoading(false);
      setIsBatchProcessing(false);
      setCurrentFileIndex(-1);
      setProgress(100);
    }
  }

  // Helper to switch modes
  const switchTool = (op: string) => {
    setViewMode('tool');
    setToolOperation(op);
  };

  const switchToConverter = () => {
    setViewMode('converter');
  };

  return (
    <div className="app-container" style={{ animation: 'fadeIn 0.5s ease-out' }}>

      {/* LEFT NAVIGATION SIDEBAR */}
      <div className="sidebar glass-panel">
        <h2 style={{ fontSize: '18px', margin: '0 0 10px 16px', color: 'var(--accent-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          epub 工具箱
        </h2>

        <div
          className={`sidebar-item ${viewMode === 'converter' ? 'active' : ''}`}
          onClick={switchToConverter}
        >
          <span>TXT 转 EPUB</span>
        </div>

        <div className="nav-group-title">基础处理</div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'reformat' ? 'active' : ''}`} onClick={() => switchTool('reformat')}>
          <span>格式化</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'encrypt' ? 'active' : ''}`} onClick={() => switchTool('encrypt')}>
          <span>加密</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'encrypt_font' ? 'active' : ''}`} onClick={() => switchTool('encrypt_font')}>
          <span>字体加密</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'decrypt' ? 'active' : ''}`} onClick={() => switchTool('decrypt')}>
          <span>解密</span>
        </div>

        <div className="nav-group-title">文本与辅助</div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 's2t' ? 'active' : ''}`} onClick={() => switchTool('s2t')}>
          <span>简体转繁体</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 't2s' ? 'active' : ''}`} onClick={() => switchTool('t2s')}>
          <span>繁体转简体</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'phonetic' ? 'active' : ''}`} onClick={() => switchTool('phonetic')}>
          <span>生僻字注音</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'yuewei' ? 'active' : ''}`} onClick={() => switchTool('yuewei')}>
          <span>阅微转多看</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'footnote' ? 'active' : ''}`} onClick={() => switchTool('footnote')}>
          <span>正则脚注</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'comment' ? 'active' : ''}`} onClick={() => switchTool('comment')}>
          <span>正则注释</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'footnote_conv' ? 'active' : ''}`} onClick={() => switchTool('footnote_conv')}>
          <span>脚注链接转注释</span>
        </div>

        <div className="nav-group-title">资源优化</div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'font_subset' ? 'active' : ''}`} onClick={() => switchTool('font_subset')}>
          <span>字体子集化</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'download_images' ? 'active' : ''}`} onClick={() => switchTool('download_images')}>
          <span>下载网络图片</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'img_compress' ? 'active' : ''}`} onClick={() => switchTool('img_compress')}>
          <span>图片无损压缩</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'img_to_webp' ? 'active' : ''}`} onClick={() => switchTool('img_to_webp')}>
          <span>图片转 WebP</span>
        </div>
        <div className={`sidebar-item ${viewMode === 'tool' && toolOperation === 'webp_to_img' ? 'active' : ''}`} onClick={() => switchTool('webp_to_img')}>
          <span>WebP 转图片</span>
        </div>
      </div>

      {/* RIGHT WORKSPACE AREA */}
      <div className="main-content">

        {/* INPUT PANEL (DYNAMIC) */}
        <div className="left-panel glass-panel">
          {viewMode === 'converter' ? (
            <>
              <h1 style={{ fontSize: '24px' }}>TXT 转 EPUB</h1>
              <div className="left-panel-scroll">
                <div>
                  <div className="section-title">1. 选择文件</div>
                  <div className="file-drop-area" onClick={selectTxt}>
                    {txtPath ? (
                      <div className="file-name" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {txtPath.split(/[\\/]/).pop()}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '14px', fontWeight: 500 }}>点击选择 .txt 文件</span>
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <div className="section-title">2. params</div>
                  <input placeholder="书籍标题 *" value={title} onChange={e => setTitle(e.target.value)} style={{ marginBottom: '10px' }} />
                  <input placeholder="作者" value={author} onChange={e => setAuthor(e.target.value)} />
                </div>

                {/* Advanced Options & Chapter List */}
                <div>
                  <div className="section-title" style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }} onClick={() => setShowAdvanced(!showAdvanced)}>
                    <span>3. 高级选项 & 章节</span>
                    <span style={{ marginLeft: 'auto' }}>{showAdvanced ? '▼' : '▶'}</span>
                  </div>
                  {showAdvanced && (
                    <div className="advanced-options-container">
                      <label style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}><input type="checkbox" checked={removeEmptyLines} onChange={e => setRemoveEmptyLines(e.target.checked)} style={{ width: 'auto', marginRight: '8px' }} />去除多余空行</label>
                      <label style={{ display: 'flex', alignItems: 'center' }}><input type="checkbox" checked={fixIndent} onChange={e => setFixIndent(e.target.checked)} style={{ width: 'auto', marginRight: '8px' }} />修正首行缩进</label>

                      <div style={{ marginTop: '12px' }}>
                        <div className="advanced-section-title">正则表达式</div>
                        <input value={customRegex} onChange={e => { setCustomRegex(e.target.value); }} placeholder="^第.+章" />
                      </div>

                      {/* Simplified Pattern List */}
                      {allScanResults.length > 0 && (
                        <div style={{ marginTop: '12px' }}>
                          <div className="advanced-section-title">自动识别</div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            {allScanResults.map((r, idx) => (
                              <div key={idx} style={{ fontSize: '12px', padding: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', display: 'flex', justifyContent: 'space-between' }}>
                                <span>{r.name} ({r.count})</span>
                                <input type="checkbox" checked={!disabledPatterns.has(r.name)} onChange={e => {
                                  const newSet = new Set(disabledPatterns);
                                  if (e.target.checked) newSet.delete(r.name); else newSet.add(r.name);
                                  setDisabledPatterns(newSet);
                                }} style={{ width: 'auto' }} />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="left-panel-footer">
                {loading && <div style={{ textAlign: 'center', marginBottom: '8px', fontSize: '12px' }}>{progress}%</div>}
                <button className="primary" onClick={convert} disabled={loading}>{loading ? '转换中...' : '开始转换'}</button>
              </div>
            </>
          ) : (
            <>
              {/* TOOL VIEW */}
              <h1 style={{ fontSize: '24px' }}>{
                // Map operation key to readable title
                {
                  'reformat': '格式化', 'encrypt': '加密', 'encrypt_font': '字体加密', 'decrypt': '解密',
                  's2t': '简体转繁体', 't2s': '繁体转简体', 'phonetic': '生僻字注音',
                  'yuewei': '阅微转多看', 'footnote': '正则脚注',
                  'font_subset': '字体子集化', 'img_compress': '图片压缩', 'download_images': '下载网络图片', 'img_to_webp': '图片转 WebP', 'webp_to_img': 'WebP 转图片',
                  'comment': '正则注释', 'footnote_conv': '脚注链接转注释'
                }[toolOperation] || toolOperation
              }</h1>

              <div className="left-panel-scroll">
                <div>
                  <div className="section-title">1. 选择 EPUB (可拖拽多选)</div>
                  <div
                    className="file-drop-area"
                    onClick={selectToolEpub}
                    // Prevent default to allow drop visual feedback, but allow propagation so Tauri sees it
                    onDragOver={(e) => {
                      e.preventDefault();
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      // Data handled by global listener
                    }}
                  >
                    {toolInputPaths.length > 0 ? (
                      <div style={{ width: '100%', textAlign: 'left' }}>
                        <div style={{ maxHeight: '160px', overflowY: 'auto', marginBottom: '8px', paddingRight: '4px' }}>
                          {toolInputPaths.map((path, idx) => (
                            <div key={idx} className="file-item-row" style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              marginBottom: '4px',
                              background: 'rgba(255,255,255,0.05)',
                              borderRadius: '4px',
                              padding: '6px 8px',
                              fontSize: '12px',
                            }} onClick={(e) => { e.stopPropagation(); }}>
                              <div style={{
                                flex: 1,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                marginRight: '8px'
                              }}>
                                {path.split(/[\\/]/).pop()}
                              </div>
                              <div
                                className="delete-btn"
                                onClick={(e) => removeToolInputPath(idx, e)}
                                style={{
                                  cursor: 'pointer',
                                  color: 'var(--text-muted)',
                                  fontWeight: 'bold',
                                  fontSize: '14px',
                                  padding: '0 4px'
                                }}
                                onMouseOver={(e) => e.currentTarget.style.color = '#ff6b6b'}
                                onMouseOut={(e) => e.currentTarget.style.color = 'var(--text-muted)'}
                              >
                                ×
                              </div>
                            </div>
                          ))}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>共 {toolInputPaths.length} 个文件</span>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                              className="secondary"
                              style={{ padding: '2px 8px', fontSize: '11px', height: 'auto', background: 'transparent', border: '1px solid var(--border-color)' }}
                              onClick={clearToolInputPaths}
                            >
                              清空
                            </button>
                          </div>
                        </div>
                        <div style={{ textAlign: 'center', marginTop: '8px', fontSize: '11px', color: 'var(--accent-primary)', cursor: 'pointer' }}>
                          + 点击或拖拽添加更多
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '14px', fontWeight: 500 }}>点击选择或拖拽 .epub</span>
                      </div>
                    )}
                  </div>
                </div>

                {toolOperation === 'encrypt' && (
                  <div>
                    <div className="section-title">2. 选择字体 (可选)</div>
                    <div className="file-drop-area" onClick={selectToolFont}>
                      {toolFontPath ? <span className="file-name">{toolFontPath.split(/[\\/]/).pop()}</span> : <span>选择字体文件</span>}
                    </div>
                  </div>
                )}

                {(toolOperation === 'footnote' || toolOperation === 'comment') && (
                  <div>
                    <div className="section-title">2. 匹配正则</div>
                    <input value={toolRegexPattern} onChange={e => setToolRegexPattern(e.target.value)} />
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>默认: \[(\d+)\] (注释: \[.*\])</div>
                  </div>
                )}
              </div>

              <div className="left-panel-footer">
                {isBatchProcessing && <div style={{ textAlign: 'center', marginBottom: '8px', fontSize: '12px' }}>
                  处理中: [{currentFileIndex + 1}/{toolInputPaths.length}] {progress}%
                </div>}
                {!isBatchProcessing && loading && <div style={{ textAlign: 'center', marginBottom: '8px', fontSize: '12px' }}>{progress}%</div>}
                <button className="primary" onClick={runToolOperation} disabled={loading || toolInputPaths.length === 0}>{loading ? '处理中...' : '执行任务'}</button>
              </div>
            </>
          )}
        </div>

        {/* LOGS PANEL (ALWAYS VISIBLE) */}
        <div className="right-panel glass-panel">
          <div className="section-title">任务日志</div>
          <div className="log-container">
            {logs.length === 0 && <div style={{ opacity: 0.5 }}>等待操作...</div>}
            {logs.map((log, i) => <div key={i} className="log-entry">{log}</div>)}
            <div ref={logEndRef} />
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;
