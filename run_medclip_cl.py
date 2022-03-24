import pdb, os
os.environ['CUDA_VISIBLE_DEVICES']='1'
from collections import defaultdict
import requests
import math

from PIL import Image
import torch
import pandas as pd
import numpy as np
from torch.utils.data import Dataset, DataLoader

from medclip.dataset import IUXRayDataset, IUXRayImageTextCollator, IUXRayAbnormalNormalCollator, IUXRayFrontalLateralCollator
from medclip.modeling_clip import MedCLIPModel
from medclip.losses import ImageTextContrastiveLoss, ImageImageContrastiveLoss
from medclip.trainer import Trainer

device = "cuda:0" if torch.cuda.is_available() else "cpu"

train_config = {
    'batch_size': 16,
    'num_epochs': 1,
    'warmup': 0.1, # the first 10% of training steps are used for warm-up
    'lr': 1e-5,
    'weight_decay': 1e-4,
    }
model_save_path = f'./checkpoints/'
if not os.path.exists(model_save_path):
    os.makedirs(model_save_path)

# #########
# define three contrastive loss models
# #########
model = MedCLIPModel()
model = model.to(device)
momentum_model = MedCLIPModel()
momentum_model = momentum_model.to(device)

# image-text pair CL
training_data = IUXRayDataset('./data/IU_XRay')
collate_fn = IUXRayImageTextCollator(img_mean=training_data.img_mean, img_std=training_data.img_std, is_train=True)
dataloader_image_text = DataLoader(training_data, batch_size=train_config['batch_size'], shuffle=True, collate_fn=collate_fn)
train_loss_image_text = ImageTextContrastiveLoss(model)
warmup_steps = math.ceil(len(training_data) * train_config['num_epochs'] * train_config['warmup']) #10% of train data for warm-up

# abnormal-normal pair CL + memory banking (moco V3)
training_data = IUXRayDataset('./data/IU_XRay')
collate_fn = IUXRayAbnormalNormalCollator(img_mean=training_data.img_mean, img_std=training_data.img_std, is_train=True)
dataloader_abnormal = DataLoader(training_data, batch_size=train_config['batch_size'], shuffle=True, collate_fn=collate_fn)
train_loss_abnormal = ImageImageContrastiveLoss(model, momentum_model)

# frontal-lateral paired CL + memory banks (moco V3)
training_data = IUXRayDataset('./data/IU_XRay')
collate_fn = IUXRayFrontalLateralCollator(img_mean=training_data.img_mean, img_std=training_data.img_std, is_train=True)
dataloader_frontal = DataLoader(training_data, batch_size=train_config['batch_size'], shuffle=True, collate_fn=collate_fn)
train_loss_frontal = ImageImageContrastiveLoss(model, momentum_model)

train_objectives = [
    (dataloader_image_text, train_loss_image_text),
    (dataloader_abnormal, train_loss_abnormal),
    (dataloader_frontal, train_loss_frontal),
]

# TODO fix checkpoint save and evaluation in trainer
trainer = Trainer()
trainer.train(
    model,
    train_objectives=train_objectives,
    warmup_steps=warmup_steps,
    epochs=train_config['num_epochs'],
    optimizer_params={'lr':train_config['lr']},
    output_path=model_save_path,
    checkpoint_path=model_save_path,
    checkpoint_save_steps=1000,
    weight_decay=train_config['weight_decay'],
    use_amp=True,
    )
print('done')


