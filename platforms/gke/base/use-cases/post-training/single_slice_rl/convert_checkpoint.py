# Copyright 2026 Google LLC
# MaxText v0.2.3 LLaMA 3.1 8B Instruct Conversion Script

import sys
from maxtext.checkpoint_conversion import to_maxtext
from maxtext.configs import pyconfig

if __name__ == "__main__":
    print("Starting LLaMA 3.1 8B Instruct Hugging Face to MaxText v0.2.3 Conversion...", flush=True)
    to_maxtext.main(sys.argv)
    print("LLaMA 3.1 8B Instruct Conversion completed successfully.", flush=True)
