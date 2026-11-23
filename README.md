# MicroFlow · LabMEMS / UFRJ

A local workspace for micromodel segmentation, dead-end detection and fluid
composition analysis. The React interface uses the LabMEMS and UFRJ logos,
background `#1c1530`, and accent `#bd3e42`.

## Agradecimentos

Agradecimentos à Shell. A interface exibe essa homenagem
de forma discreta no rodapé, com a logo fornecida sem fundo.

## Start the app

From `C:\labmems\wag-app`, open two PowerShell terminals.

Backend:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON_INSTALL_DIR = "$PWD\.uv-python"
uv sync
uv run uvicorn API.FASTAPI.app.main:app --host 127.0.0.1 --port 8000
```

Frontend, in a second terminal:

```powershell
cd C:\labmems\wag-app\FRONTEND
npm install
npm run dev
```

Open the local URL printed by Vite (normally http://127.0.0.1:5173).
The frontend proxies `/api` to port 8000. Both servers must be running.
Use one backend worker: inference jobs run serially to limit memory use.

## Workflow

1. Drop or browse for a PNG, JPG, TIFF or WebP image, up to 25 MB / 40 MP.
2. Select **Analyze image**. The progress screen tracks real processing stages.
3. Switch between original, segmentation, detection and overlay images.
4. Compare full-image fluid composition with the union of detected boxes.
5. Search, filter and sort individual dead ends in a table or image grid.
6. Open a region for enlarged original/mask images and download its class-ID mask.
7. Export composition measurements as CSV, or download the current viewer image.

The **Explore sample** button opens the existing `train.png` results, when the
inference/analysis output files are present. These are real saved results.
New uploads always run both models. A browser refresh preserves an analysis via
its URL; a backend restart interrupts running jobs and the UI asks for reupload.

## Models and outputs

- `MODELS/unet/dcaunet_ema_combined_loss_weighted.pt`
- `MODELS/yolo/best.pt`
- New analyses: `ALGORITHMS/data/results/web/<job-id>/analysis/`
- Each run has independent outputs, a composition JSON/CSV and per-region crops.
- U-Net input is RGB, CHW `3 × 768 × 576`, float32 scaled by 255.
  This normalization remains an assumption to confirm against training.
- YOLOv5 v7.0 runs on a `1792 × 1344` image using `224 × 224` tiles and
  25% overlap. Global class-aware NMS uses IoU 0.45; displayed confidence ≥ 0.70.
  The first detector load downloads the pinned YOLOv5 source if absent.
- Segmentation aligns to the YOLO grid using nearest-neighbor interpolation.
- Fluid composition excludes wall pixels; oil + water + gas fractions sum to 1.
  Regions containing no fluid pixels report unavailable fractions.
- Box coverage measures rectangles, including their wall pixels, and counts
  overlapping pixels once. It is not exact anatomical dead-end area.

The UI adapts the logo backgrounds with CSS filters/blending. Uploaded image
processing stays local; optional web fonts are requested from Google Fonts,
with system-font fallbacks. This development server has no authentication;
keep it bound to loopback for the local research workflow.

## Óleo residual em Dead ends

A seção **Óleo residual em Dead ends** usa a hipótese de que toda a área
fluida estava inicialmente preenchida por óleo. A parede é excluída:

- Óleo inicial equivalente: `água + óleo + gás` (100% da referência).
- Residual: `(óleo + gás) / óleo inicial × 100`.
- Óleo removido equivalente: `água / óleo inicial × 100`.

As áreas são contagens de pixels, sem conversão para volume. Os percentuais
residual e removido somam 100% quando há pixels de fluido; com área fluida
zero, os percentuais são indefinidos. O gás é incluído na fração residual.
São estimativas por área de uma única imagem, sem comparação temporal.

O painel alterna entre imagem completa e união das caixas de Dead ends.
Pixels sobrepostos são contados uma única vez no agregado. Os detalhes de
cada região também exibem os indicadores. As análises salvas anteriormente
são calculadas a partir das contagens existentes, sem nova inferência.

Os botões da seção exportam CSV e JSON com a imagem completa, a união das caixas,
a região externa e todas as regiões individuais. A API disponibiliza
`/api/analyses/<id>/residual-oil?format=json` ou `format=csv` (incluindo `sample`).
Novos processamentos e o comando `python -m ALGORITHMS.analyze_deadends`
também gravam `residual_oil.json` e `residual_oil.csv` na pasta de resultados.

Após atualizar o código, reiniciar o servidor Python e atualizar a página
para carregar os novos campos e a seção de análise.

## Banco relacional de experimentos

A FastAPI usa SQLAlchemy e SQLite em `DATABASE/database.db`. As tabelas são
criadas e atualizadas automaticamente pelo Alembic ao iniciar o backend.
O arquivo do banco é local e está no `.gitignore`. Não é necessário instalar
um servidor de banco separado. A organização de modelos, sessões e rotas segue
como referência [a API do projeto mdistrl4](https://github.com/smartsenseia/mdistrl4/tree/main/FASTAPI/app).

Cada nova análise concluída é salva automaticamente em uma transação, com:

- Nome original da imagem, identificação da análise, SHA-256 do upload, nome
  e observações do experimento, datas de criação, conclusão e salvamento em UTC.
- Resolução original, resolução final de comparação e resolução da máscara
  da UNet, tempo de inferência, dispositivo, parâmetros e informações dos modelos.
- Número de Dead ends e cobertura da união de suas caixas.
- Contagens de pixels e frações de água, óleo e gás na imagem completa,
  dentro da união das caixas e fora dela. As paredes são registradas separadamente
  e excluídas do denominador das frações.
- Óleo inicial equivalente, óleo + gás residual e óleo removido equivalente,
  em pixels e percentuais, nos três agregados e em cada Dead end.
- Coordenadas, confiança, composição e referências às imagens e máscaras
  exportadas de cada Dead end.

O percentual de óleo (`class_fractions.Oil × 100`) é separado do percentual
residual (`residual_oil.residual_percent`), que inclui óleo **e gás** conforme
a hipótese descrita na seção anterior. As frações são de 0 a 1 e os percentuais
de 0 a 100. Quando não há área fluida, as frações e percentuais são `null`.
A região externa é calculada subtraindo a **união** das caixas da imagem
completa; a soma das caixas individuais não é usada por causa das sobreposições.

As tabelas são `experiments` (metadados de uma imagem analisada) e
`region_results` (três agregados mais um registro por Dead end). As métricas
ficam em colunas SQL; parâmetros variáveis e referências a arquivos ficam em JSON.
Os arquivos de imagens e máscaras continuam nas pastas de resultados. Consultas
numéricas ao histórico independem desses arquivos; abrir ou baixar as imagens
exige que eles sejam preservados. Para backup completo, guardar o banco e
`ALGORITHMS/data/results/`, além dos uploads necessários.

### Rotas

| Método | Rota | Resultado |
| --- | --- | --- |
| POST | `/api/experiments` | Salva uma análise já concluída pelo `analysis_id` |
| GET | `/api/experiments` | Lista paginada com os indicadores dos três agregados |
| GET | `/api/experiments/{id}` | Dados completos, regiões individuais e arquivos |
| GET | `/api/experiments/{id}/export?format=json` | Exporta o registro completo diretamente do banco |
| GET | `/api/experiments/{id}/export?format=csv` | Exporta os três agregados e cada Dead end em linhas separadas |
| GET | `/api/experiments/{id}/residual-oil?format=json` | Exporta o balanço de óleo salvo; também aceita `format=csv` |
| DELETE | `/api/experiments/{id}` | Remove o experimento e seus registros relacionados |

`id` identifica o registro no banco e difere de `analysis_id`, que identifica
o processamento. O status de uma nova análise concluída inclui `experiment_id`
e `persistence_status: "saved"`. Se o banco falhar após a inferência, os arquivos
e o resultado permanecem disponíveis, com `persistence_status: "failed"` e
`persistence_error`. O POST permite repetir apenas o salvamento.

O POST aceita `analysis_id`, `name` e `notes`, sem aceitar métricas enviadas
pelo cliente. Retorna 201 no primeiro salvamento e 200 se a análise já estiver
registrada, preservando os dados existentes. Uma análise pendente retorna 409;
uma análise inexistente retorna 404. Análises antigas podem ser registradas pela
mesma rota, inclusive `sample`, sem executar os modelos novamente. Campos que
não existiam nos arquivos antigos, como SHA-256 e datas de execução, ficam `null`.

A listagem aceita `limit` (1 a 100, padrão 20), `offset`, `filename` (trecho
literal do nome), `analysis_id`, `saved_from` e `saved_until` (datas ISO 8601,
limites inclusivos). O filtro `q` busca por nome, arquivo, ID do experimento ou
ID da análise, tratando caracteres como `%` e `_` literalmente. A ordenação
aceita `sort_by=saved_at|created_at|name|deadend_count` e `order=asc|desc`;
o padrão é o salvamento mais recente primeiro. Retorna `{total, offset, limit, items}`.
A listagem inclui os três agregados; os recortes
individuais aparecem apenas no GET por ID.

O DELETE retorna 204 e remove os registros relacionados por chave estrangeira,
preservando os arquivos de inferência. O experimento excluído não é recriado ao
reiniciar o servidor; um novo POST explícito pode registrá-lo novamente.

Exemplos em PowerShell, com o backend em execução:

```powershell
$api = "http://127.0.0.1:8000/api/experiments"

# Registrar uma análise antiga; para um upload, substituir sample pelo ID da análise.
$body = @{ analysis_id = "sample"; name = "Ensaio de referência" } | ConvertTo-Json
$experimento = Invoke-RestMethod -Method Post -Uri $api -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))

# Listar o histórico e consultar um experimento completo.
Invoke-RestMethod -Uri "${api}?limit=20&offset=0"
Invoke-RestMethod -Uri "$api/$($experimento.id)"

# Exclusão de um registro, quando necessária:
# Invoke-RestMethod -Method Delete -Uri "$api/$($experimento.id)"
```

Os contratos e exemplos interativos estão em [Swagger UI](http://127.0.0.1:8000/docs).

### Consulta pela interface

Na página inicial, a opção **Consultar experimentos** é uma alternativa à
importação de imagem. O mesmo histórico fica disponível em **Experimentos salvos**
no menu lateral ou em `http://127.0.0.1:5173/experiments`.

O histórico permite buscar por nome, arquivo ou identificação, filtrar pelo
intervalo de salvamento, ordenar os registros e selecionar 10, 20 ou 50 resultados
por página. As datas dos filtros usam o fuso local do navegador e são enviadas
à API em UTC, incluindo o dia final inteiro. Os filtros ficam na URL e são
preservados ao voltar de um experimento para a listagem.

O botão **Abrir** acessa `/experiments/{id}` e consulta o banco diretamente,
sem executar a UNet ou o YOLO. A página mostra metadados, resoluções, datas,
identificadores, parâmetros de inferência, os três agregados numéricos,
composição e balanço de óleo, além da tabela/grade de Dead ends com detalhes
individuais. Campos ausentes em análises antigas aparecem como não registrados.
Uma imagem ausente é indicada na visualização; os resultados numéricos continuam
acessíveis. As exportações JSON/CSV dessa página e do painel de óleo residual
são geradas do banco e independem dos arquivos originais de relatórios.

Depois de atualizar o código, reiniciar o backend Python e atualizar o navegador
para disponibilizar as novas consultas e rotas de exportação. O frontend usa
a porta 8000 por padrão. Para um backend em outra porta durante desenvolvimento,
definir `MICROFLOW_API_TARGET` no terminal do Vite, por exemplo
`$env:MICROFLOW_API_TARGET = "http://127.0.0.1:8001"`, antes de `npm run dev`.

### Configuração e migrações

O caminho padrão do banco é absoluto e independe da pasta de onde o servidor
é iniciado. Para usar outro arquivo SQLite, definir `DATABASE_URL` no `.env`
da raiz (modelo em `.env.example`) ou no terminal antes de iniciar o servidor:

```powershell
$env:DATABASE_URL = "sqlite:///DATABASE/experimentos.db"
uv run uvicorn API.FASTAPI.app.main:app --host 127.0.0.1 --port 8000
```

Não copiar o `.env.example` se já houver um `.env` configurado. URLs de outros
bancos SQLAlchemy exigem o driver correspondente e validação nesse banco;
esta implementação foi testada com SQLite. O comando manual equivalente à
atualização automática é `uv run alembic upgrade head`. Para futuras alterações
nas tabelas, gerar e revisar uma migração com
`uv run alembic revision --autogenerate -m "Descricao da alteracao"`.

## Verify

```powershell
uv run pytest ALGORITHMS/tests API/FASTAPI/tests -q
cd FRONTEND
npm run build
```
