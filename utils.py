def report_output(output, tokenizer):
    # print(f"Scores of shape [{len(output.scores)}]")
    # print(output.scores)
    print("Sequences scores")
    print(output.sequences_scores)
    # print("Beam indices")
    # print(output.beam_indices)
    print("Sequences")
    print(output.sequences)
    max_sequence_len = max([len(seq) for seq in output.sequences])
    print(f"Decoded sequences [of length {max_sequence_len}]")
    print(tokenizer.batch_decode(output[0], skip_special_tokens=True))
    # print("Last Beam Scores")
    # print(output.last_beam_scores)
    # print("Attention mask")
    # print(output.attentions)