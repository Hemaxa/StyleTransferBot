import torch
import torchvision.models as models

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

vgg19_config = {
    "name": "VGG-19 (Детальный)",
    "description": "Более сложная модель, лучше передает детали стиля, но работает медленнее.",
    "model": models.vgg19(pretrained=True).features.to(device).eval(),
    "normalization_mean": torch.tensor([0.485, 0.456, 0.406]).to(device),
    "normalization_std": torch.tensor([0.229, 0.224, 0.225]).to(device),
    "content_layers": ['conv_8'],  # conv4_2
    "style_layers": ['conv_1', 'conv_3', 'conv_5', 'conv_9', 'conv_13'],  # conv1_1, conv2_1, conv3_1, conv4_1, conv5_1
}

vgg16_config = {
    "name": "VGG-16 (Быстрый)",
    "description": "Более простая модель, работает быстрее, но может упускать мелкие детали.",
    "model": models.vgg16(pretrained=True).features.to(device).eval(),
    "normalization_mean": torch.tensor([0.485, 0.456, 0.406]).to(device),
    "normalization_std": torch.tensor([0.229, 0.224, 0.225]).to(device),
    "content_layers": ['conv_7'],  # conv4_2
    "style_layers": ['conv_1', 'conv_3', 'conv_5', 'conv_8', 'conv_11'],  # conv1_1, conv2_1, conv3_1, conv4_1, conv5_1
}

MODELS_VGG = {
    "vgg19": vgg19_config,
    "vgg16": vgg16_config,
}

def get_vgg_config(name: str):
    if name not in MODELS_VGG:
        raise ValueError(f"Model {name} not found. Available models: {list(MODELS_VGG.keys())}")
    return MODELS_VGG[name]