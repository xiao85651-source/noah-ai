"""No pretrained weights, remote model APIs, or downloaded tokenizers."""
from dataclasses import asdict, dataclass
import base64
import io
import zipfile
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

BOS, EOS, PAD, VOCAB = 256, 257, 258, 259

def encode(text, boundaries=False):
    result = list(text.encode('utf-8'))
    return [BOS, *result, EOS] if boundaries else result

def decode(tokens):
    return bytes(t for t in tokens if 0 <= t < 256).decode('utf-8', errors='replace')

@dataclass
class Config:
    context: int = 128
    width: int = 128
    heads: int = 4
    layers: int = 3
    vocab: int = VOCAB
    def validate(self):
        if self.vocab != VOCAB or not 16 <= self.context <= 512 or not 16 <= self.width <= 256 or not 1 <= self.heads <= 8 or self.width % self.heads or not 1 <= self.layers <= 6:
            raise ValueError('Unsupported Noah model configuration')

class Attention(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.heads, self.width = config.heads, config.width
        self.qkv = nn.Linear(config.width, 3 * config.width)
        self.output = nn.Linear(config.width, config.width)
    def forward(self, x):
        b, t, c = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)
        def split(tensor):
            return tensor.view(b, t, self.heads, c // self.heads).transpose(1, 2)
        y = F.scaled_dot_product_attention(split(q), split(k), split(v), is_causal=True)
        return self.output(y.transpose(1, 2).contiguous().view(b, t, c))

class Block(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.norm1, self.norm2 = nn.LayerNorm(config.width), nn.LayerNorm(config.width)
        self.attention = Attention(config)
        self.mlp = nn.Sequential(nn.Linear(config.width, 4 * config.width), nn.GELU(), nn.Linear(4 * config.width, config.width))
    def forward(self, x):
        x = x + self.attention(self.norm1(x))
        return x + self.mlp(self.norm2(x))

class Noah(nn.Module):
    def __init__(self, config=None):
        super().__init__()
        self.config = config or Config()
        self.config.validate()
        c = self.config
        self.token_embedding = nn.Embedding(c.vocab, c.width)
        self.position_embedding = nn.Embedding(c.context, c.width)
        self.blocks = nn.Sequential(*(Block(c) for _ in range(c.layers)))
        self.norm = nn.LayerNorm(c.width)
        self.head = nn.Linear(c.width, c.vocab, bias=False)
        self.apply(self._initialize)
        self.head.weight = self.token_embedding.weight
    def _initialize(self, layer):
        if isinstance(layer, (nn.Linear, nn.Embedding)):
            nn.init.normal_(layer.weight, mean=0, std=.02)
            if isinstance(layer, nn.Linear) and layer.bias is not None:
                nn.init.zeros_(layer.bias)
    def forward(self, tokens, targets=None):
        if tokens.ndim != 2 or not 1 <= tokens.shape[1] <= self.config.context:
            raise ValueError('Invalid token shape')
        x = self.token_embedding(tokens) + self.position_embedding(torch.arange(tokens.shape[1], device=tokens.device))
        logits = self.head(self.norm(self.blocks(x)))
        loss = F.cross_entropy(logits.reshape(-1, self.config.vocab), targets.reshape(-1)) if targets is not None else None
        return logits, loss
    @torch.no_grad()
    def generate(self, prompt, count=96, temperature=.8):
        self.eval()
        device = next(self.parameters()).device
        tokens = torch.tensor([[BOS, *encode(prompt)]], dtype=torch.long, device=device)
        output = []
        for _ in range(min(count, 256)):
            logits, _ = self(tokens[:, -self.config.context:])
            scores = logits[:, -1, :] / max(.1, temperature)
            scores[:, [BOS, PAD]] = -float('inf')
            top = min(40, scores.shape[-1])
            cutoff = torch.topk(scores, top)[0][:, -1:]
            scores[scores < cutoff] = -float('inf')
            token = torch.multinomial(F.softmax(scores, dim=-1), 1)
            if token.item() == EOS:
                break
            output.append(token.item())
            tokens = torch.cat((tokens, token), dim=1)
        return decode(output)

def pack_tensors(tensors):
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **{name: tensor.detach().cpu().float().numpy() for name, tensor in tensors.items()})
    return base64.b64encode(buffer.getvalue()).decode('ascii')

def unpack_tensors(payload, reference):
    if not isinstance(payload, str) or len(payload) > 24 * 1024 * 1024:
        raise ValueError('Tensor payload too large')
    raw = base64.b64decode(payload, validate=True)
    buffer = io.BytesIO(raw)
    with zipfile.ZipFile(buffer) as archive:
        files = archive.infolist()
        if len(files) != len(reference) or sum(f.file_size for f in files) > 32 * 1024 * 1024:
            raise ValueError('Invalid tensor archive')
    buffer.seek(0)
    result = {}
    with np.load(buffer, allow_pickle=False) as arrays:
        if set(arrays.files) != set(reference):
            raise ValueError('Unexpected tensor names')
        for name, parameter in reference.items():
            array = arrays[name]
            if array.shape != tuple(parameter.shape) or array.dtype != np.float32 or not np.isfinite(array).all():
                raise ValueError('Invalid tensor values or shape')
            result[name] = torch.from_numpy(array.copy())
    return result

def parameters(model):
    return dict(model.named_parameters())

def set_parameters(model, packed):
    values = unpack_tensors(packed, parameters(model))
    with torch.no_grad():
        for name, p in model.named_parameters():
            p.copy_(values[name].to(p.device))

def make_batch(ids, positions, context, device='cpu'):
    x = torch.tensor([ids[p:p+context] for p in positions], dtype=torch.long, device=device)
    y = torch.tensor([ids[p+1:p+context+1] for p in positions], dtype=torch.long, device=device)
    return x, y
