# -*- coding: utf-8 -*-
# Copyright (C) 2024 Machine Learning Group of the University of Oldenburg.
# Licensed under the Academic Free License version 3.0

import os, random
import sys
import h5py
import numpy as np
import torch as to
from skimage.metrics import peak_signal_noise_ratio
from typing import Dict, Union
from pesq import pesq
from torchmetrics.audio import ScaleInvariantSignalNoiseRatio


class stdout_logger(object):
    """Redirect print statements both to console and file

    Source: https://stackoverflow.com/a/14906787
    """

    def __init__(self, txt_file):
        self.terminal = sys.stdout
        self.log = open(txt_file, "w")

    def write(self, message):
        self.terminal.write(message)
        self.terminal.flush()
        self.log.write(message)
        self.log.flush()

    def flush(self):
        # this flush method is needed for python 3 compatibility.
        # this handles the flush command by doing nothing.
        # you might want to specify some extra behavior here.
        pass


def set_zero_mask(clean, sr, mask_duration, num_masks):
    """
    Takes the clean audio and randomly zero-masks a segment  
    of length mask_duration, 
    segment size in samples = mask_duration * sr

    :param clean: clean audio file
    :param sr: sampling rate
    :param mask_duration: duration of zero mask in seconds
    :param num_masks: number of zero masks (default = 1)
    """
    masked_audio = clean
    sample_mask_length = int(mask_duration*sr)
    clean_length = len(clean)

    for n in range(num_masks):
        mask_init_index = random.randint(0, clean_length-1-sample_mask_length)
        masked_audio[mask_init_index:mask_init_index+int(sample_mask_length)] = 0
        print('Masked to zero: ' + str(mask_init_index) + ' to ' + str(mask_init_index+int(sample_mask_length)))

    return masked_audio

def store_as_h5(to_store_dict: Dict[str, to.Tensor], output_name: str) -> None:
    """Takes dictionary of tensors and writes to H5 file

    :param to_store_dict: Dictionary of torch Tensors
    :param output_name: Full path of H5 file to write data to
    """
    os.makedirs(os.path.split(output_name)[0], exist_ok=True)
    with h5py.File(output_name, "w") as f:
        for key, val in to_store_dict.items():
            f.create_dataset(
                key, data=val if isinstance(val, float) else val.detach().cpu()
            )
    print(f"Wrote {output_name}")


def eval_fn(
    target: Union[np.ndarray, to.Tensor],
    reco: Union[np.ndarray, to.Tensor],
    data_range: int = None,
    device=None,
) -> to.Tensor:
    """
    Takes the ground truth audio and the reconstruction and outputs 
    the computed PSNR, SNR and SI-SNR measures
    """
    return to.tensor(
        peak_signal_noise_ratio(
            target.detach().cpu().numpy() if isinstance(target, to.Tensor) else target,
            reco.detach().cpu().numpy() if isinstance(reco, to.Tensor) else reco,
            data_range=data_range,
        )), to.tensor(
        compute_snr_metric(
            target.detach().cpu().numpy() if isinstance(target, to.Tensor) else target,
            reco.detach().cpu().numpy() if isinstance(reco, to.Tensor) else reco
        )), to.tensor(
         compute_si_snr_metric(target, reco, device)
        )   

def compute_SNR(ref, est):
        """
        Computing signal-to-noise ratio (SNR) between the reconstucted 
        signal and ground truth (target)
        """
        snr =  np.sum(ref**2) / np.sum((ref-est)**2)  
        snr = 10*np.log10(snr)
        return snr.round(decimals=2)

def compute_snr_metric(clean, reconstructed: to.Tensor) -> int:
        """
        Computing signal-to-noise ratio (SNR) between the reconstucted 
        signal and ground truth (target)
        """
        assert reconstructed.shape == clean.shape
        snr = compute_SNR(clean, np.clip(reconstructed, -1.0, 1.0))
        return snr

def compute_si_snr_metric(clean, reconstructed: to.Tensor, device) -> int:
        """
        Computing signal invariant signal-to-noise ratio (SI-SNR) 
        (Source:https://torchmetrics.readthedocs.io/en/v0.8.2/audio/scale_invariant_signal_noise_ratio.html) 
        between the reconstucted signal and ground truth (target)
        """
        assert reconstructed.shape == clean.shape
        si_snr = ScaleInvariantSignalNoiseRatio().to(device)
        si_snr_value = si_snr(reconstructed, clean)
        return si_snr_value 

def compute_pesq_metric(clean, reconstructed: to.Tensor) -> int:
        """
        Computing PESQ wideband measure (Source: https://github.com/ludlows/PESQ) 
        between the reconstucted signal and ground truth (target)
        """
        assert reconstructed.shape == clean.shape
        reconstructed = reconstructed[0, :]
        clean = clean[0, :]
        pesq_ = pesq(16000, clean, np.clip(reconstructed, -1.0, 1.0), 'wb')
        return pesq_