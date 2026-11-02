# Especificações de software para segmentação semântica e detecção de dead-ends em micro-modelos artificais.


# Espeficiações de entrada do programa:

- Entrada: imagem de micro modelo
- saída: segmentação semântica e detecção de deadends

## Segmentação semântica:
- É uma segmentação de 4 classes:
0: parade do micro modelo
1: Água
2: Óleo
3: Gás

favor pintar cada uma das classes da cor familiarizada:

gás: verde
Água: azul
Óleo: vermelho
Parede do mimo: amarelo

ASSUMA que temos um modelo já treinado para tal e sua arquitetura é a DCA UNet abaixo:

class RoPE(nn.Module):
    def __init__(self, sequence_len, embedding_dim):
        super(RoPE, self).__init__()

        self.sequence_len = sequence_len
        self.embedding_dim = embedding_dim

        pos_vec = torch.arange(0, sequence_len, 1, dtype=torch.float32)
        dims_vec = torch.arange(0, embedding_dim//2, 1, dtype=torch.float32)

        unity = torch.ones([sequence_len, embedding_dim//2])
        pos = pos_vec.reshape(sequence_len, 1) * unity
        dims = dims_vec.reshape(1, embedding_dim//2) * unity

        theta = pos / 10000**(2 * dims / embedding_dim)
        self.register_buffer("sin", torch.sin(theta))
        self.register_buffer("cos", torch.cos(theta))

    def forward(self, x):
        batch_size= x.size()[0]
        pairs = x.reshape(batch_size, self.sequence_len, self.embedding_dim//2, 2)
        out1 = self.cos * pairs[:, :, :, 0] - self.sin * pairs[:, :, :, 1]
        out2 = self.sin * pairs[:, :, :, 0] + self.cos * pairs[:, :, :, 1]
        out = torch.stack((out1, out2), dim=-1)
        return out.reshape(batch_size, self.sequence_len, self.embedding_dim)


class DoubleConv(nn.Module):
    def __init__(self, in_channels, out_channels, dropout_prob=0.20):
        super(DoubleConv, self).__init__()

        # define double convolution operation with dropout
        self.operation = nn.Sequential(
            nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(num_features=out_channels),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout_prob),
            nn.Conv2d(in_channels=out_channels, out_channels=out_channels, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout_prob)
        )

    def forward(self, x):
        return self.operation(x)


class SelfAttention(nn.Module):
    """
    Efficient spatial self-attention for CNN feature maps.

    Input:  [B, C, H, W]
    Output: [B, C, H, W]

    Features:
      - Multi-head scaled dot-product attention
      - 2D Rotary Positional Embeddings
      - Spatial token reduction
      - Learnable residual scaling
    """

    def __init__(
        self,
        semantic: int,
        compressed: int = 1,
        num_heads: int = 4,
        max_tokens: int = 576,
        dropout: float = 0.0,
    ):
        super().__init__()

        if semantic % num_heads != 0:
            raise ValueError(
                "semantic must be divisible by num_heads"
            )

        self.head_dim = semantic // num_heads

        if self.head_dim % 4 != 0:
            raise ValueError(
                "head_dim must be divisible by 4 for 2D RoPE"
            )

        if compressed < 1 or max_tokens < 1:
            raise ValueError(
                "compressed and max_tokens must be positive"
            )

        self.compressed = compressed
        self.max_tokens = max_tokens
        self.num_heads = num_heads
        self.channels = semantic
        self.dropout = dropout

        # Pre-attention normalization
        self.norm = nn.LayerNorm(semantic)

        # Joint QKV projection
        self.qkv = nn.Linear(semantic, 3 * semantic)

        # Output projection
        self.proj = nn.Linear(semantic, semantic)
        self.out_dropout = nn.Dropout(dropout)

        # Small initial residual contribution
        self.gamma = nn.Parameter(torch.tensor(1e-2))

        # RoPE frequencies for each spatial axis
        axis_dim = self.head_dim // 2

        inv_freq = 1.0 / (
            10000 ** (
                torch.arange(
                    0, axis_dim, 2, dtype=torch.float32
                ) / axis_dim
            )
        )

        self.register_buffer(
            "inv_freq", inv_freq, persistent=False
        )

    @staticmethod
    def _rotate(t, cos, sin):
        even = t[..., 0::2]
        odd = t[..., 1::2]

        return torch.stack(
            (
                even * cos - odd * sin,
                even * sin + odd * cos,
            ),
            dim=-1,
        ).flatten(-2)

    def _rope2d(self, t, h, w):
        """
        t: [B, heads, H*W, head_dim]
        """
        b, heads, n, d = t.shape

        t = t.reshape(b, heads, h, w, d)
        half = d // 2

        yy = torch.arange(
            h, device=t.device, dtype=self.inv_freq.dtype
        )
        xx = torch.arange(
            w, device=t.device, dtype=self.inv_freq.dtype
        )

        angle_y = torch.outer(yy, self.inv_freq)
        angle_x = torch.outer(xx, self.inv_freq)

        cos_y = angle_y.cos().to(t.dtype)[
            None, None, :, None, :
        ]
        sin_y = angle_y.sin().to(t.dtype)[
            None, None, :, None, :
        ]

        cos_x = angle_x.cos().to(t.dtype)[
            None, None, None, :, :
        ]
        sin_x = angle_x.sin().to(t.dtype)[
            None, None, None, :, :
        ]

        # Rotate height and width channel groups separately
        y = self._rotate(
            t[..., :half], cos_y, sin_y
        )
        x = self._rotate(
            t[..., half:], cos_x, sin_x
        )

        return torch.cat(
            (y, x), dim=-1
        ).reshape(b, heads, n, d)

    def forward(self, x):
        b, c, h, w = x.shape

        # ----------------------------------------
        # 1. Spatial token reduction
        # ----------------------------------------
        ph = max(1, h // self.compressed)
        pw = max(1, w // self.compressed)

        # Enforce maximum attention token budget
        if ph * pw > self.max_tokens:
            ratio = math.sqrt(
                self.max_tokens / (ph * pw)
            )

            ph = max(1, int(ph * ratio))
            pw = max(1, int(pw * ratio))

        z = F.adaptive_avg_pool2d(x, (ph, pw))

        # [B, C, ph, pw] -> [B, N, C]
        z = z.flatten(2).transpose(1, 2)
        z = self.norm(z)

        # ----------------------------------------
        # 2. Multi-head QKV projection
        # ----------------------------------------
        qkv = self.qkv(z).reshape(
            b,
            ph * pw,
            3,
            self.num_heads,
            self.head_dim,
        )

        # [3, B, heads, N, head_dim]
        q, k, v = qkv.permute(
            2, 0, 3, 1, 4
        ).unbind(0)

        # ----------------------------------------
        # 3. 2D RoPE applied to Q and K
        # ----------------------------------------
        q = self._rope2d(q, ph, pw)
        k = self._rope2d(k, ph, pw)

        # ----------------------------------------
        # 4. Optimized PyTorch attention
        # ----------------------------------------
        z = F.scaled_dot_product_attention(
            q,
            k,
            v,
            dropout_p=(
                self.dropout if self.training else 0.0
            ),
            is_causal=False,
        )

        # ----------------------------------------
        # 5. Restore spatial layout
        # ----------------------------------------
        z = z.transpose(1, 2).contiguous()
        z = z.reshape(b, ph * pw, c)

        z = self.out_dropout(self.proj(z))

        z = z.transpose(1, 2).reshape(
            b, c, ph, pw
        )

        # Recover original feature-map resolution
        z = F.interpolate(
            z,
            size=(h, w),
            mode="bilinear",
            align_corners=False,
        )

        # ----------------------------------------
        # 6. Residual connection
        # ----------------------------------------
        return x + self.gamma * z



class DCAUNet(nn.Module):
    def __init__(self):
        super(DCAUNet, self).__init__()

        # input [3, 768, 576]

        # encoder: [64, 256, 384, 384]
        self.encoder1 = DoubleConv(in_channels=3, out_channels=64)
        self.encoder2 = DoubleConv(in_channels=64, out_channels=256)
        self.encoder3 = DoubleConv(in_channels=256, out_channels=384)
        self.encoder4 = DoubleConv(in_channels=384, out_channels=384)

        self.selfatt1 = SelfAttention(
            semantic=64,
            compressed=8,
            num_heads=4,
            max_tokens=576
        )

        self.selfatt2 = SelfAttention(
            semantic=256,
            compressed=4,
            num_heads=4,
            max_tokens=576
        )

        self.selfatt3 = SelfAttention(
            semantic=384,
            compressed=2,
            num_heads=8,
            max_tokens=576
        )

        self.selfatt4 = SelfAttention(
            semantic=384,
            compressed=1,
            num_heads=8,
            max_tokens=576
        )

        # bottleneck
        self.bottom_conv = nn.Conv2d(
            384, 384, kernel_size=3, stride=1, padding=1
        )
        self.bottom_normalizer = nn.BatchNorm2d(384)

        self.unity_conv = nn.Conv2d(
            384, 384, kernel_size=1, stride=1, padding=0
        )
        self.bottom_drop = nn.Dropout(p=0.20)

        # decoder
        self.transpose3 = nn.ConvTranspose2d(
            384, 384, kernel_size=2, stride=2
        )
        self.decoder3 = DoubleConv(
            in_channels=768, out_channels=384
        )

        self.transpose2 = nn.ConvTranspose2d(
            384, 256, kernel_size=2, stride=2
        )
        self.decoder2 = DoubleConv(
            in_channels=512, out_channels=256
        )

        self.transpose1 = nn.ConvTranspose2d(
            256, 64, kernel_size=2, stride=2
        )
        self.decoder1 = DoubleConv(
            in_channels=128, out_channels=64
        )

        self.final_conv = nn.Conv2d(
            64, 4, kernel_size=3, stride=1, padding=1
        )

        self.pool = nn.MaxPool2d(2, 2)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):

        # encoder
        enc1 = self.selfatt1(self.encoder1(x))
        enc2 = self.selfatt2(self.encoder2(self.pool(enc1)))
        enc3 = self.selfatt3(self.encoder3(self.pool(enc2)))
        enc4 = self.selfatt4(self.encoder4(self.pool(enc3)))

        # bottleneck
        bottom1 = self.bottom_drop(
            self.relu(
                self.bottom_normalizer(self.bottom_conv(enc4))
            )
        )
        bottom2 = self.bottom_drop(
            self.relu(
                self.bottom_normalizer(self.unity_conv(bottom1))
            )
        )

        # decoder
        dec3 = self.decoder3(
            torch.cat([self.transpose3(bottom2), enc3], dim=1)
        )
        dec2 = self.decoder2(
            torch.cat([self.transpose2(dec3), enc2], dim=1)
        )
        dec1 = self.decoder1(
            torch.cat([self.transpose1(dec2), enc1], dim=1)
        )

        return self.final_conv(dec1)

e seus pesos estão armazenados em um arquivo .pt na pasta de modelos que será descrita no formato do projeto.

exemplo de código de inferência pode ser encontrado abaixo, adapte de acordo com a usabilidade e contexto:

def load_model(model: torch.nn.Module, path: str) -> torch.nn.Module:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Model weights not found: {path}")

    state_dict = torch.load(
        path,
        map_location="cpu",
        weights_only=True
    )

    model.load_state_dict(state_dict)
    return model

@torch.inference_mode()
def plot_segmentation(
    model: torch.nn.Module,
    dataset: WagDataset,
    i: int,
    device: torch.device
) -> None:
    model.eval()

    # Get image and ground truth
    image, target = dataset[i]

    # Model inference
    logits = model(image.unsqueeze(0).to(device))

    # Convert predicted segmentation to RGB using dataset's color map
    pred_mask = dataset.class_to_mask(logits)[0].astype(np.uint8)

    # Convert ground truth class IDs to RGB
    colors = np.empty((logits.shape[1], 3), dtype=np.uint8)

    for rgb, class_id in dataset.color_map.items():
        colors[class_id] = rgb

    gt_mask = colors[target.cpu().numpy()]

    # Convert image from [C, H, W] to [H, W, C]
    image = image.permute(1, 2, 0).cpu().numpy()

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    axes[0].imshow(np.clip(image, 0, 1))
    axes[0].set_title("Input Image")

    axes[1].imshow(gt_mask)
    axes[1].set_title("Ground Truth")

    axes[2].imshow(pred_mask)
    axes[2].set_title("Predicted Segmentation")

    for ax in axes:
        ax.axis("off")

    plt.tight_layout()
    plt.show()

assuma que no código assima a segmentação real não exista, nesse caso, tratamos o modelo como verdade já. Ele está em produção.

a predição do modelo deve ser mostrada na interface do software nas cores designadas com uma legenda mostrando.

## Detecção de deadends

Deadends são estruturas dentro do micro modelo (e de uma rocha também) onde o óleo entra e não consegue mais sair. São como se fossem becos sem saída.

Assuma que temos um modelo YOLOv5 já treinado pra detectar os deadends e seus pesos estão na forma de um .pt na pasta de modelos também.

o colab usando para treiná-la está em anexo junto com esse markdown na conversa

a yolo foi treinada para inferencia em pequenos tiles da imagem original, por isso, eis o algoritmo que faz tiled inference e junta as predições na imagem toda


# ============================================================
# YOLOv5 TILED INFERENCE
# Full image: 1792 x 1344
# Tile size: 224 x 224
# YOLO prediction size: 224 x 224
# Display confidence threshold: 0.70
# ============================================================

!pip -q install ultralytics opencv-python matplotlib torchvision

import os
import cv2
import torch
import numpy as np
import matplotlib.pyplot as plt

from torchvision.ops import batched_nms
from google.colab import drive


# ============================================================
# 1. CONFIGURATION
# ============================================================

drive.mount("/content/drive")

WEIGHTS_PATH = "/content/drive/MyDrive/YOLOv5Models/best.pt"

IMAGE_PATH = (
    "/content/drive/MyDrive/wag-segmentation/outubro_2026/sliced/input/out_2026.png"
)

OUTPUT_PATH = "pred.png"

# Full image dimensions (width, height)
IMAGE_WIDTH = 1792
IMAGE_HEIGHT = 1344

# Tiling configuration
TILE_SIZE = 224
OVERLAP = 0.25

# YOLO inference configuration
INFERENCE_SIZE = 224
CONF_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45

# Minimum confidence required to SHOW a prediction
DISPLAY_CONF_THRESHOLD = 0.70

# Global NMS
GLOBAL_NMS_IOU = 0.45

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ============================================================
# 2. LOAD MODEL
# ============================================================

assert os.path.exists(WEIGHTS_PATH), (
    f"Weights not found: {WEIGHTS_PATH}"
)

model = torch.hub.load(
    "ultralytics/yolov5",
    "custom",
    path=WEIGHTS_PATH,
    force_reload=False
)

model.to(DEVICE)
model.eval()

model.conf = CONF_THRESHOLD
model.iou = IOU_THRESHOLD

print(f"Model loaded on {DEVICE}")


# ============================================================
# 3. LOAD AND RESIZE IMAGE
# ============================================================

image = cv2.imread(IMAGE_PATH)

assert image is not None, (
    f"Could not load image: {IMAGE_PATH}"
)

original_height, original_width = image.shape[:2]

print(
    f"Original resolution: "
    f"{original_width}x{original_height}"
)

# Resize to EXACTLY 1792 x 1344
image = cv2.resize(
    image,
    (IMAGE_WIDTH, IMAGE_HEIGHT),
    interpolation=cv2.INTER_LINEAR
)

height, width = image.shape[:2]

print(f"Resized resolution: {width}x{height}")

assert width == IMAGE_WIDTH
assert height == IMAGE_HEIGHT


# ============================================================
# 4. GENERATE TILE COORDINATES
# ============================================================

def generate_positions(length, tile_size, stride):
    """
    Generate tile starting positions while ensuring
    complete coverage of the image.
    """

    if length <= tile_size:
        return [0]

    positions = list(
        range(0, length - tile_size + 1, stride)
    )

    last_position = length - tile_size

    if positions[-1] != last_position:
        positions.append(last_position)

    return positions


def generate_tiles(image, tile_size=224, overlap=0.25):
    """
    Split image into overlapping tiles.

    Returns:
        List of tuples:
        (tile_image, x_offset, y_offset)
    """

    height, width = image.shape[:2]

    stride = max(
        1,
        int(tile_size * (1 - overlap))
    )

    x_positions = generate_positions(
        width, tile_size, stride
    )

    y_positions = generate_positions(
        height, tile_size, stride
    )

    tiles = []

    for y in y_positions:
        for x in x_positions:

            tile = image[
                y:y + tile_size,
                x:x + tile_size
            ]

            tiles.append((tile, x, y))

    return tiles


# ============================================================
# 5. TILED INFERENCE
# ============================================================

def tiled_inference(
    image,
    model,
    tile_size=224,
    overlap=0.25,
    inference_size=224,
    global_nms_iou=0.45
):
    """
    Run YOLOv5 independently on overlapping tiles.

    Steps:
        1. Generate overlapping tiles
        2. Run YOLOv5 inference on each tile
        3. Convert local boxes to global coordinates
        4. Apply global class-aware NMS

    Returns:
        boxes, scores, labels
    """

    tiles = generate_tiles(
        image,
        tile_size=tile_size,
        overlap=overlap
    )

    print(f"Generated {len(tiles)} tiles")

    all_boxes = []
    all_scores = []
    all_labels = []

    for tile_idx, (tile, x_offset, y_offset) in enumerate(tiles):

        # OpenCV BGR -> RGB
        tile_rgb = cv2.cvtColor(
            tile,
            cv2.COLOR_BGR2RGB
        )

        # YOLO prediction
        with torch.no_grad():
            results = model(
                tile_rgb,
                size=inference_size
            )

        # [x1, y1, x2, y2, confidence, class]
        detections = results.xyxy[0].cpu().numpy()

        for detection in detections:

            x1, y1, x2, y2, confidence, class_id = detection

            # Local -> global coordinates
            global_x1 = x1 + x_offset
            global_y1 = y1 + y_offset
            global_x2 = x2 + x_offset
            global_y2 = y2 + y_offset

            all_boxes.append([
                global_x1,
                global_y1,
                global_x2,
                global_y2
            ])

            all_scores.append(float(confidence))
            all_labels.append(int(class_id))

        if (tile_idx + 1) % 20 == 0:
            print(
                f"Processed {tile_idx + 1}/{len(tiles)} tiles"
            )

    # No detections
    if len(all_boxes) == 0:

        return (
            torch.empty((0, 4)),
            torch.empty((0,)),
            torch.empty((0,), dtype=torch.long)
        )

    boxes = torch.tensor(
        np.array(all_boxes),
        dtype=torch.float32
    )

    scores = torch.tensor(
        all_scores,
        dtype=torch.float32
    )

    labels = torch.tensor(
        all_labels,
        dtype=torch.long
    )

    print(f"Detections before NMS: {len(boxes)}")

    # Global class-aware NMS
    keep_indices = batched_nms(
        boxes,
        scores,
        labels,
        global_nms_iou
    )

    boxes = boxes[keep_indices]
    scores = scores[keep_indices]
    labels = labels[keep_indices]

    print(f"Detections after NMS: {len(boxes)}")

    return boxes, scores, labels


# ============================================================
# 6. FILTER PREDICTIONS BY DISPLAY CONFIDENCE
# ============================================================

def filter_predictions(
    boxes,
    scores,
    labels,
    confidence_threshold=0.70
):
    """
    Keep only predictions with confidence >= threshold.
    """

    mask = scores >= confidence_threshold

    filtered_boxes = boxes[mask]
    filtered_scores = scores[mask]
    filtered_labels = labels[mask]

    print(
        f"Predictions with confidence >= "
        f"{confidence_threshold:.2f}: {len(filtered_boxes)}"
    )

    return filtered_boxes, filtered_scores, filtered_labels


# ============================================================
# 7. DRAW DETECTIONS
# ============================================================

def draw_detections(
    image,
    boxes,
    scores,
    labels,
    class_names=None
):
    """
    Draw filtered detections on the full image.
    """

    output = image.copy()

    for box, score, label in zip(
        boxes, scores, labels
    ):

        x1, y1, x2, y2 = map(
            int,
            box.tolist()
        )

        class_id = int(label)

        if class_names is not None:
            class_name = class_names[class_id]
        else:
            class_name = str(class_id)

        text = f"{class_name}: {float(score):.2f}"

        cv2.rectangle(
            output,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

        cv2.putText(
            output,
            text,
            (x1, max(y1 - 5, 0)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA
        )

    return output


# ============================================================
# 8. RUN TILED INFERENCE
# ============================================================

boxes, scores, labels = tiled_inference(
    image=image,
    model=model,
    tile_size=TILE_SIZE,
    overlap=OVERLAP,
    inference_size=INFERENCE_SIZE,
    global_nms_iou=GLOBAL_NMS_IOU
)


# ============================================================
# 9. APPLY DISPLAY CONFIDENCE THRESHOLD
# ============================================================

display_boxes, display_scores, display_labels = filter_predictions(
    boxes=boxes,
    scores=scores,
    labels=labels,
    confidence_threshold=DISPLAY_CONF_THRESHOLD
)


# ============================================================
# 10. DRAW AND SAVE RESULTS
# ============================================================

result_image = draw_detections(
    image,
    display_boxes,
    display_scores,
    display_labels,
    class_names=model.names
)

cv2.imwrite(
    OUTPUT_PATH,
    result_image
)

print(f"Result saved to: {OUTPUT_PATH}")


# ============================================================
# 11. DISPLAY RESULTS
# ============================================================

plt.figure(figsize=(18, 14))

plt.imshow(
    cv2.cvtColor(
        result_image,
        cv2.COLOR_BGR2RGB
    )
)

plt.title(
    f"YOLOv5 Tiled Inference ({IMAGE_WIDTH}x{IMAGE_HEIGHT}) | "
    f"{len(display_boxes)} detections | "
    f"Confidence >= {DISPLAY_CONF_THRESHOLD:.2f}"
)

plt.axis("off")
plt.tight_layout()
plt.show()


sempre redimensione a imagem original para as dimensões nesse código e sempre faça inferencia com window size de 224x224 da yolo.


## Analise de dados do programa

O programa deve pegar as duas saídas (as duas imagens segmentadas) e faer uma analise detalhada de proporções de classes

1. proporção de classes na imagem toda (segmentação completa)
2. proporção de classes apenas dentro dos deadends --> e mostrar quais classes são mais comuns de estar dentro de deadends

fazer um gráfico comparativo entre 1. e 2. permitindo tirar insights.

mostrar quantos % da imagem são dead ends

o programa deve ter uma aba quer permite ver cada dead end separadamente permitindo analise individual, em uma grid, que ao clicar no deadend ele abre expandindo.


## Formato geral da estrutura de arquivos

Podem ser necessárias mudanças de acordo com o contexto de desenvolvimento do programa, porém siga essa divisão central com recomendações de frameworks e conexões especificadas:

MICROMODEL_ANALYSIS/
│
├── ALGORITHMS/                         # Scripts de análise (pacote Python)
│   ├── __init__.py                     # Exporta todas as classes dos indicadores
│   ├── main.py                         # Orquestrador: roda todos os indicadores
│   ├── config.yaml                     # Parâmetros (px→µm, profundidade, caminhos dos modelos)
│   │
│   ├── core/                           # Base comum a todos os indicadores
│   │   ├── __init__.py
│   │   ├── base_indicator.py           # Classe abstrata BaseIndicator (compute(), to_dict())
│   │   ├── inference.py                # Carrega U-Net e YOLO e gera máscaras/detecções
│   │   ├── overlay.py                  # Interseção máscara U-Net × região YOLO, boca do dead-end
│   │   ├── registration.py             # Registro de imagem entre frames
│   │   ├── calibration.py              # Conversão px → µm, área → volume
│   │   └── io_utils.py                 # Leitura de imagens/vídeos e exportação de resultados
│   │
│   ├── indicators/                     # Um script por indicador
│   │   ├── __init__.py
│   │   ├── saturacao_local.py          # class SaturacaoLocal
│   │   ├── oleo_residual_recuperacao.py# class OleoResidualRecuperacao
│   │   ├── cinetica_mobilizacao.py     # class CineticaMobilizacao
│   │   ├── invasao_dead_ends.py        # class InvasaoDeadEnds
│   │   ├── molhabilidade_interfacial.py# class MolhabilidadeInterfacial (ângulo, curvatura, Pc)
│   │   ├── conectividade_aprisionamento.py # class ConectividadeAprisionamento
│   │   ├── geometria_desempenho.py     # class GeometriaDesempenho
│   │   └── dinamica_trifasica.py       # class DinamicaTrifasica
│   │
│   ├── data/                           # Dados de entrada e saída das análises
│   │   ├── raw/                        # Imagens/vídeos do micromodelo
│   │   ├── reference/                  # Imagem de referência (seca/saturada) p/ detecção YOLO
│   │   ├── masks/                      # Máscaras geradas pela U-Net
│   │   ├── detections/                 # Detecções YOLO (json/txt)
│   │   └── results/                    # CSV/JSON com os indicadores calculados
│   │
│   └── tests/
│       ├── __init__.py
│       ├── test_overlay.py
│       └── test_indicators.py
│
├── MODELS/                             # Modelos treinados (parâmetros dos scripts)
│   ├── unet/
│   │   ├── unet_best.pt                # Pesos da U-Net
│   │   ├── unet_config.yaml            # Arquitetura, nº de classes, normalização
│   │   └── classes.yaml                # 0=micromodelo, 1=água, 2=óleo, 3=gás
│   ├── yolo/
│   │   ├── yolo_deadend.pt             # Pesos do YOLO
│   │   └── data.yaml                   # Classes (dead_end, garganta, ...)
│   └── README.md                       # Versão, métricas e data de treino de cada modelo
│
├── API/
│   ├── FASTAPI/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── v1/
│   │   │   │   │   ├── endpoints/
│   │   │   │   │   │   ├── auth.py
│   │   │   │   │   │   ├── experiments.py  # CRUD de experimentos
│   │   │   │   │   │   ├── analysis.py     # Dispara ALGORITHMS/main.py, status do job
│   │   │   │   │   │   ├── indicators.py   # Consulta resultados por indicador
│   │   │   │   │   │   └── uploads.py      # Upload de imagens/vídeos
│   │   │   │   │   └── api.py
│   │   │   │   └── deps.py
│   │   │   ├── core/
│   │   │   │   ├── config.py
│   │   │   │   ├── security.py
│   │   │   │   └── users_fake.py
│   │   │   ├── db/
│   │   │   │   ├── base.py
│   │   │   │   ├── models.py           # Experiment, Frame, DeadEnd, IndicatorResult
│   │   │   │   └── session.py
│   │   │   ├── schemas/                # Pydantic
│   │   │   │   ├── experiment.py
│   │   │   │   └── indicator.py
│   │   │   ├── services/
│   │   │   │   └── analysis_service.py # Ponte entre a API e o pacote ALGORITHMS
│   │   │   └── main.py
│   │   ├── Dockerfile                  # Imagem do backend (API + ALGORITHMS + MODELS)
│   │   ├── requirements.txt
│   │   └── README.md
│   └── MQTT/
│       ├── mqtt_client.py
│       └── mosquitto.conf
│
├── DATABASE/
│   ├── database.db                     # SQLite (montado como volume no Docker)
│   └── migrations/                     # Alembic
│       ├── env.py
│       └── versions/
│
├── FRONTEND/                           # React + Vite
│   ├── public/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js               # Axios/fetch para a FastAPI
│   │   ├── components/
│   │   │   ├── ImageViewer.jsx         # Imagem com overlay U-Net + bboxes YOLO
│   │   │   ├── IndicatorCard.jsx
│   │   │   └── Charts/
│   │   │       ├── SaturationChart.jsx
│   │   │       └── KineticsChart.jsx
│   │   ├── pages/
│   │   │   ├── Login.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Experiments.jsx
│   │   │   └── Analysis.jsx
│   │   ├── hooks/
│   │   ├── context/
│   │   │   └── AuthContext.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── .env
│   ├── nginx.conf                      # Serve o build e faz proxy /api → backend
│   ├── Dockerfile                      # Multi-stage: build Vite → nginx
│   └── .dockerignore
│
├── venv/
├── docker-compose.yml                  # Serviços: backend, frontend, mosquitto
├── docker-compose.dev.yml              # Dev: hot reload (uvicorn --reload, vite dev)
├── .dockerignore
├── .env                                # Variáveis compartilhadas (SECRET_KEY, DB_URL...)
├── .gitignore
├── cloudflared_config.yml
├── INICIAR.bat                         # docker compose up -d --build
├── main.py                             # Execução local sem Docker
├── requirements.txt
└── README.md


## Considerações importantes: dimensões

Atenção para a diferença das dimensões de inferencia da yolo e da DCA UNet, elas fazem inferencia em dimensões diferentes, porém em um dado momento o software deve ter uma funcionalidade interna que automaticamente redimensiona as imagens para fazer as comparações dentro das caixas da yolo. lide com isso criando essa funcionalidade.

sempre respeite as dimensões de inferência.