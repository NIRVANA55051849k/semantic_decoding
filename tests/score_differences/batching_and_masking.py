import os
import sys
import torch
from utils import report

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
# This experiment is here to show differences in logits 
# (and ultimately scores) that occur due to 
# batching and masking.
# For that, the simple forward pass and generate 
# with greedy search and beam search are compared.
# 0. Imports, setup, etc
# 1. Loading tokenizer and model
# 2. Preparing inputs and outputs
# 3. a) direct forward pass
#       - no masking, no batching
#       - masking and batching
# 3. b) generate with greedy search
#       - no masking, no batching
#       - masking and batching
# 3. c) generate with beam search
#       - no masking, no batching
#       - masking and batching
# 4. Comparing and running tests
# 
# masking will occur in the following size:
# - no masking
# - 10 token masked
# batching is done with 4 sequences (always the same)

#### Experiments setup ####
amount_of_tokens = 2    # amount of tokens generated
amount_of_beams = 4     # amount of beams used for generation

# examples with batching and wo batching
example = ["Obama was born"]
example_10_masked = example + ["Obama was born these are words filling up to a mask of 10"]
# chose the example you want to test (singular or batched)


# select the model you want to test
model_name = checkpoints[0]


#### 1. loading model ####
# loading tokenizer and model
syntactic_generator = SyntacticGenerator(model_name, device, access_token)
model = syntactic_generator.model
tokenizer = syntactic_generator.tokenizer

print(f"Model {model_name} loaded successfully")


#### 2. prepare inputs and outputs ####
model_inputs = tokenizer(example, return_tensors="pt", padding=True).to(device)
model_inputs_10_masked = tokenizer(example_10_masked, return_tensors="pt", padding=True).to(device)
original_input_length = model_inputs["input_ids"].shape[-1]
original_input_length_10_masked = model_inputs_10_masked["input_ids"].shape[-1]
assert all(
    [
        original_input_length_10_masked - 10 == original_input_length,
    ]
), "Mask length is not as expected"

model_inputs["input_ids"] = model_inputs["input_ids"][:1]
model_inputs["attention_mask"] = model_inputs["attention_mask"][:1]
# use the same sentence multiple times (batching) with mask
model_inputs_10_masked["input_ids"] = model_inputs_10_masked["input_ids"][:1].repeat(4, 1)
model_inputs_10_masked["attention_mask"] = model_inputs_10_masked["attention_mask"][:1].repeat(4, 1)


#### 3. Run experiment ####
# a) direct forward pass with no, one, two, four and ten tokens masked
out_forward_no_mask = model(**model_inputs)
out_forward_10_masked = model(**model_inputs_10_masked)

# b) generate with greedy search with no, one, two, four and ten tokens masked
out_greedy_no_mask = syntactic_generator.generate(
    **model_inputs,
    max_new_tokens=int(amount_of_tokens),
    renormalize_logits=True,
    return_dict_in_generate=True,
    output_scores = True,
    output_logits = True,
)
out_greedy_10_masked = syntactic_generator.generate(
    **model_inputs_10_masked,
    max_new_tokens=int(amount_of_tokens),
    renormalize_logits=True,
    return_dict_in_generate=True,
    output_scores = True,
    output_logits = True,
)

# c) generate with beam search with no, one, two, four and ten tokens masked
out_bs_no_mask = syntactic_generator.generate(
    **model_inputs,
    max_new_tokens=int(amount_of_tokens),
    renormalize_logits=True,
    num_beams=amount_of_beams,
    num_return_sequences=amount_of_beams,
    return_dict_in_generate=True,
    output_scores = True,
    output_logits = True,
)
out_bs_10_masked = syntactic_generator.generate(
    **model_inputs_10_masked,
    max_new_tokens=int(amount_of_tokens),
    renormalize_logits=True,
    num_beams=amount_of_beams,
    num_return_sequences=amount_of_beams,
    return_dict_in_generate=True,
    output_scores = True,
    output_logits = True,
)

#### 4. Run tests ####
print("\n\n", "\t\tResults".upper())
print("#" * 40)
print()
print("a) Direct forward pass")

print("No masking, no batching vs 10 token masked, batched (4 times)")
print("Logits")
print(
    *report(
        out_forward_no_mask.logits[:, -1:, :],
        out_forward_10_masked.logits[0, -1:, :]
    )
)
print("Scores")
print(
    *report(
        out_forward_no_mask.logits[:, -1:, :].log_softmax(dim=-1).exp(),
        out_forward_10_masked.logits[0, -1:, :].log_softmax(dim=-1).exp(),
        compare_top = True
        )
)
print()
print("b) Generate with greedy search")

print("Logits")
print(
    *report(
        out_greedy_no_mask.logits[0],
        out_greedy_10_masked.logits[0][:1, :]
    )
)
print("Scores")
print(
    *report(
        out_greedy_no_mask.scores[0].exp(),
        out_greedy_10_masked.scores[0][:1, :].exp(),
        compare_top = True
    )
)

print()
print("c) Generate with beam search")
print("Logits")
print(
    *report(
        out_bs_no_mask.logits[0][:1, :],
        out_bs_10_masked.logits[0][:1, :]
    )
)

print("Scores")
print(
    *report(
        out_bs_no_mask.scores[0][:1, :].exp(),
        out_bs_10_masked.scores[0][:1, :].exp(),
        compare_top = True
    )
)

print("Done")