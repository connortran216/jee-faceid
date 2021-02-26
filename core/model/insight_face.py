import os
import torch

from core.model.irse import IR_50, IR_SE_152, IR_SE_101, IR_SE_50, IR_152, IR_101

MODELS = {
    "IR_50": IR_50,
    "IR_SE_50": IR_SE_50,
    "IR_152": IR_152,
    "IR_SE_152": IR_SE_152,
    "IR_101": IR_101,
    "IR_SE_101": IR_SE_101
}

IR_50 = "IR_50"
IR_SE_50 = "IR_SE_50"
IR_152 = "IR_152"
IR_SE_152 = "IR_SE_152"
IR_101 = "IR_101"
IR_SE_101 = "IR_SE_101"


class InsightFace(object):
    def __init__(self, backbone=IR_50, face_size=(112, 112)):
        self.backbone = MODELS[backbone](face_size)
        self.output_size = self.backbone.output_layer[-1].num_features

    def load_model(self, pretrained_path, device):
        assert pretrained_path, "Pre-trained model is not found!"

        self.backbone.to(device)

        if os.environ.get('COMPUTE_ENGINE_BACKEND', 'cpu') == 'cpu':
            self.backbone.load_state_dict(torch.load(pretrained_path, map_location=torch.device('cpu')))
        else:
            self.backbone.load_state_dict(torch.load(pretrained_path))
        self.backbone.eval()

    def get_feature(self, face):
        assert isinstance(face, torch.Tensor)
        return self.backbone(face)

    __call__ = get_feature