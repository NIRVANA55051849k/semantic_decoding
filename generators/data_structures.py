from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, is_dataclass
from typing import Optional, Tuple
import torch

"""
General structure
1. generation_step
    [
        a) semantic_hypothesis
            z) unique_key
            y) score
            x) SynthacticHypothesis
                [
                    - unique_key
                    - semantic_source_hypothesis_idx
                    - syntactic_source_hypothesis_idx
                    SemanticData:
                        - unique_key
                        - start
                        - end
                        - type
                        - other
                    SyntacticHypothesisContinuationData:
                        - sequences
                        - transition_scores
                        - last_beam_scores
                        - past_key_values
                        - attention_mask
                        - SyntacticHypothesisUnshortenedContinuationData:
                            - transition_scores
                            - sequences
                            - last_beam_scores
                            - past_key_values
                            - attention_mask
                    SynthacticHypothesisMetaData: [...]
                ]
            w) OriginalContinuationData
    ]
"""

# new dataclasses
@dataclass
class SemanticHypothesis:
    """
    Contains all the data which make up a semantic hypothesis.

    :param aggregation_key: Aggregation key of the hypothesis. The aggregation key
        is a composite key used to group syntactic hypotheses from the same previous 
        semantic hypothesis. It is constructed as follows:
        `f"{semantic_source_hypothesis_idx}-{semantic_data.unique_key}"`
    :type aggregation_key: str
    :param score: Score of the hypothesis. Is calculated from the scores of the
        syntactic hypotheses.
    :type score: float
    :param syntactic_hypotheses: Tuple of syntactic hypotheses that are part of the
        semantic hypothesis.
    :type syntactic_hypotheses: Tuple[SyntacticHypothesis, ...]
    :param source_data: Original data of the continuation. This data is in raw format
        (as output by the model) and optional, as it is highly unefficient to store.
    """
    aggregation_key: str
    score: float
    syntactic_hypotheses: Tuple[SyntacticHypothesis, ...]
    source_data: Optional[OriginalContinuationData]

    def __len__(self) -> int:
        return len(self.syntactic_hypotheses)

    def __repr__(self) -> str:
        return f"SemHyp({self.aggregation_key}, score={self.score}, syntactic_hypotheses={len(self.syntactic_hypotheses)})"

    def __str__(self) -> str:
        return self.__repr__()

    def __lt__(self, other: SemanticHypothesis) -> bool:
        return self.score < other.score

@dataclass
class SyntacticHypothesis:
    """ 
    Contains all the data necessary to continue the generation of a sequence.
 
    :param aggregation_key: Aggregation key of the hypothesis. The aggregation key
        is a composite key used to group syntactic hypotheses from the same previous
        semantic hypothesis. It is constructed as follows:
        `f"{semantic_source_hypothesis_idx}-{semantic_data.unique_key}"`
    :type aggregation_key: str
    :param semantic_source_hypothesis_idx: Index of the semantic hypothesis that
        was used to generate the syntactic hypothesis.
    :type semantic_source_hypothesis_idx: int
    :param syntactic_source_hypothesis_idx: Index of the syntactic hypothesis that
        was used to generate the syntactic hypothesis.
    :type syntactic_source_hypothesis_idx: int
    :param hypothesis_idx: Index of the hypothesis. This is the index of the hypothesis at 
        the current generation step. It is used to identify the hypothesis in the aggregation of
        the next step. Should be updated as soon as order of hypotheses changes.
    :type hypothesis_idx: int
    :param path_score: Score of the path. The path score is the sum of the scores of the
        syntactic hypotheses that make up the path (sum of log probabilities which equals 
        multiplication of probabilities).
    :type path_score: torch.tensor
    :param semantic_data: Data that ties the syntactic hypothesis to a semantic hypothesis.
        The semantic data contains the unique key which is part of the composite key used
        to group hypotheses. See `aggregation_key` for more information.
    :type semantic_data: SemanticData
    :param syntactic_hypothesis: Data necessary to continue the generation of the sequence.
    :type syntactic_hypothesis: SyntacticHypothesisContinuationData
    :param metadata: Metadata of the syntactic hypothesis.
    :type metadata: SyntacticHypothesisMetaData
    :param is_aggregation_key_complete: Flag to indicate if the aggregation key is complete.
        The aggregation key is complete if both the source_hypothesis_idx and the semantic_data
        are set. This flag is checked when grouping hypotheses.
    :type is_aggregation_key_complete: bool, defaults to False
    :param is_normalized_path_score_calculated: Flag to indicate if the normalized path score
    :type is_normalized_path_score_calculated: bool, defaults to False
    """
    aggregation_key: str
    semantic_source_hypothesis_idx: int
    syntactic_source_hypothesis_idx: int
    hypothesis_idx: int
    path_score: torch.Tensor
    normalized_path_score: torch.Tensor
    semantic_data: SemanticData
    syntactic_hypothesis: SyntacticHypothesisContinuationData
    metadata: SyntacticHypothesisMetaData
    is_aggregation_key_complete: bool = False
    is_normalized_path_score_calculated: bool = False

    def __len__(self) -> int:
        return self.syntactic_hypothesis.sequences.shape[-1]

    def __eq__(self, other: SyntacticHypothesis) -> bool:
        return torch.equal(self.syntactic_hypothesis.sequences, other.syntactic_hypothesis.sequences)

    def __hash__(self) -> int:
        return hash(tuple(self.syntactic_hypothesis.sequences.flatten()))

    def __str__(self) -> str:
        return f"SyntacticHypothesis({self.aggregation_key}, semantic_source_hypothesis_idx={self.semantic_source_hypothesis_idx}, path_score[normalized]={self.path_score}[{self.normalized_path_score}], syntactic_hypothesis={len(self.syntactic_hypothesis)}, metadata={self.metadata}, is_aggr_key_complete={self.is_aggregation_key_complete}, is_norm_path_score_calced={self.is_normalized_path_score_calculated})"

@dataclass
class SemanticData:
    """ 
    Contains data which ties sytactic hypotheses to a semantic hypothesis.

    :param unique_key: Unique key of the semantic hypothesis. This key is used
        to identify the semantic hypothesis.
    :type unique_key: str
    :param start: Start index of the entity in the decoded sequence.
    :type start: int
    :param end: End index of the entity in the decoded sequence.
    :type end: int
    :param _type: Type of the semantic data (f.e. entity type).
    :type _type: str
    :param amount_of_chunks: Amount of chunks the semantic data was merged from.
    :type amount_of_chunks: Optional[int]
    :param other: Other data that is relevant for the semantic data. Can be 
        used to store additional information or comments.
    :type other: Optional[any]
    """
    unique_key: str
    start: int
    end: int
    _type: str
    amount_of_chunks: Optional[int]
    other: Optional[any]
    has_semantic_data: bool = True

@dataclass
class SyntacticHypothesisData(ABC):
    """ 
    Contains all the sliced data necessary to continue the generation of a sequence.

    :param sequences: Sequence of token ids of shape (, sequnce_length)
    :type sequences: torch.Tensor
    :param transition_scores: Transition scores of the tokens at generation steps. 
        The transition_scores are not of the same shape as the scores, instead only
        the scores of the hypothesis itself are kept. The shape is therefore
        (, sequence_length).
    :type transition_scores: torch.Tensor
    :param last_beam_scores: Scores of the last beam. Can also be calculated from
        the transition_scores. The sum of the transition_scores of a beam correspond
        to the `last_beam_scores`.
    :type last_beam_scores: torch.Tensor
    :param past_key_values: Past key values for the model. The past key values contain
        values for the previously generated content. The structure
        as follow:
        - layer of the transformer
        - tuple of key and value tensors
        - tensor of shape (
            1, # since only kept for this hypothesis
            num_heads,
            sequence_length,
            head_dim
        )
    :type past_key_values: Tuple[Tuple[torch.Tensor, torch.Tensor], ...]
    :param attention_mask: Attention mask for the hypothesis.
    :type attention_mask: torch.Tensor
    """
    sequences: torch.Tensor
    transition_scores: torch.Tensor
    last_beam_scores: torch.Tensor
    past_key_values: Tuple[Tuple[torch.Tensor, torch.Tensor], ...]
    attention_mask: torch.Tensor

    def __repr__(self) -> str:
        pkv_len_0 = len(self.past_key_values)
        pkv_len_1 = len(self.past_key_values[0])
        pkv_shape = self.past_key_values[0][0].shape
        return f"ContinuationData(sequences={self.sequences}, transition_scores={self.transition_scores}, last_beam_scores={self.last_beam_scores}, past_key_values=(Shape [{pkv_len_0}, {pkv_len_1}, {pkv_shape}, attention_mask={self.attention_mask})"
 
    def __str__(self) -> str:
        return self.__repr__()

    def __len__(self) -> int:
        """ 
        The length of the sequences tensor.
        """
        return self.sequences.shape[-1]
    
@dataclass
class SyntacticHypothesisContinuationData(SyntacticHypothesisData):
    unshortened_data: Optional[SyntacticHypothesisUnshortenedContinuationData]

    def __repr__(self):
        # Call the superclass's __repr__ method and include the new attribute
        base_repr = super().__repr__()
        return f"{base_repr[:-1]}, unshortened_data={'Available' if self.unshortened_data is not None else 'None'})"

class SyntacticHypothesisUnshortenedContinuationData(SyntacticHypothesisData):
    pass    
    
@dataclass
class SyntacticHypothesisMetaData:
    tokens_shortened: int

# legacy dataclasses
@dataclass
class ContinuationData:
    """ 
    Contains all the data necessary to continue the generation of a sequence.
    The data is sliced to only contain the data necessary for a hypothesis.
    The only exception is the `original_data` field, which contains the original
    data in raw format (as output by the model) and is optional, as it is highly
    unefficient to store.
 
    :param sequences: Sequence of token ids of shape (, sequnce_length)
    :type sequences: torch.Tensor
    :param transition_scores: Transition scores of the tokens at generation steps. 
        The transition_scores are not of the same shape as the scores, instead only
        the scores of the hypothesis itself are kept. The shape is therefore
        (, sequence_length).
    :type transition_scores: torch.Tensor
    :param last_beam_scores: Scores of the last beam. Can also be calculated from
        the transition_scores. The sum of the transition_scores of a beam correspond
        to the `last_beam_scores`.
    :type last_beam_scores: torch.Tensor
    :param past_key_values: Past key values for the model. The past key values contain
        values for the previously generated content. The structure
        as follow:
        - layer of the transformer
        - tuple of key and value tensors
        - tensor of shape (
            1, # since only kept for this hypothesis
            num_heads,
            sequence_length,
            head_dim
        )
    :type past_key_values: Tuple[Tuple[torch.Tensor, torch.Tensor], ...]
    :param attention_mask: Attention mask for the hypothesis.
    :type attention_mask: torch.Tensor
    :param original_data: Original data of the continuation. This data is in raw format
        (as output by the model) and optional, as it is highly unefficient to store.
    :type original_data: Optional[OriginalContinuationData]
    """
    sequences: torch.Tensor
    transition_scores: torch.Tensor
    last_beam_scores: torch.Tensor
    past_key_values: Tuple[Tuple[torch.Tensor, torch.Tensor], ...]
    attention_mask: torch.Tensor
    original_data: Optional[OriginalContinuationData]

    def __repr__(self) -> str:
        pkv_len_0 = len(self.past_key_values)
        pkv_len_1 = len(self.past_key_values[0])
        pkv_shape = self.past_key_values[0][0].shape
        return f"ContinuationData(sequences={self.sequences}, transition_scores={self.transition_scores}, last_beam_scores={self.last_beam_scores}, past_key_values=(Shape [{pkv_len_0}, {pkv_len_1}, {pkv_shape}, attention_mask={self.attention_mask}, original_data={'Available' if self.original_data is not None else 'None'})"
    
    def __str__(self) -> str:
        return self.__repr__()

    def __len__(self) -> int:
        """ 
        The length of the sequences tensor.
        """
        return len(self.sequences.shape[-1])
    
@dataclass
class OriginalContinuationData:
    """ 
    This class contains all the data in raw format (as output by the model).
    
    :param sequences: Sequence of token ids
    :type sequences: torch.Tensor
    :param scores: Scores of the tokens at generation steps. # of tuples is 
        equal to the number of tokens generated. The tensor itself is of shape
        (batch_size, vocab_size).
    :type scores: Tuple[torch.Tensor]
    :param transition_scores: Transition scores of the tokens at generation steps.
    :type transition_scores: Tuple[torch.Tensor]
    :param beam_indices: Indices of the beams that generated the tokens.
    :type beam_indices: torch.Tensor
    :param past_key_values: Past key values for the model. The past key values contain
        values for the previously generated content. The structure
        as follow:
        - layer of the transformer
        - tuple of key and value tensors
        - tensor of shape (
            batch_size,
            num_heads,
            sequence_length,
            head_dim
        )
    :type past_key_values: Tuple[Tuple[torch.Tensor, torch.Tensor], ...]
    :param attention_mask: Attention mask for the model.
    :type attention_mask: torch.Tensor
    :param last_beam_scores: Scores of the last beam. Can also be calculated from
            the scores, sequences and beam indices by using 
            `model.compute_transition_scores`. The sum of the
            transition_scores of a beam correspond to the `last_beam_scores`.
    
    """
    sequences: torch.Tensor
    scores: Tuple[torch.Tensor]
    transition_scores: Tuple[torch.Tensor]
    beam_indices: torch.Tensor
    past_key_values: Tuple[Tuple[torch.Tensor, torch.Tensor], ...]
    attention_mask: torch.Tensor
    last_beam_scores: torch.Tensor

    def __repr__(self) -> str:
        return f"OriginalContinuationData(sequences={self.sequences}, scores={self.scores}, transition_scores={self.transition_scores}, beam_indices={self.beam_indices}, past_key_values=<ommited_for_readability>, attention_mask={self.attention_mask}, last_beam_scores={self.last_beam_scores})"

    def __str__(self) -> str:
        return self.__repr__()
