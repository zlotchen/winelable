## Instructions for downloading to local server hugginface models for image-to-text extraction:

pip install -U "huggingface_hub"

# allow authentication to HF:

hf auth login

# create local directory and download

cd <project workdirectory>

# first the smaller quantilzed model

mkdir -p models/SmolVLM-500M-Instruct

huggingface-cli download HuggingFaceTB/SmolVLM-500M-Instruct --local-dir ./models/SmolVLM-500M-Instruct

# then the larger quantilzed model

mkdir -p models/SmolVLM-Instruct

huggingface-cli download HuggingFaceTB/SmolVLM-Instruct --local-dir ./models/SmolVLM-Instruct

