import { useEffect, useRef, useState } from "react";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import "./App.css";
import { decimal, localizeApiMessage, number, percent } from "./locale.js";

const FLUIDS = [
  { key: "Oil", label: "Óleo", color: "#e3676d" },
  { key: "Water", label: "Água", color: "#749de8" },
  { key: "Gas", label: "Gás", color: "#77c6a3" },
];

function Icon({ name, size = 20, ...props }) {
  const paths = {
    plus: <path d="M12 5v14M5 12h14" />,
    scan: (
      <>
        <path d="M8 3H4a1 1 0 0 0-1 1v4m13-5h4a1 1 0 0 1 1 1v4M3 16v4a1 1 0 0 0 1 1h4m8 0h4a1 1 0 0 0 1-1v-4M7 12h10" />
        <path d="M12 7v10" />
      </>
    ),
    chart: <path d="M4 4v16h17M9 16v-5m5 5V6m5 10v-8" />,
    upload: (
      <path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5" />
    ),
    arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
    down: <path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4" />,
    chevron: <path d="m9 5 7 7-7 7" />,
    back: <path d="m15 5-7 7 7 7" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    image: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="3" />
        <circle cx="8" cy="8" r="1.5" />
        <path d="m3 17 6-6 4 4 3-3 5 5" />
      </>
    ),
    layers: (
      <path d="m12 3 10 6-10 6L2 9l10-6Zm-10 12 10 6 10-6M2 12l10 6 10-6" />
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    table: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 9h18M3 14h18M9 9v11" />
      </>
    ),
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 6 6" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    expand: <path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" />,
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6m0-10v1" />
      </>
    ),
    drop: <path d="M12 2C9 7 5 10 5 15a7 7 0 0 0 14 0c0-5-4-8-7-13Z" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name] || paths.scan}
    </svg>
  );
}

async function request(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error(
      "Falha na conexão com o servidor de análise. O servidor Python precisa estar em execução.",
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      typeof data?.detail === "string"
        ? localizeApiMessage(data.detail)
        : "Servidor de análise indisponível. Detalhes no terminal do servidor Python.",
    );
  return data;
}

function Shell() {
  const [online, setOnline] = useState(null);
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname]);
  useEffect(() => {
    let mounted = true;
    const check = () =>
      request("/api/health")
        .then((data) => {
          if (mounted) setOnline(data.models_available);
        })
        .catch(() => {
          if (mounted) setOnline(false);
        });
    check();
    const interval = setInterval(check, 30000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link
          to="/"
          className="lab-brand"
          aria-label="Página inicial do LabMEMS"
        >
          <img src="/brand/labmems.png" alt="LabMEMS" />
          <span>ANÁLISE DE MICROMODELOS</span>
        </Link>
        <div className="sidebar-rule" />
        <span className="nav-label">ÁREA DE TRABALHO</span>
        <nav aria-label="Navegação principal">
          <NavLink to="/" end>
            <Icon name="plus" />
            <span>Nova análise</span>
            <span className="nav-shortcut">01</span>
          </NavLink>
          <NavLink to="/analysis/sample">
            <Icon name="chart" />
            <span>Análise de exemplo</span>
            <span className="nav-shortcut">02</span>
          </NavLink>
        </nav>
        <div className="sidebar-note">
          <div className="tiny-orbit">
            <Icon name="scan" size={23} />
          </div>
          <p>
            Análise de imagens
            <br />
            de micromodelos.
          </p>
          <span>
            Segmentação de fases
            <br />
            e detecção de regiões.
          </span>
        </div>
        <div className="sidebar-footer">
          <img
            className="ufrj-logo"
            src="/brand/ufrj.png"
            alt="Universidade Federal do Rio de Janeiro — UFRJ"
          />
          <p>Laboratório de Nano e Microfluídica e Microssistemas</p>
          <span>Uso interno · LabMEMS / UFRJ</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <Link className="workspace-name" to="/">
            <span className="brand-mark">
              <Icon name="scan" size={19} />
            </span>
            <span>
              Micro<span className="muted">Flow</span>
            </span>
            <span className="workspace-divider" />
            <span className="workspace-subtitle">Ambiente de pesquisa</span>
          </Link>
          <div className="connection">
            <span
              className={`status-dot ${online === false ? "offline" : ""}`}
            />
            {online === null
              ? "Conectando…"
              : online
                ? "Servidor de análise disponível"
                : "Servidor de análise desconectado"}
            <span className="local-pill">LOCAL</span>
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<UploadPage online={online} />} />
            <Route path="/analysis/:id" element={<AnalysisPage />} />
            <Route
              path="*"
              element={
                <div className="empty-state">
                  <h1>Página não encontrada</h1>
                  <Link className="primary-button" to="/">
                    Nova análise <Icon name="arrow" />
                  </Link>
                </div>
              }
            />
          </Routes>
        </main>
        <footer className="page-footer">
          <span>
            <img
              className="footer-ufrj ufrj-logo"
              src="/brand/ufrj.png"
              alt="UFRJ"
            />
            LabMEMS <span className="footer-dot">·</span> Universidade Federal
            do Rio de Janeiro
          </span>
          <div className="footer-credits">
            <div
              className="shell-acknowledgment"
              aria-label="Agradecimentos à Shell"
            >
              <span>Agradecimentos à Shell</span>
              <img src="/brand/shell.png" alt="Shell" width="33" height="33" />
            </div>
            <span className="footer-version">
              MicroFlow <span className="version">v0.1</span>
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}

function UploadPage({ online }) {
  const input = useRef(null);
  const navigate = useNavigate();
  const [selected, setSelected] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  useEffect(
    () => () => {
      if (selected?.url) URL.revokeObjectURL(selected.url);
    },
    [selected],
  );
  function choose(file) {
    setError("");
    if (!file) return;
    if (!/\.(png|jpe?g|tiff?|webp)$/i.test(file.name)) {
      setError("Formato não suportado. Formatos aceitos: PNG, JPG, TIFF e WebP.");
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setError("A imagem deve ter no máximo 25 MB.");
      return;
    }
    setSelected({ file, url: URL.createObjectURL(file) });
  }
  async function start() {
    if (!selected || uploading) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("image", selected.file);
      const job = await request("/api/analyses", {
        method: "POST",
        body: form,
      });
      navigate(`/analysis/${job.id}`);
    } catch (e) {
      setError(e.message);
      setUploading(false);
    }
  }
  return (
    <div className="page upload-page">
      <div className="breadcrumb">
        <span>Área de trabalho</span>
        <Icon name="chevron" size={13} />
        <span>Nova análise</span>
      </div>
      <section className="upload-intro">
        <div>
          <span className="eyebrow">
            <span />
            PROCESSAMENTO DE IMAGENS
          </span>
          <h1>Análise de micromodelo</h1>
          <p>
            Segmentação de fases, detecção de Dead ends
            <br className="desktop-break" /> e quantificação da composição dos fluidos.
          </p>
        </div>
        <div className="intro-coordinate">
          <span>LABMEMS / UFRJ</span>
          <div className="coordinate-cross">+</div>
          <span>MICROFLUÍDICA</span>
        </div>
      </section>
      <div className="upload-layout">
        <section className="panel upload-panel">
          <div className="section-heading">
            <div>
              <span className="step-label">01 / IMAGEM DE ENTRADA</span>
              <h2>Importação de imagem</h2>
            </div>
            <Icon name="image" size={24} />
          </div>
          <input
            ref={input}
            type="file"
            accept=".png,.jpg,.jpeg,.tif,.tiff,.webp"
            onChange={(event) => choose(event.target.files?.[0])}
            className="visually-hidden"
            aria-label="Enviar uma imagem do micromodelo"
          />
          <button
            type="button"
            className={`dropzone ${dragging ? "dragging" : ""} ${selected ? "has-image" : ""}`}
            onClick={() => input.current?.click()}
            disabled={uploading}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              choose(event.dataTransfer.files[0]);
            }}
          >
            {selected ? (
              <>
                <img
                  className="upload-preview"
                  src={selected.url}
                  alt="Prévia do micromodelo selecionado"
                  onError={(event) => {
                    event.currentTarget.style.display = "none";
                  }}
                />
                <div className="selected-file">
                  <span className="selected-check">
                    <Icon name="check" size={16} />
                  </span>
                  <span>{selected.file.name}</span>
                  <span>{decimal(selected.file.size / 1024 / 1024, 1)} MB</span>
                </div>
                <span className="change-image">
                  Substituir imagem
                </span>
              </>
            ) : (
              <>
                <span className="upload-icon">
                  <Icon name="upload" size={30} />
                </span>
                <h3>Imagem do micromodelo</h3>
                <p>
                  <span className="browse-text">Selecionar arquivo</span> ou arrastar a imagem para esta área.
                </p>
                <span className="format-list">
                  PNG, JPG, TIFF ou WebP <span>·</span> Até 25 MB
                </span>
              </>
            )}
          </button>
          <div className="upload-tip">
            <Icon name="info" size={16} />
            <span>
              Entrada: imagem original do micromodelo, sem anotações ou sobreposições.
            </span>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <Icon name="info" size={17} />
              {error}
            </div>
          )}
          <div className="upload-action">
            <span>
              <Icon name="layers" size={16} />
              Processamento local
            </span>
            <button
              className="primary-button"
              disabled={!selected || uploading || online === false}
              onClick={start}
            >
              {uploading ? (
                <>
                  <span className="spinner" />
                  Enviando…
                </>
              ) : (
                <>
                  Analisar imagem
                  <Icon name="arrow" size={18} />
                </>
              )}
            </button>
          </div>
          {online === false && (
            <p className="offline-help">
              Servidor Python indisponível. Instruções de inicialização no README do projeto.
            </p>
          )}
        </section>
        <aside className="pipeline-panel">
          <span className="step-label">ETAPAS DO PROCESSAMENTO</span>
          <h2>Fluxo de análise</h2>
          <p className="pipeline-description">
            Segmentação semântica, detecção de regiões e análise da composição dos fluidos.
          </p>
          <div className="pipeline-steps">
            {[
              {
                n: "01",
                icon: "layers",
                title: "Segmentação semântica",
                desc: "Classificação dos pixels em parede, água, óleo e gás.",
              },
              {
                n: "02",
                icon: "scan",
                title: "Detecção de Dead ends",
                desc: "Identificação das regiões de Dead ends.",
              },
              {
                n: "03",
                icon: "chart",
                title: "Composição dos fluidos",
                desc: "Cálculo das frações de água, óleo e gás por região.",
              },
            ].map((item) => (
              <div className="pipeline-step" key={item.n}>
                <span className="pipeline-step-icon">
                  <Icon name={item.icon} />
                </span>
                <div>
                  <span>{item.n}</span>
                  <h3>{item.title}</h3>
                  <p>{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="phase-legend">
            <span>FASES FLUIDAS</span>
            <div>
              {FLUIDS.map((fluid) => (
                <span key={fluid.key}>
                  <i style={{ background: fluid.color }} />
                  {fluid.label}
                </span>
              ))}
            </div>
          </div>
        </aside>
      </div>
      <section className="sample-banner">
        <div className="sample-image">
          <img src="/api/sample-image" alt="Micromodelo de exemplo" />
          <span className="sample-corner" />
        </div>
        <div className="sample-description">
          <span className="step-label">ANÁLISE DE EXEMPLO</span>
          <h3>Resultados de uma imagem de exemplo</h3>
          <p>
            Resultados de segmentação, detecção de Dead ends e composição dos fluidos.
          </p>
        </div>
        <Link className="secondary-button" to="/analysis/sample">
          Abrir exemplo
          <Icon name="arrow" size={17} />
        </Link>
      </section>
      <div className="upload-bottom">
        <span>
          <Icon name="check" size={14} />
          Processamento local com armazenamento dos arquivos no diretório do projeto.
        </span>
        <span>
          DCA UNet <span>+</span> YOLOv5
        </span>
      </div>
    </div>
  );
}

function AnalysisPage() {
  const { id } = useParams();
  return <AnalysisLoader key={id} id={id} />;
}

function AnalysisLoader({ id }) {
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true,
      timer;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const data = await request(`/api/analyses/${encodeURIComponent(id)}`, {
          signal: controller.signal,
        });
        if (!active) return;
        setAnalysis(data);
        setError("");
        if (["queued", "processing"].includes(data.status))
          timer = setTimeout(poll, 1400);
      } catch (e) {
        if (active && e.name !== "AbortError") setError(e.message);
      }
    };
    poll();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [id, attempt]);
  if (error || analysis?.status === "failed")
    return (
      <div className="page">
        <div className="empty-state">
          <span className="upload-icon">
            <Icon name="info" size={28} />
          </span>
          <h1>Falha na análise</h1>
          <p role="alert">{error || localizeApiMessage(analysis.error)}</p>
          <div className="button-row">
            <button
              className="secondary-button"
              onClick={() => setAttempt((value) => value + 1)}
            >
              Tentar novamente
            </button>
            <Link className="primary-button" to="/">
              Nova análise
              <Icon name="plus" size={18} />
            </Link>
          </div>
        </div>
      </div>
    );
  if (!analysis || analysis.status !== "completed")
    return <Processing analysis={analysis} />;
  return <Results analysis={analysis} />;
}

function Processing({ analysis }) {
  const stages = [
    "queued",
    "segmentation",
    "detection",
    "composition",
    "completed",
  ];
  const current = stages.indexOf(analysis?.stage || "queued");
  return (
    <div className="page">
      <div className="processing-card panel">
        <div className="processing-orbit">
          <Icon name="scan" size={38} />
        </div>
        <span className="eyebrow">STATUS DO PROCESSAMENTO</span>
        <h1>Processamento em andamento</h1>
        <p>{analysis?.filename || "Carregamento da análise…"}</p>
        <div className="processing-steps">
          {[
            "Segmentação das fases",
            "Detecção de Dead ends",
            "Cálculo da composição",
          ].map((label, index) => (
            <div
              key={label}
              className={
                current > index + 1
                  ? "done"
                  : current === index + 1
                    ? "working"
                    : ""
              }
            >
              <span>
                {current > index + 1 ? (
                  <Icon name="check" size={16} />
                ) : current === index + 1 ? (
                  <span className="spinner" />
                ) : (
                  `0${index + 1}`
                )}
              </span>
              {label}
            </div>
          ))}
        </div>
        <p className="processing-note">
          Processamento local. O tempo de execução depende das dimensões da imagem e dos recursos computacionais.
        </p>
      </div>
    </div>
  );
}

function Metric({ icon, label, value, unit, note, accent }) {
  return (
    <div className={`metric ${accent ? "metric-accent" : ""}`}>
      <div className="metric-top">
        <span>{label}</span>
        <Icon name={icon} size={18} />
      </div>
      <div className="metric-value">
        {value}
        <span>{unit}</span>
      </div>
      <p>{note}</p>
    </div>
  );
}

function Results({ analysis }) {
  const [view, setView] = useState("original");
  const [expanded, setExpanded] = useState(false);
  const views = [
    { key: "original", label: "Original" },
    { key: "segmentation", label: "Segmentação" },
    { key: "detection", label: "Detecção" },
    { key: "overlay", label: "Sobreposição" },
  ];
  const activeView = views.find((item) => item.key === view);
  return (
    <div className="page results-page">
      <div className="breadcrumb">
        <Link to="/">Área de trabalho</Link>
        <Icon name="chevron" size={13} />
        <span>Resultados da análise</span>
        <Icon name="chevron" size={13} />
        <span className="file-crumb">{analysis.filename}</span>
      </div>
      <div className="results-heading">
        <div>
          <span className="eyebrow">
            <span />
            SEGMENTAÇÃO, DETECÇÃO E COMPOSIÇÃO
          </span>
          <h1>Resultados da análise</h1>
          <div className="file-meta">
            <Icon name="image" size={15} />
            <span>{analysis.filename}</span>
            <i />
            {analysis.image_size_wh.join(" × ")} px
            <i />
            <span className="complete-label">
              <Icon name="check" size={13} />
              Análise concluída
            </span>
            {analysis.is_sample && <span className="sample-tag">EXEMPLO</span>}
          </div>
        </div>
        <div className="button-row">
          <Link to="/" className="secondary-button">
            <Icon name="plus" size={17} />
            Nova análise
          </Link>
          <a href={analysis.assets.csv} download className="primary-button">
            <Icon name="down" size={17} />
            Exportar CSV
          </a>
        </div>
      </div>
      <section className="metrics" aria-label="Resumo da análise">
        <Metric
          icon="scan"
          label="Dead ends detectados"
          value={number(analysis.deadend_count)}
          note="Confiança ≥ 70%"
        />
        <Metric
          icon="grid"
          label="Área das caixas"
          value={decimal(analysis.coverage_percent)}
          unit="%"
          note="Da imagem completa do micromodelo"
        />
        <Metric
          icon="drop"
          label="Óleo nos Dead ends"
          value={
            analysis.composition.deadends.class_fractions.Oil == null
              ? "—"
              : decimal(analysis.composition.deadends.class_fractions.Oil * 100)
          }
          unit="%"
          note="Dos pixels de fluido nas caixas"
          accent
        />
        <Metric
          icon="clock"
          label="Tempo de processamento"
          value={decimal(analysis.inference_seconds, 1)}
          unit="s"
          note={`${analysis.device.toUpperCase()} · Inferência local`}
        />
      </section>
      <div className="results-visuals">
        <section className="panel viewer-panel">
          <div className="panel-heading">
            <div>
              <span className="step-label">01 / EXPLORADOR DE IMAGENS</span>
              <h2>Imagens e máscaras</h2>
            </div>
            <div className="button-row">
              <a
                className="icon-button"
                href={analysis.assets[view]}
                download
                title={`Baixar imagem: ${activeView.label.toLowerCase()}`}
                aria-label={`Baixar imagem: ${activeView.label.toLowerCase()}`}
              >
                <Icon name="down" size={18} />
              </a>
              <button
                className="icon-button"
                onClick={() => setExpanded(true)}
                aria-label="Ampliar imagem"
              >
                <Icon name="expand" size={18} />
              </button>
            </div>
          </div>
          <div
            className="viewer-tabs"
            role="tablist"
            aria-label="Visualização da imagem"
          >
            {views.map((item) => (
              <button
                role="tab"
                aria-selected={view === item.key}
                aria-controls="image-view"
                id={`tab-${item.key}`}
                key={item.key}
                onClick={() => setView(item.key)}
                className={view === item.key ? "active" : ""}
              >
                {item.label}
                {item.key === "detection" && (
                  <span>{analysis.deadend_count}</span>
                )}
              </button>
            ))}
          </div>
          <div
            className="image-stage"
            id="image-view"
            role="tabpanel"
            aria-labelledby={`tab-${view}`}
          >
            <img
              src={analysis.assets[view]}
              alt={`${activeView.label} de ${analysis.filename}`}
            />
            <span className="image-caption">
              {activeView.label.toUpperCase()}
              <span>
                {view === "original"
                  ? analysis.image_size_wh.join(" × ")
                  : analysis.analysis_size_wh.join(" × ")}{" "}
                PX
              </span>
            </span>
          </div>
          <div className="viewer-legend">
            <span>
              <i className="dot wall" />
              Parede
            </span>
            <span>
              <i className="dot water" />
              Água
            </span>
            <span>
              <i className="dot oil" />
              Óleo
            </span>
            <span>
              <i className="dot gas" />
              Gás
            </span>
            <span className="legend-note">
              {view === "detection"
                ? "Caixas verdes · confiança ≥ 70%"
                : "Segmentação em quatro classes"}
            </span>
          </div>
        </section>
        <CompositionChart composition={analysis.composition} />
      </div>
      <DeadendExplorer items={analysis.deadends} />
      <p className="analysis-method">
        <Icon name="info" size={15} />
        As frações dos fluidos excluem a parede e somam 1. A área das caixas
        considera a união dos retângulos, contando sobreposições uma única vez.
      </p>
      {expanded && (
        <Modal
          title={`${activeView.label} · ${analysis.filename}`}
          onClose={() => setExpanded(false)}
          wide
        >
          <img
            className="expanded-image"
            src={analysis.assets[view]}
            alt={activeView.label}
          />
          <div className="modal-footer">
            <span>
              {analysis.analysis_size_wh.join(" × ")} · grade de análise
            </span>
            <a
              className="secondary-button"
              href={analysis.assets[view]}
              download
            >
              <Icon name="down" size={16} />
              Baixar imagem
            </a>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Donut({ fractions, label }) {
  const oil = fractions.Oil || 0,
    water = fractions.Water || 0;
  const empty = Object.values(fractions).every((value) => value == null);
  return (
    <div className="donut-group">
      <div
        className={`donut ${empty ? "donut-empty" : ""}`}
        role="img"
        aria-label={`${label}: ${FLUIDS.map((fluid) => `${fluid.label} ${percent(fractions[fluid.key])}`).join(", ")}`}
        style={{
          "--donut": `conic-gradient(${FLUIDS[0].color} 0% ${oil * 100}%, ${FLUIDS[1].color} ${oil * 100}% ${(oil + water) * 100}%, ${FLUIDS[2].color} ${(oil + water) * 100}% 100%)`,
        }}
      >
        <div>
          <strong>{empty ? "—" : `${decimal(oil * 100, 1)}%`}</strong>
          <span>ÓLEO</span>
        </div>
      </div>
      <h3>{label}</h3>
    </div>
  );
}

function CompositionChart({ composition }) {
  return (
    <section className="panel composition-panel">
      <div className="panel-heading">
        <div>
          <span className="step-label">02 / DISTRIBUIÇÃO DAS FASES</span>
          <h2>Composição dos fluidos</h2>
        </div>
        <span className="fluid-only">APENAS FLUIDOS</span>
      </div>
      <div className="donuts">
        <Donut
          fractions={composition.full_image.class_fractions}
          label="Imagem completa"
        />
        <Donut
          fractions={composition.deadends.class_fractions}
          label="Nos Dead ends"
        />
      </div>
      <div className="comparison-labels">
        <span>Composição dos fluidos</span>
        <span>
          <i />
          Imagem <i />
          Dead ends
        </span>
      </div>
      <div className="fluid-comparison">
        {FLUIDS.map((fluid) => (
          <div className="fluid-row" key={fluid.key}>
            <div className="fluid-row-label">
              <span>
                <i style={{ background: fluid.color }} />
                {fluid.label}
              </span>
              <span>
                {percent(composition.full_image.class_fractions[fluid.key])}
                <b>/</b>
                <strong>
                  {percent(composition.deadends.class_fractions[fluid.key])}
                </strong>
              </span>
            </div>
            <div className="comparison-bars">
              <span
                style={{
                  width: `${(composition.full_image.class_fractions[fluid.key] || 0) * 100}%`,
                  background: fluid.color,
                  opacity: 0.3,
                }}
              />
              <span
                style={{
                  width: `${(composition.deadends.class_fractions[fluid.key] || 0) * 100}%`,
                  background: fluid.color,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="composition-note">
        <Icon name="info" size={14} />
        Parede excluída. Cada distribuição soma 100%.
      </div>
    </section>
  );
}

function FluidBar({ fractions }) {
  const empty = Object.values(fractions).every((value) => value == null);
  return (
    <div
      className="fluid-bar"
      role="img"
      aria-label={
        empty
          ? "Sem pixels de fluido"
          : FLUIDS.map(
              (fluid) => `${fluid.label} ${percent(fractions[fluid.key])}`,
            ).join(", ")
      }
    >
      {FLUIDS.map((fluid) => (
        <span
          key={fluid.key}
          style={{
            width: `${(fractions[fluid.key] || 0) * 100}%`,
            backgroundColor: fluid.color,
          }}
        />
      ))}
    </div>
  );
}

function DeadendExplorer({ items }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [mode, setMode] = useState("table");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState("id");
  const [selected, setSelected] = useState(null);
  const pageSize = mode === "grid" ? 8 : 6;
  const filtered = items
    .filter(
      (item) =>
        `${item.id} ${item.detection_id} DE-${String(item.detection_id).padStart(3, "0")}`
          .toLowerCase()
          .includes(query.trim().toLowerCase()) &&
        (filter === "all" || item.dominant_class === filter),
    )
    .sort((a, b) =>
      sort === "oil"
        ? (b.class_fractions.Oil ?? -1) - (a.class_fractions.Oil ?? -1)
        : sort === "confidence"
          ? b.confidence - a.confidence
          : a.detection_id - b.detection_id,
    );
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const visible = filtered.slice(
    currentPage * pageSize,
    (currentPage + 1) * pageSize,
  );
  const selectedIndex = filtered.findIndex((item) => item.id === selected?.id);
  function change(callback) {
    callback();
    setPage(0);
  }
  return (
    <section className="panel deadends-panel">
      <div className="deadends-heading">
        <div>
          <span className="step-label">03 / EXPLORADOR DE REGIÕES</span>
          <h2>
            Análise por região
            <span className="count-badge">{items.length} Dead ends</span>
          </h2>
          <p>Frações de água, óleo e gás por região detectada.</p>
        </div>
        <div className="view-toggle" aria-label="Visualização das regiões">
          <button
            className={mode === "table" ? "active" : ""}
            aria-label="Visualizar tabela"
            aria-pressed={mode === "table"}
            onClick={() => change(() => setMode("table"))}
          >
            <Icon name="table" size={17} />
          </button>
          <button
            className={mode === "grid" ? "active" : ""}
            aria-label="Visualizar grade"
            aria-pressed={mode === "grid"}
            onClick={() => change(() => setMode("grid"))}
          >
            <Icon name="grid" size={17} />
          </button>
        </div>
      </div>
      <div className="table-tools">
        <label className="search-field">
          <Icon name="search" size={17} />
          <input
            value={query}
            onChange={(event) => change(() => setQuery(event.target.value))}
            placeholder="Buscar Dead ends…"
            aria-label="Buscar Dead ends"
          />
          {query && (
            <button
              className="icon-button"
              onClick={() => change(() => setQuery(""))}
              aria-label="Limpar busca"
            >
              <Icon name="close" size={13} />
            </button>
          )}
        </label>
        <div className="table-filters">
          <label>
            <span className="visually-hidden">
              Filtrar por fluido predominante
            </span>
            <select
              value={filter}
              onChange={(event) => change(() => setFilter(event.target.value))}
            >
              <option value="all">Todas as composições</option>
              {FLUIDS.map((fluid) => (
                <option value={fluid.key} key={fluid.key}>
                  {fluid.label} predominante
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="visually-hidden">Ordenar regiões</span>
            <select
              value={sort}
              onChange={(event) => change(() => setSort(event.target.value))}
            >
              <option value="id">Ordenar: ID da região</option>
              <option value="oil">Ordenar: Fração de óleo</option>
              <option value="confidence">Ordenar: Confiança</option>
            </select>
          </label>
        </div>
      </div>
      {visible.length === 0 ? (
        <div className="no-regions">
          <Icon name="search" size={24} />
          <h3>Nenhuma região encontrada</h3>
          <p>Nenhuma região corresponde aos critérios de busca ou ao filtro de composição.</p>
        </div>
      ) : mode === "table" ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>REGIÃO</th>
                <th>DIMENSÕES</th>
                <th>CONFIANÇA</th>
                <th>COMPOSIÇÃO DOS FLUIDOS</th>
                <th>
                  <i className="dot oil" />
                  ÓLEO
                </th>
                <th>
                  <i className="dot water" />
                  ÁGUA
                </th>
                <th>
                  <i className="dot gas" />
                  GÁS
                </th>
                <th>
                  <span className="visually-hidden">Ver detalhes</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((item) => (
                <tr key={item.id}>
                  <td>
                    <button
                      className="region-link"
                      onClick={() => setSelected(item)}
                    >
                      <img src={item.assets.original} alt="" loading="lazy" />
                      <span>
                        DE-{String(item.detection_id).padStart(3, "0")}
                        <small>Região detectada</small>
                      </span>
                    </button>
                  </td>
                  <td className="size-cell">
                    {item.size_wh.join(" × ")}
                    <small>px</small>
                  </td>
                  <td>
                    <span className="confidence">
                      <span />
                      {decimal(item.confidence * 100, 1)}%
                    </span>
                  </td>
                  <td>
                    <FluidBar fractions={item.class_fractions} />
                  </td>
                  {FLUIDS.map((fluid) => (
                    <td
                      className={`fraction-cell ${fluid.key === "Oil" ? "oil-value" : ""}`}
                      key={fluid.key}
                    >
                      {percent(item.class_fractions[fluid.key])}
                    </td>
                  ))}
                  <td>
                    <button
                      className="icon-button"
                      onClick={() => setSelected(item)}
                      aria-label={`Ver região ${item.detection_id} de Dead ends`}
                    >
                      <Icon name="arrow" size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="deadend-grid">
          {visible.map((item) => (
            <button
              key={item.id}
              className="deadend-card"
              onClick={() => setSelected(item)}
            >
              <div className="crop-pair">
                <img
                  src={item.assets.original}
                  alt={`Imagem original da região ${item.detection_id} de Dead ends`}
                  loading="lazy"
                />
                <img
                  className="pixelated"
                  src={item.assets.segmentation}
                  alt="Segmentação"
                  loading="lazy"
                />
              </div>
              <div className="deadend-card-title">
                <strong>DE-{String(item.detection_id).padStart(3, "0")}</strong>
                <span>{decimal(item.confidence * 100, 1)}% de confiança</span>
              </div>
              <FluidBar fractions={item.class_fractions} />
              <div className="deadend-card-meta">
                <span>{percent(item.class_fractions.Oil)} de óleo</span>
                <Icon name="arrow" size={16} />
              </div>
            </button>
          ))}
        </div>
      )}
      <div className="pagination">
        <span>
          {filtered.length
            ? `${currentPage * pageSize + 1}–${Math.min((currentPage + 1) * pageSize, filtered.length)}`
            : "0"}{" "}
          de {filtered.length} regiões
        </span>
        <div>
          <button
            className="icon-button"
            disabled={currentPage === 0}
            onClick={() => setPage(currentPage - 1)}
            aria-label="Página anterior"
          >
            <Icon name="back" size={15} />
          </button>
          <span>
            Página {currentPage + 1} de {totalPages}
          </span>
          <button
            className="icon-button"
            disabled={currentPage >= totalPages - 1}
            onClick={() => setPage(currentPage + 1)}
            aria-label="Próxima página"
          >
            <Icon name="chevron" size={15} />
          </button>
        </div>
      </div>
      {selected && (
        <DeadendModal
          item={selected}
          onClose={() => setSelected(null)}
          onPrevious={
            selectedIndex > 0
              ? () => setSelected(filtered[selectedIndex - 1])
              : null
          }
          onNext={
            selectedIndex >= 0 && selectedIndex < filtered.length - 1
              ? () => setSelected(filtered[selectedIndex + 1])
              : null
          }
        />
      )}
    </section>
  );
}

function Modal({ title, onClose, children, wide }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => {
      dialog.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "wide-modal" : ""}`}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal-header">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Fechar detalhes"
        >
          <Icon name="close" />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function DeadendModal({ item, onClose, onPrevious, onNext }) {
  const [overlay, setOverlay] = useState(false);
  return (
    <Modal
      title={`Dead ends · DE-${String(item.detection_id).padStart(3, "0")}`}
      onClose={onClose}
      wide
    >
      <div className="detail-meta">
        <span className="confidence">
          <span />
          {decimal(item.confidence * 100, 1)}% de confiança
        </span>
        <span>{item.size_wh.join(" × ")} pixels</span>
        <label className="overlay-switch">
          <input
            type="checkbox"
            checked={overlay}
            onChange={(event) => setOverlay(event.target.checked)}
          />
          Mostrar sobreposição
        </label>
      </div>
      <div className="detail-images">
        <figure>
          <img
            className="pixelated"
            src={item.assets.original}
            alt="Recorte original da região de Dead ends"
          />
          <figcaption>
            Região original
            <a
              href={item.assets.original}
              download
              aria-label="Baixar recorte original"
            >
              <Icon name="down" size={16} />
            </a>
          </figcaption>
        </figure>
        <figure>
          <img
            className="pixelated"
            src={overlay ? item.assets.overlay : item.assets.segmentation}
            alt={
              overlay ? "Sobreposição da segmentação" : "Máscara de segmentação"
            }
          />
          <figcaption>
            {overlay ? "Sobreposição da segmentação" : "Máscara de segmentação"}
            <a
              href={overlay ? item.assets.overlay : item.assets.segmentation}
              download
              aria-label="Baixar segmentação"
            >
              <Icon name="down" size={16} />
            </a>
          </figcaption>
        </figure>
      </div>
      <div className="detail-composition">
        <div>
          <span className="step-label">COMPOSIÇÃO DOS FLUIDOS</span>
          <p>Parede excluída · as frações somam 1</p>
        </div>
        <div className="detail-fluids">
          {FLUIDS.map((fluid) => (
            <div key={fluid.key}>
              <span>
                <i style={{ background: fluid.color }} />
                {fluid.label}
              </span>
              <strong>{percent(item.class_fractions[fluid.key])}</strong>
            </div>
          ))}
        </div>
        <FluidBar fractions={item.class_fractions} />
      </div>
      <div className="detail-coordinates">
        <span>
          Coordenadas da caixa <code>{item.pixel_bounds_xyxy.join(", ")}</code>
        </span>
        <span>
          {number(item.fluid_area_px)} pixels de fluido <span>·</span>{" "}
          {number(item.excluded_wall_px)} pixels de parede excluídos
        </span>
      </div>
      <div className="modal-footer">
        <div className="button-row">
          <button
            className="icon-button"
            disabled={!onPrevious}
            onClick={onPrevious}
            aria-label="Região anterior de Dead ends"
          >
            <Icon name="back" size={17} />
          </button>
          <button
            className="icon-button"
            disabled={!onNext}
            onClick={onNext}
            aria-label="Próxima região de Dead ends"
          >
            <Icon name="chevron" size={17} />
          </button>
          <span>Navegação entre regiões</span>
        </div>
        <a className="primary-button" href={item.assets.class_ids} download>
          <Icon name="down" size={16} />
          Exportar máscara de classes
        </a>
      </div>
    </Modal>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}
