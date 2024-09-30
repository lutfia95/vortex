# Copyright (c) 2024, Michael Poli.

# Copyright (c) Together
# This software is distributed under the terms of the Apache License, Version 2.0
# Author: Michael Poli

import argparse
import os

import torch
import yaml

from vortex.model.generation import Generator
from vortex.model.model import StripedHyena
from vortex.model.sample import sample
from vortex.model.tokenizer import HFAutoTokenizer, CharLevelTokenizer
from vortex.model.utils import dotdict, print_rank_0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run StripedHyena Model")
    parser.add_argument("--config_path", required=True, help="Path to configuration file")
    parser.add_argument("--checkpoint_path", default=None, help="Path to checkpoint file")
    parser.add_argument("--num_tokens", default=84, help="Number of tokens to generate.")
    parser.add_argument("--prompt_file", default="./prompt.txt", help="Path to prompt file.")
    parser.add_argument(
        "--cached_generation",
        action="store_true",
        help="Use kv and hyena caching to speed up generation.",
    )

    torch.manual_seed(1)
    torch.cuda.manual_seed(1)
    args = parser.parse_args()

    config = dotdict(yaml.load(open(args.config_path), Loader=yaml.FullLoader))

    if config.tokenizer_type == "CharLevelTokenizer":
        tokenizer = CharLevelTokenizer(config.vocab_size)
    else:
        tokenizer = HFAutoTokenizer(config.vocab_file)
    
    print(f"Loaded config: {config}")

    device = torch.device("cuda")
    m = StripedHyena(config)

    print_rank_0("Loading state dict...", end="\n\n")

    if args.checkpoint_path:
        state_dict = torch.load(args.checkpoint_path, map_location=device)
        print(m.state_dict().keys())
        print(state_dict.keys())
        # inv_freq are instantiated as parameters
        m.load_state_dict(state_dict, strict=False)

    m = m.to(device)
    m.to_bfloat16_except_pr_lc()

    with open(args.prompt_file, "r") as f:
        input_string = f.read()
    print_rank_0(f"Prompt: {input_string}", end="\n\n")

    with torch.inference_mode():
        g = Generator(m, tokenizer, top_k=1, top_p=1, temperature=1)
        g.generate(
            num_tokens=args.num_tokens,
            cached_generation=args.cached_generation,
            input_string=input_string,
            device=device,
            verbose=True,
            print_generation=True,
            max_seqlen=8192,
        )
