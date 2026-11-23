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
import ResidualOilSection, { ResidualOilMetrics } from "./ResidualOil.jsx";
import Icon from "./Icon.jsx";
import { getExperiment, request } from "./api/client.js";
import ExperimentsPage, {
  ExperimentInfo,
  EntryOptions,
  NumericalResults,
} from "./Experiments.jsx";

const FLUIDS = [
  { key: "Oil", label: "Óleo", color: "#e3676d" },
  { key: "Water", label: "Água", color: "#749de8" },
  { key: "Gas", label: "Gás", color: "#77c6a3" },
];

function Shell() {
  const [online, setOnline] = useState(null);
  const [connected, setConnected] = useState(null);
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname]);
  useEffect(() => {
    let mounted = true;
    const check = () =>
      request("/api/health")
        .then((data) => {
          if (mounted) {
            setOnline(data.models_available);
            setConnected(true);
          }
        })
        .catch(() => {
          if (mounted) {
            setOnline(false);
            setConnected(false);
          }
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
          <NavLink to="/experiments">
            <Icon name="database" />
            <span>Experimentos salvos</span>
            <span className="nav-shortcut">02</span>
          </NavLink>
          <NavLink to="/analysis/sample">
            <Icon name="chart" />
            <span>Análise de exemplo</span>
            <span className="nav-shortcut">03</span>
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
            <br />e detecção de regiões.
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
              className={`status-dot ${connected === false ? "offline" : ""}`}
            />
            {connected === null
              ? "Conectando…"
              : connected
                ? online
                  ? "Servidor de análise disponível"
                  : "Servidor disponível · modelos indisponíveis"
                : "Servidor de análise desconectado"}
            <span className="local-pill">LOCAL</span>
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<UploadPage online={online} />} />
            <Route path="/analysis/:id" element={<AnalysisPage />} />
            <Route path="/experiments" element={<ExperimentsPage />} />
            <Route path="/experiments/:id" element={<SavedExperimentPage />} />
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
      setError(
        "Formato não suportado. Formatos aceitos: PNG, JPG, TIFF e WebP.",
      );
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
            <br className="desktop-break" /> e quantificação da composição dos
            fluidos.
          </p>
        </div>
        <div className="intro-coordinate">
          <span>LABMEMS / UFRJ</span>
          <div className="coordinate-cross">+</div>
          <span>MICROFLUÍDICA</span>
        </div>
      </section>
      <EntryOptions />
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
                <span className="change-image">Substituir imagem</span>
              </>
            ) : (
              <>
                <span className="upload-icon">
                  <Icon name="upload" size={30} />
                </span>
                <h3>Imagem do micromodelo</h3>
                <p>
                  <span className="browse-text">Selecionar arquivo</span> ou
                  arrastar a imagem para esta área.
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
              Entrada: imagem original do micromodelo, sem anotações ou
              sobreposições.
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
              Servidor Python indisponível. Instruções de inicialização no
              README do projeto.
            </p>
          )}
        </section>
        <aside className="pipeline-panel">
          <span className="step-label">ETAPAS DO PROCESSAMENTO</span>
          <h2>Fluxo de análise</h2>
          <p className="pipeline-description">
            Segmentação semântica, detecção de regiões e análise da composição
            dos fluidos.
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
              {
                n: "04",
                icon: "drop",
                title: "Óleo residual em Dead ends",
                desc: "Estimativa do óleo residual e removido pela água.",
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
            Resultados de segmentação, detecção de Dead ends e composição dos
            fluidos.
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
          Processamento local com armazenamento dos arquivos no diretório do
          projeto.
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

function SavedExperimentPage() {
  const { id } = useParams();
  return <AnalysisLoader key={`experiment-${id}`} id={id} saved />;
}

function AnalysisLoader({ id, saved = false }) {
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true,
      timer;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const options = { signal: controller.signal };
        const data = saved
          ? await getExperiment(id, options)
          : await request(`/api/analyses/${encodeURIComponent(id)}`, options);
        if (saved && !data.exports)
          throw new Error(
            "Reiniciar o servidor Python para carregar a consulta de experimentos e as novas rotas de exportação.",
          );
        if (!active) return;
        setAnalysis(
          saved
            ? {
                ...data,
                status: "completed",
                assets: {
                  ...data.assets,
                  csv: data.exports.csv,
                  residual_report: data.exports.residual_json,
                  residual_csv: data.exports.residual_csv,
                },
              }
            : data,
        );
        setError("");
        if (!saved && ["queued", "processing"].includes(data.status))
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
  }, [id, attempt, saved]);
  if (error || analysis?.status === "failed")
    return (
      <div className="page">
        <div className="empty-state">
          <span className="upload-icon">
            <Icon name="info" size={28} />
          </span>
          <h1>{saved ? "Experimento indisponível" : "Falha na análise"}</h1>
          <p role="alert">{error || localizeApiMessage(analysis.error)}</p>
          <div className="button-row">
            {saved && (
              <Link className="secondary-button" to="/experiments">
                Voltar ao histórico
              </Link>
            )}
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
  if (saved && !analysis)
    return (
      <div className="page">
        <div className="history-empty panel" role="status">
          <span className="spinner" />
          <h1>Carregando experimento</h1>
          <p>Consulta aos resultados armazenados no banco.</p>
        </div>
      </div>
    );
  if (!analysis || analysis.status !== "completed")
    return <Processing analysis={analysis} />;
  return <Results analysis={analysis} fromDatabase={saved} />;
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
          Processamento local. O tempo de execução depende das dimensões da
          imagem e dos recursos computacionais.
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

function Results({ analysis, fromDatabase = false }) {
  const location = useLocation();
  const historyPath = `/experiments${location.state?.historySearch ? `?${location.state.historySearch}` : ""}`;
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
        {fromDatabase && (
          <>
            <Link to={historyPath}>Experimentos salvos</Link>
            <Icon name="chevron" size={13} />
          </>
        )}
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
          <h1>{fromDatabase ? analysis.name : "Resultados da análise"}</h1>
          <div className="file-meta">
            <Icon name="image" size={15} />
            <span>{analysis.filename}</span>
            <i />
            {analysis.image_size_wh.join(" × ")} px
            <i />
            <span className="complete-label">
              <Icon name="check" size={13} />
              {fromDatabase ? "Experimento salvo" : "Análise concluída"}
            </span>
            {analysis.is_sample && <span className="sample-tag">EXEMPLO</span>}
          </div>
        </div>
        <div className="button-row">
          {fromDatabase && (
            <Link to={historyPath} className="secondary-button">
              <Icon name="back" size={17} />
              Histórico
            </Link>
          )}
          <Link to="/" className="secondary-button">
            <Icon name="plus" size={17} />
            Nova análise
          </Link>
          {fromDatabase && (
            <a
              href={analysis.exports.json}
              download
              className="secondary-button"
            >
              <Icon name="down" size={17} />
              Exportar JSON
            </a>
          )}
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
          note={
            fromDatabase
              ? "Regiões registradas no experimento"
              : "Confiança ≥ 70%"
          }
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
      {fromDatabase && <ExperimentInfo experiment={analysis} />}
      <NumericalResults composition={analysis.composition} />
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
            <AnalysisImage
              key={analysis.assets[view]}
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
      <ResidualOilSection
        composition={analysis.composition}
        assets={analysis.assets}
      />
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
          <AnalysisImage
            key={analysis.assets[view]}
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

function AnalysisImage({ src, alt, compact = false, ...props }) {
  const [failed, setFailed] = useState(!src);
  return failed ? (
    <span
      className={`missing-image ${compact ? "compact" : ""}`}
      role="img"
      aria-label={alt || "Imagem indisponível"}
    >
      <Icon name="image" size={compact ? 18 : 28} />
      {!compact && (
        <>
          <strong>Arquivo de imagem indisponível</strong>
          <small>Os resultados numéricos permanecem disponíveis.</small>
        </>
      )}
    </span>
  ) : (
    <img src={src} alt={alt} {...props} onError={() => setFailed(true)} />
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
          <span className="step-label">04 / EXPLORADOR DE REGIÕES</span>
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
          <p>
            Nenhuma região corresponde aos critérios de busca ou ao filtro de
            composição.
          </p>
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
                      <AnalysisImage
                        key={item.assets.original}
                        src={item.assets.original}
                        alt=""
                        loading="lazy"
                        compact
                      />
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
                <AnalysisImage
                  key={item.assets.original}
                  src={item.assets.original}
                  alt={`Imagem original da região ${item.detection_id} de Dead ends`}
                  loading="lazy"
                />
                <AnalysisImage
                  key={item.assets.segmentation}
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
          <AnalysisImage
            key={item.assets.original}
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
          <AnalysisImage
            key={overlay ? item.assets.overlay : item.assets.segmentation}
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
      <ResidualOilMetrics data={item.residual_oil} compact />
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
