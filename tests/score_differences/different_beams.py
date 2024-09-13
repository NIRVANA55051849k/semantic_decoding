import os
import sys
import torch
import string
import json
from tqdm import tqdm
from utils import compare_top_k
from transformers.generation.utils import GenerationConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
import pickle

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../generators')))

from syntactic import SyntacticGenerator

# read access token from environment variable
import os
import time

start_time = time.time()
access_token = os.getenv("HF_TOKEN")
# some models are gated and require a hf token (make sure to request access to the model)
if access_token is not None:
    print(f"Access token: {access_token[:3]}{'*' * 16}")
else:
    print("No access token found.")
    # sys.exit(1)

device = "cuda" if torch.cuda.is_available() else "cpu"
# device = "cpu" # comment in and out to quickly switch between cpu and gpu

# print all available devices
print(f"Available devices: {torch.cuda.device_count()}")
print( f"Device names: {[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}")

# selection of models
checkpoints = [
    # "meta-llama/Meta-Llama-3-8B-Instruct",
    # "meta-llama/Meta-Llama-3-70B-Instruct",
    # "mistralai/Mistral-7B-Instruct-v0.3",
    # "mistralai/Mistral-7B-v0.3",
    "EleutherAI/pythia-70m-deduped",
    "EleutherAI/pythia-160m-deduped",
    "EleutherAI/pythia-410m-deduped",
    "EleutherAI/pythia-1b-deduped",
    "EleutherAI/pythia-1.4b-deduped",
    "EleutherAI/pythia-2.8b-deduped",
    "EleutherAI/pythia-6.9b-deduped",
    "EleutherAI/pythia-12b-deduped",
]

###############################################
########### Notes about Experiments ###########
###############################################
# This experiment is designed to see how many beams
# would be the same for inputs with masking and batching.
# The experiment is in these steps:
# 1. Load the model
# 2. Prepare inputs and outputs
# 3. Run the experiment
#     a) baseline (no batching, no masking)
#     b) batched with multiple sequences (batching, no masking)
#     c) not batched and masking (short, not batched)
#     d) batched with multiple sequences and masking (short, batched)
#     e) not batched and masking (medium, not batched)
#     f) batched with multiple sequences and masking (medium, batched)
#     g) not batched and masking (long, not batched)
#     h) batched with multiple sequences and masking (long, batched)
# 4. Report the results

#### Experiments setup ####
amount_of_tokens = 200                           # amount of tokens generated
amount_of_beams = 1                              # amount of beams used for generation
beam_sizes = [1, 2, 3, 4, 5, 8, 10, 50, 100]     # which beams to compare

generation_config = GenerationConfig(
    renormalize_logits=True,
    num_beams=amount_of_beams,
    num_return_sequences=amount_of_beams,
    return_dict_in_generate=True,
    output_scores = True,
    output_logits = True,
    max_new_tokens = int(amount_of_tokens),
)
# select the model you want to test
model_name = checkpoints[0]

# examples with batching and wo batching
example = ["Obama was born"]
masking_addition_1 = [" 1"]
masking_addition_5 = [" fill up mask to 5"]
masking_addition_10 = [" these are words filling up to a mask of 10"]
example_1_masked = example + [example[0] + " 1"]
example_5_masked = example + [example[0] + " fill up mask to 5"]
example_10_masked = example + [example[0] + " these are words filling up to a mask of 10"]


# prompt samples from wikipedia (wikimedia/wikipedai from hf)
with open("dev/tests/score_differences/bs_prompts.json", "r", encoding="utf-8") as f:
    bs_prompts = json.load(f)

bs_prompts = bs_prompts[:250]


#### 1. loading model ####
# loading tokenizer and model
model = AutoModelForCausalLM.from_pretrained(model_name).to(device)
tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")
if tokenizer.pad_token_id is None:
    tokenizer.pad_token_id = tokenizer.eos_token_id
    generation_config.pad_token_id = tokenizer.pad_token_id

print(f"Model {model_name} loaded successfully")

descriptors = list(string.ascii_lowercase[:8])
max_tokens = min(generation_config.max_new_tokens +1, 200)
max_beams = 200
# results are of shape (beam_idx, prompt_idx,) and value is at the how maniest token the beams were still the same
results = {key: torch.full((max_beams, len(bs_prompts)), -1, dtype=torch.int16) for key in descriptors[1:]}

progress_bar = tqdm(total=len(bs_prompts), unit="prompt")
for prompt_idx, prompt in enumerate(bs_prompts):
    prompt_time = time.time()
    example = " ".join(prompt["text"][:50].split(" ")[:-1])
    example_1_masked = [example] + [example + " 1"]
    example_5_masked = [example] + [example + " fill up mask to 5"]
    example_10_masked = [example] + [example + " these are words filling up to a mask of 10"]

    
    #### 2. prepare inputs and outputs ####
    model_inputs = tokenizer([example], return_tensors="pt", padding=True).to(device)
    model_inputs_1_masked = tokenizer(example_1_masked, return_tensors="pt", padding=True).to(device)
    model_inputs_5_masked = tokenizer(example_5_masked, return_tensors="pt", padding=True).to(device)
    model_inputs_10_masked = tokenizer(example_10_masked, return_tensors="pt", padding=True).to(device)
    original_input_length = model_inputs["input_ids"].shape[-1]
    original_input_length_1_masked = model_inputs_1_masked["input_ids"].shape[-1]
    original_input_length_5_masked = model_inputs_5_masked["input_ids"].shape[-1]
    original_input_length_10_masked = model_inputs_10_masked["input_ids"].shape[-1]
    assert all(
        [
            original_input_length_1_masked - 1 == original_input_length,
            original_input_length_5_masked - 5 == original_input_length,
            original_input_length_10_masked - 10 == original_input_length,
        ]
    ), "Mask length is not as expected"

    model_inputs["input_ids"] = model_inputs["input_ids"][:1]
    model_inputs["attention_mask"] = model_inputs["attention_mask"][:1]
    model_inputs_batched = {}
    model_inputs_batched["input_ids"] = model_inputs["input_ids"][:1].repeat(4, 1)
    model_inputs_batched["attention_mask"] = model_inputs["attention_mask"][:1].repeat(4, 1)
    # use the same sentence multiple times (batching) with mask
    model_inputs_1_masked["input_ids"] = model_inputs_1_masked["input_ids"][:1]
    model_inputs_1_masked["attention_mask"] = model_inputs_1_masked["attention_mask"][:1]
    model_inputs_1_m_b = {}
    model_inputs_1_m_b["input_ids"] = model_inputs_1_masked["input_ids"][:1].repeat(4, 1)
    model_inputs_1_m_b["attention_mask"] = model_inputs_1_masked["attention_mask"][:1].repeat(4, 1)
    model_inputs_5_masked["input_ids"] = model_inputs_5_masked["input_ids"][:1]
    model_inputs_5_masked["attention_mask"] = model_inputs_5_masked["attention_mask"][:1]
    model_inputs_5_m_b = {}
    model_inputs_5_m_b["input_ids"] = model_inputs_5_masked["input_ids"][:1].repeat(4, 1)
    model_inputs_5_m_b["attention_mask"] = model_inputs_5_masked["attention_mask"][:1].repeat(4, 1)
    model_inputs_10_masked["input_ids"] = model_inputs_10_masked["input_ids"][:1]
    model_inputs_10_masked["attention_mask"] = model_inputs_10_masked["attention_mask"][:1]
    model_inputs_10_m_b = {}
    model_inputs_10_m_b["input_ids"] = model_inputs_10_masked["input_ids"][:1].repeat(4, 1)
    model_inputs_10_m_b["attention_mask"] = model_inputs_10_masked["attention_mask"][:1].repeat(4, 1)

    inputs = {
        "b": model_inputs_batched,
        "c": model_inputs_1_masked,
        "d": model_inputs_1_m_b,
        "e": model_inputs_5_masked,
        "f": model_inputs_5_m_b,
        "g": model_inputs_10_masked,
        "h": model_inputs_10_m_b,
    }
    #### 3. Run experiment ####
    progress_bar.set_postfix({"status": "a Gen"})
    # a
    out_baseline = model.generate(
        **model_inputs,
        generation_config=generation_config,
    )

    def find_amount_beams_supported(out_baseline, out_other, until_beam: int, until_token: int = None):
        if until_token is None:
            until_token = amount_of_tokens
        for amount_beams in range(1, until_beam+1, 10):
            result = compare_top_k(
                torch.stack(out_baseline.scores)[:until_token, :4],
                torch.stack(out_other.scores)[:until_token, :4],
                amount_beams,
                -1
            )
            if result is not True:
                result = amount_beams
                break
        for amount_beams in range(max(result-10, 0), result+10, 1):
            result = compare_top_k(
                torch.stack(out_baseline.scores)[:until_token, :4],
                torch.stack(out_other.scores)[:until_token, :4],
                amount_beams,
                -1
            )
            if result is not True:
                result = amount_beams
                break
        return result

    def find_amount_tokens_supported(out_baseline, out_other, amount_beam: int, until_token: int):
        for amount_tokens in range(1, until_token+1, 10):
            result = compare_top_k(
                torch.stack(out_baseline.scores)[:amount_tokens, :4],
                torch.stack(out_other.scores)[:amount_tokens, :4],
                amount_beam,
                -1
            )
            if result is not True:
                amount_tokens = amount_tokens -1
                break
            if amount_tokens >= until_token:
                return amount_tokens
        for amount_tokens in range(max(amount_tokens-10, 1), amount_tokens+10, 1):
            result = compare_top_k(
                torch.stack(out_baseline.scores)[:amount_tokens, :4],
                torch.stack(out_other.scores)[:amount_tokens, :4],
                amount_beam,
                -1
            )
            if result is not True:
                amount_of_tokens = amount_tokens -1
                break
            if amount_tokens >= until_token:
                return amount_tokens
        return amount_of_tokens

    #### 4. Report the results ####
    tqdm.write("\n")
    tqdm.write("Differences in beams; baseline vs tests")

    tqdm.write(f"Would the beams have been the same for #tokens and #beams?")
    for desc in descriptors[1:]:
        progress_bar.set_postfix({"status": f"{desc} Gen"})
        # run model (b-h)
        output_experiment = model.generate(
            **inputs[desc],
            generation_config=generation_config,
        )

        last_beams_by_token = []
        tqdm.write(f"{descriptors[0]} vs {desc})")
        for beams in range(1, max_beams+1, 1):
            progress_bar.set_postfix({"status": f"{desc} Sea"})
            result = find_amount_tokens_supported(out_baseline, output_experiment, beams, max_tokens)
            results[desc][beams-1, prompt_idx] = result
            if result == 0:
                # although technically still possible to go back to a stage where they are the same again
                tqdm.write(f"{beams:3d} beams; Last amount of tokens for which beams were the same: {result:3d} tokens")
                # fill rest of indices with zero as well
                results[desc][beams:, prompt_idx] = 0
                break
        del output_experiment
        torch.cuda.empty_cache()
    # give update on time for last iteration
    tqdm.write(f"Prompt {prompt_idx+1}/{len(bs_prompts)} took {int((time.time() - prompt_time)//60):2d}:{(time.time() - prompt_time) % 60:.2f} [{int((time.time() - start_time) // 3600):2d}:{int((time.time() - start_time)//60) % 60:2d}:{(time.time() - start_time) % 60:.2f}]")
    progress_bar.update(1)

progress_bar.close()

print(f"Saving to file: dev/tests/score_differences/different_beams_resulst.pkl")
with open("dev/tests/score_differences/different_beams_results.pkl", "ab") as f:
    pickle.dump(results, f)

print(f"Total time: {int((time.time() - start_time) // 3600):2d}:{int((time.time() - start_time)//60) % 60:2d}:{(time.time() - start_time) % 60:.2f}")
print("Done")