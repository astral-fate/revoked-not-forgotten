"""Convert the AutoScientist PEFT LoRA (Qwen/Qwen3.5-4B, text layers) to a llama.cpp GGUF LoRA adapter.

Written for this experiment (uses only the PyPI `gguf` package). It reproduces what llama.cpp's converter does to the
base weights of Qwen3.5 so the adapter lines up with the base GGUF:
  * HF module -> GGUF tensor name (table below);
  * linear-attention V heads are reordered from grouped-by-K-head to tiled order (16 K heads, 32 V heads): rows of
    lora_B for in_proj_qkv (V part), in_proj_z, in_proj_a, in_proj_b; columns of lora_A for out_proj.
Every produced tensor is checked against the base GGUF's shape. Vision-tower adapters (if any) are dropped.
Usage: python lora_to_gguf.py <adapter_dir> <base.gguf> <out.gguf>
"""
import json
import re
import sys
from pathlib import Path

import gguf
import numpy as np
import torch
from safetensors.torch import load_file

NK, NV, HK, HV = 16, 32, 128, 128
VPK = NV // NK
MAP = {"linear_attn.in_proj_qkv": "attn_qkv", "linear_attn.in_proj_z": "attn_gate", "linear_attn.in_proj_a": "ssm_alpha",
       "linear_attn.in_proj_b": "ssm_beta", "linear_attn.out_proj": "ssm_out", "self_attn.q_proj": "attn_q",
       "self_attn.k_proj": "attn_k", "self_attn.v_proj": "attn_v", "self_attn.o_proj": "attn_output",
       "mlp.gate_proj": "ffn_gate", "mlp.up_proj": "ffn_up", "mlp.down_proj": "ffn_down"}


def vperm(n, hd):
    return torch.arange(n).reshape(NK, VPK, hd).permute(1, 0, 2).contiguous().reshape(n)


def main(adir, base, out):
    adir = Path(adir)
    cfg = json.loads((adir / "adapter_config.json").read_text())
    sd = load_file(str(adir / "adapter_model.safetensors"))
    shapes = {t.name: [int(x) for x in t.shape] for t in gguf.GGUFReader(base).tensors}
    pairs, dropped = {}, []
    for k, v in sd.items():
        m = re.search(r"layers\.(\d+)\.(linear_attn|self_attn|mlp)\.(\w+)\.lora_([AB])\.weight$", k)
        if not m or "visual" in k or "mtp" in k:
            dropped.append(k)
            continue
        bid, grp, mod, ab = m.groups()
        pairs.setdefault((int(bid), f"{grp}.{mod}"), {})[ab] = v.float()
    w = gguf.GGUFWriter(out, "qwen35")
    w.add_type(gguf.GGUFType.ADAPTER)
    w.add_string(gguf.Keys.Adapter.TYPE, "lora")
    w.add_float32(gguf.Keys.Adapter.LORA_ALPHA, float(cfg["lora_alpha"]))
    n = 0
    for (bid, mod), t in sorted(pairs.items()):
        A, B = t["A"], t["B"]  # A: (r, in), B: (out, r)
        if mod == "linear_attn.in_proj_qkv":
            qk = 2 * NK * HK
            B = torch.cat([B[:qk], B[qk:][vperm(B.shape[0] - qk, HV)]], 0)
        elif mod == "linear_attn.in_proj_z":
            B = B[vperm(B.shape[0], HV)]
        elif mod in ("linear_attn.in_proj_a", "linear_attn.in_proj_b"):
            B = B[vperm(B.shape[0], 1)]
        elif mod == "linear_attn.out_proj":
            A = A[:, vperm(A.shape[1], HV)]
        name = f"blk.{bid}.{MAP[mod]}.weight"
        ins, outs = shapes[name]  # gguf order: ne0 = in, ne1 = out
        assert (A.shape[1], B.shape[0]) == (ins, outs), (name, A.shape, B.shape, shapes[name])
        w.add_tensor(name + ".lora_a", A.to(torch.float16).numpy())
        w.add_tensor(name + ".lora_b", B.to(torch.float16).numpy())
        n += 1
    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file()
    w.close()
    print(f"wrote {n} LoRA pairs (r={cfg.get('r')}, alpha={cfg['lora_alpha']}) to {out}; dropped {len(dropped)} tensors",
          dropped[:5])


if __name__ == "__main__":
    main(*sys.argv[1:4])
