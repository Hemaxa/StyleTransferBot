import torch
import torchvision.transforms as transforms
from PIL import Image
from models.gan_definitions import Generator
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
MODEL_WEIGHTS_PATH = "weights/monet_generator.pth"
IMG_SIZE = 256

gan_model = Generator().to(DEVICE)
gan_model.load_state_dict(torch.load(MODEL_WEIGHTS_PATH, map_location=DEVICE))
gan_model.eval()

def run_gan_transfer(content_img_path: str, output_img_path: str) -> str:
    transform = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
    ])
    
    image = Image.open(content_img_path).convert('RGB')
    input_tensor = transform(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        output_tensor = gan_model(input_tensor)

    output_tensor = (output_tensor.squeeze(0) * 0.5) + 0.5
    output_image = transforms.ToPILImage()(output_tensor.cpu().clamp_(0, 1))
    output_image.save(output_img_path)
    
    return output_img_path