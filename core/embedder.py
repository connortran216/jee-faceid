import os
import torch
from torchvision import transforms
from core.model.irse import iresnet100

# os.environ['CUDA_VISIBLE_DEVICES'] = '1'


class FaceEmbedder:
    def __init__(
        self,
        model_path=os.environ.get('EMBEDDER_MODEL_PATH', 'static/...'),
        backbone=os.environ.get('EMBEDDER_BACKBONE', 'IR_50'),
        face_size=(112, 112),
        device=os.environ.get('COMPUTE_ENGINE_BACKEND', 'cuda')
    ):
        super(FaceEmbedder, self).__init__()
        self.embedder = iresnet100(pretrained=True)
        if device == 'cuda':
            self.device = 'cuda'
            self.embedder.cuda()
        else:
            self.device = 'cpu'

        self.embedder.eval()

        self.mean = [0.5] * 3
        self.std = [0.5 * 256 / 255] * 3
        self.process = transforms.Compose([
            transforms.Resize((128, 128)),
            transforms.CenterCrop((112, 112)),
            transforms.ToTensor(),
            transforms.Normalize(self.mean, self.std)
        ])

    def get_features(self, face):
        tensor = self.process(face)

        if self.device == 'cuda':
            tensor = tensor.cuda()

        with torch.no_grad():
            features = self.embedder(tensor.unsqueeze(0))

        if self.device == 'cuda':
            features = features.cpu().detach().numpy()

        return features
