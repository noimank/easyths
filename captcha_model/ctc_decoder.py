"""
CTC decoding utilities for captcha recognition.

This module provides:
- Greedy decoding
- Beam search decoding with log-space computation for numerical stability
"""

import math
from typing import Dict, List, Tuple
import numpy as np


def greedy_decode(
    probs: np.ndarray,
    blank: int = 0,
) -> List[int]:
    """
    Greedy CTC decoding for a single sequence.

    Args:
        probs: Probability matrix (seq_len, num_classes).
        blank: Blank token index.

    Returns:
        Decoded sequence of character indices.
    """
    # Get best path
    best_path = np.argmax(probs, axis=1)

    # Remove consecutive duplicates
    collapsed = []
    prev = None
    for token in best_path:
        if token != prev:
            collapsed.append(token)
            prev = token

    # Remove blanks (blank=0, characters are 1 to charset_size)
    decoded = [t for t in collapsed if t != blank]

    return decoded


def beam_search_decode(
    probs: np.ndarray,
    blank: int = 0,
    beam_width: int = 10,
) -> List[int]:
    """
    Beam search CTC decoding for a single sequence.

    Uses log-space computation for numerical stability with long sequences.

    Args:
        probs: Probability matrix (seq_len, num_classes).
        blank: Blank token index.
        beam_width: Beam width for search.

    Returns:
        Decoded sequence of character indices.
    """
    seq_len, num_classes = probs.shape

    # Convert to log space for numerical stability
    log_probs = np.log(probs + 1e-10)  # Add small epsilon to avoid log(0)

    # Initialize beam with empty sequence
    # beam: dict mapping (prefix) -> (log_prob_blank, log_prob_non_blank)
    # log_prob_blank: log probability of prefix ending with blank
    # log_prob_non_blank: log probability of prefix ending with non-blank
    NEG_INF = float('-inf')
    beam: Dict[Tuple, Tuple[float, float]] = {(): (0.0, NEG_INF)}

    for t in range(seq_len):
        new_beam: Dict[Tuple, Tuple[float, float]] = {}

        for prefix, (lp_blank, lp_non_blank) in beam.items():
            # Log probability of emitting blank at this timestep
            lp_b = log_probs[t, blank]

            # Case 1: Extend with blank (no change to prefix)
            # New log prob ending with blank = log(exp(lp_blank) + exp(lp_non_blank)) + lp_b
            new_lp_blank = _logsumexp(lp_blank, lp_non_blank) + lp_b
            if prefix in new_beam:
                old_lp_blank, old_lp_non_blank = new_beam[prefix]
                new_beam[prefix] = (_logsumexp(old_lp_blank, new_lp_blank), old_lp_non_blank)
            else:
                new_beam[prefix] = (new_lp_blank, NEG_INF)

            # Case 2: Extend with each non-blank token
            for c in range(num_classes):
                if c == blank:
                    continue

                lp_c = log_probs[t, c]
                char_idx = c

                # Create new prefix
                if len(prefix) > 0 and prefix[-1] == char_idx:
                    # Same as last char - can only extend if preceded by blank
                    new_prefix = prefix + (char_idx,)
                    new_lp_non_blank = lp_blank + lp_c
                else:
                    # Different char - can extend from both
                    new_prefix = prefix + (char_idx,)
                    new_lp_non_blank = _logsumexp(lp_blank, lp_non_blank) + lp_c

                if new_prefix in new_beam:
                    old_lp_blank, old_lp_non_blank = new_beam[new_prefix]
                    new_beam[new_prefix] = (old_lp_blank, _logsumexp(old_lp_non_blank, new_lp_non_blank))
                else:
                    new_beam[new_prefix] = (NEG_INF, new_lp_non_blank)

        # Prune beam - keep top beam_width entries by total log probability
        sorted_beam = sorted(
            new_beam.items(),
            key=lambda x: _logsumexp(x[1][0], x[1][1]),
            reverse=True,
        )[:beam_width]

        beam = {k: v for k, v in sorted_beam}

    # Get best sequence
    best_prefix = max(beam.keys(), key=lambda x: _logsumexp(beam[x][0], beam[x][1]))
    return list(best_prefix)


def _logsumexp(a: float, b: float) -> float:
    """
    Numerically stable log(exp(a) + exp(b)).

    Uses the identity: log(exp(a) + exp(b)) = max(a, b) + log(1 + exp(-|a - b|))
    """
    if a == float('-inf'):
        return b
    if b == float('-inf'):
        return a

    max_val = max(a, b)
    return max_val + math.log(1.0 + math.exp(min(a, b) - max_val))


def beam_search_decode_batch(
    probs: np.ndarray,
    blank: int = 0,
    beam_width: int = 10,
) -> List[List[int]]:
    """
    Beam search CTC decoding for a batch of sequences.

    Args:
        probs: Probability matrix (batch_size, seq_len, num_classes).
        blank: Blank token index.
        beam_width: Beam width for search.

    Returns:
        List of decoded sequences.
    """
    results = []
    for i in range(probs.shape[0]):
        decoded = beam_search_decode(probs[i], blank, beam_width)
        results.append(decoded)
    return results


def greedy_decode_batch(
    probs: np.ndarray,
    blank: int = 0,
) -> List[List[int]]:
    """
    Greedy CTC decoding for a batch of sequences.

    Args:
        probs: Probability matrix (batch_size, seq_len, num_classes).
        blank: Blank token index.

    Returns:
        List of decoded sequences.
    """
    results = []
    for i in range(probs.shape[0]):
        decoded = greedy_decode(probs[i], blank)
        results.append(decoded)
    return results
