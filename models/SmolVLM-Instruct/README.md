---
library_name: transformers
license: apache-2.0
datasets:
- HuggingFaceM4/the_cauldron
- HuggingFaceM4/Docmatix
pipeline_tag: image-text-to-text
language:
- en
base_model:
- HuggingFaceTB/SmolLM2-1.7B-Instruct
- google/siglip-so400m-patch14-384
---

<img src="https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/SmolVLM.png" width="800" height="auto" alt="Image description">

# SmolVLM

SmolVLM is a compact open multimodal model that accepts arbitrary sequences of image and text inputs to produce text outputs. Designed for efficiency, SmolVLM can answer questions about images, describe visual content, create stories grounded on multiple images, or function as a pure language model without visual inputs. Its lightweight architecture makes it suitable for on-device applications while maintaining strong performance on multimodal tasks.

## Model Summary

- **Developed by:** Hugging Face 🤗
- **Model type:** Multi-modal model (image+text)
- **Language(s) (NLP):** English
- **License:** Apache 2.0
- **Architecture:** Based on [Idefics3](https://huggingface.co/HuggingFaceM4/Idefics3-8B-Llama3) (see technical summary)

## Resources

- **Demo:** [SmolVLM Demo](https://huggingface.co/spaces/HuggingFaceTB/SmolVLM)
- **Blog:** [Blog post](https://huggingface.co/blog/smolvlm)

## Uses

SmolVLM can be used for inference on multimodal (image + text) tasks where the input comprises text queries along with one or more images. Text and images can be interleaved arbitrarily, enabling tasks like image captioning, visual question answering, and storytelling based on visual content. The model does not support image generation.

To fine-tune SmolVLM on a specific task, you can follow the fine-tuning tutorial.
<!-- todo: add link to fine-tuning tutorial -->

### Technical Summary

SmolVLM leverages the lightweight SmolLM2 language model to provide a compact yet powerful multimodal experience. It introduces several changes compared to previous Idefics models:

- **Image compression:** We introduce a more radical image compression compared to Idefics3 to enable the model to infer faster and use less RAM.
- **Visual Token Encoding:** SmolVLM uses 81 visual tokens to encode image patches of size 384×384. Larger images are divided into patches, each encoded separately, enhancing efficiency without compromising performance.

More details about the training and architecture are available in our technical report.


### How to get started

You can use transformers to load, infer and fine-tune SmolVLM.

```python
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForVision2Seq
from transformers.image_utils import load_image

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Load images
image1 = load_image("https://cdn.britannica.com/61/93061-050-99147DCE/Statue-of-Liberty-Island-New-York-Bay.jpg")
image2 = load_image("https://huggingface.co/spaces/merve/chameleon-7b/resolve/main/bee.jpg")

# Initialize processor and model
processor = AutoProcessor.from_pretrained("HuggingFaceTB/SmolVLM-Instruct")
model = AutoModelForVision2Seq.from_pretrained(
    "HuggingFaceTB/SmolVLM-Instruct",
    torch_dtype=torch.bfloat16,
    _attn_implementation="flash_attention_2" if DEVICE == "cuda" else "eager",
).to(DEVICE)

# Create input messages
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image"},
            {"type": "image"},
            {"type": "text", "text": "Can you describe the two images?"}
        ]
    },
]

# Prepare inputs
prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
inputs = processor(text=prompt, images=[image1, image2], return_tensors="pt")
inputs = inputs.to(DEVICE)

# Generate outputs
generated_ids = model.generate(**inputs, max_new_tokens=500)
generated_texts = processor.batch_decode(
    generated_ids,
    skip_special_tokens=True,
)

print(generated_texts[0])
"""
Assistant: The first image shows a green statue of the Statue of Liberty standing on a stone pedestal in front of a body of water. 
The statue is holding a torch in its right hand and a tablet in its left hand. The water is calm and there are no boats or other objects visible. 
The sky is clear and there are no clouds. The second image shows a bee on a pink flower. 
The bee is black and yellow and is collecting pollen from the flower. The flower is surrounded by green leaves.
"""
```


### Model optimizations

**Precision**: For better performance, load and run the model in half-precision (`torch.float16` or `torch.bfloat16`) if your hardware supports it.

```python
from transformers import AutoModelForVision2Seq
import torch

model = AutoModelForVision2Seq.from_pretrained(
    "HuggingFaceTB/SmolVLM-Instruct",
    torch_dtype=torch.bfloat16
).to("cuda")
```

You can also load SmolVLM with 4/8-bit quantization using bitsandbytes, torchao or Quanto. Refer to [this page](https://huggingface.co/docs/transformers/en/main_classes/quantization) for other options.

```python
from transformers import AutoModelForVision2Seq, BitsAndBytesConfig
import torch

quantization_config = BitsAndBytesConfig(load_in_8bit=True)
model = AutoModelForVision2Seq.from_pretrained(
    "HuggingFaceTB/SmolVLM-Instruct",
    quantization_config=quantization_config,
)
```

**Vision Encoder Efficiency**: Adjust the image resolution by setting `size={"longest_edge": N*384}` when initializing the processor, where N is your desired value. The default `N=4` works well, which results in input images of
size 1536×1536. For documents, `N=5` might be beneficial. Decreasing N can save GPU memory and is appropriate for lower-resolution images. This is also useful if you want to fine-tune on videos.


## Misuse and Out-of-scope Use

SmolVLM is not intended for high-stakes scenarios or critical decision-making processes that affect an individual's well-being or livelihood. The model may produce content that appears factual but may not be accurate. Misuse includes, but is not limited to:

- Prohibited Uses:
  - Evaluating or scoring individuals (e.g., in employment, education, credit)
  - Critical automated decision-making
  - Generating unreliable factual content
- Malicious Activities:
  - Spam generation
  - Disinformation campaigns
  - Harassment or abuse
  - Unauthorized surveillance

### License

SmolVLM is built upon [the shape-optimized SigLIP](https://huggingface.co/google/siglip-so400m-patch14-384) as image encoder and [SmolLM2](https://huggingface.co/HuggingFaceTB/SmolLM2-1.7B-Instruct) for text decoder part.

We release the SmolVLM checkpoints under the Apache 2.0 license.

## Training Details

### Training Data

The training data comes from [The Cauldron](https://huggingface.co/datasets/HuggingFaceM4/the_cauldron) and [Docmatix](https://huggingface.co/datasets/HuggingFaceM4/Docmatix) datasets, with emphasis on document understanding (25%) and image captioning (18%), while maintaining balanced coverage across other crucial capabilities like visual reasoning, chart comprehension, and general instruction following.
<img src="https://huggingface.co/HuggingFaceTB/SmolVLM-Instruct/resolve/main/mixture_the_cauldron.png" alt="Example Image" style="width:90%;" />




## Evaluation

| Model             | MMMU (val) | MathVista (testmini) | MMStar (val) | DocVQA (test) | TextVQA (val) | Min GPU RAM required (GB) |
|-------------------|------------|----------------------|--------------|---------------|---------------|---------------------------|
| SmolVLM           | 38.8       | 44.6                | 42.1         | 81.6          | 72.7          | 5.02                      |
| Qwen-VL 2B        | 41.1       | 47.8                | 47.5         | 90.1          | 79.7          | 13.70                     |
| InternVL2 2B      | 34.3       | 46.3                | 49.8         | 86.9          | 73.4          | 10.52                     |
| PaliGemma 3B 448px| 34.9       | 28.7                | 48.3         | 32.2          | 56.0          | 6.72                      |
| moondream2        | 32.4       | 24.3                | 40.3         | 70.5          | 65.2          | 3.87                      |
| MiniCPM-V-2       | 38.2       | 39.8                | 39.1         | 71.9          | 74.1          | 7.88                      |
| MM1.5 1B          | 35.8       | 37.2                | 0.0          | 81.0          | 72.5          | NaN                       |

# Citation information
You can cite us in the following way:
```bibtex
@article{marafioti2025smolvlm,
  title={SmolVLM: Redefining small and efficient multimodal models}, 
  author={Andrés Marafioti and Orr Zohar and Miquel Farré and Merve Noyan and Elie Bakouch and Pedro Cuenca and Cyril Zakka and Loubna Ben Allal and Anton Lozhkov and Nouamane Tazi and Vaibhav Srivastav and Joshua Lochner and Hugo Larcher and Mathieu Morlon and Lewis Tunstall and Leandro von Werra and Thomas Wolf},
  journal={arXiv preprint arXiv:2504.05299},
  year={2025}
}
```