import os
import torch
import numpy
from core.model.model import py_cpu_nms, decode, decode_landm, PriorBox, RetinaNet


def remove_prefix(state_dict, prefix):
    f = lambda x: x.split(prefix, 1)[-1] if x.startswith(prefix) else x
    return {f(key): value for key, value in state_dict.items()}


class RetinaFace(object):
    def __init__(self, backbone_model, model_config, device, backbone_path=None):
        torch.set_grad_enabled(False)
        self.model = RetinaNet(backbone_model, model_config, backbone_path=backbone_path)
        self.model_config = model_config
        self.device = device
        self.image_size = None
        self.prior_data = None
        self.landmark_scale = None
        self.box_scale = None
        self.priorbox = PriorBox(self.model_config)

    def load_model(self, pretrained_path):
        if os.environ.get('COMPUTE_ENGINE_BACKEND', 'cpu') == 'cpu':
            pretrained_dict = torch.load(pretrained_path, map_location=torch.device('cpu'))
        else:
            pretrained_dict = torch.load(pretrained_path)

#         pretrained_dict = torch.load(pretrained_path)

        if "state_dict" in pretrained_dict.keys():
            pretrained_dict = remove_prefix(pretrained_dict['state_dict'], 'module.')
        else:
            pretrained_dict = remove_prefix(pretrained_dict, 'module.')
        self.model.load_state_dict(pretrained_dict, strict=False)
        self.model.to(self.device)
        self.model.eval()
        print(f'Loaded model with device {self.device}')

    def update_prior(self, image_size):
        if self.image_size == image_size:
            return

        priors = self.priorbox.forward(image_size, self.device)
        self.prior_data = priors.data
        self.image_size = image_size
        self.landmark_scale = torch.Tensor([
            image_size[1], image_size[0], image_size[1], image_size[0],
            image_size[1], image_size[0], image_size[1], image_size[0],
            image_size[1], image_size[0]]
        ).to(self.device)
        self.box_scale = torch.Tensor([image_size[1], image_size[0], image_size[1], image_size[0]]).to(self.device)

    def detect(self, img, threshold, topK=500):
        self.update_prior(img.shape[:2])
        resize = 1
        img = numpy.float32(img)

        img -= (104, 117, 123)
        img = img.transpose(2, 0, 1)  # BGR to RGB
        img = torch.from_numpy(img).unsqueeze(0).to(self.device)
        loc, conf, landms = self.model(img)
        boxes = decode(loc.data.squeeze(0), self.prior_data, self.model_config['variance'])
        boxes = boxes * self.box_scale / resize
        scores = conf.squeeze(0).data[:, 1]

        landms = decode_landm(landms.data.squeeze(0), self.prior_data, self.model_config['variance'])
        landms = landms * self.landmark_scale / resize

        boxes = boxes.cpu().numpy()
        landms = landms.cpu().numpy()
        scores = scores.cpu().numpy()

        # empty gpu cached memory
        torch.cuda.empty_cache()

        # ignore low scores
        inds = scores > threshold
        boxes = boxes[inds]
        landms = landms[inds]
        scores = scores[inds]

        # keep top-K before NMS
        order = scores.argsort()[::-1][:topK]
        boxes = boxes[order]
        landms = landms[order]
        scores = scores[order]

        # do NMS
        dets = numpy.hstack((boxes, scores[:, numpy.newaxis])).astype(numpy.float32, copy=False)
        keep = py_cpu_nms(dets, 0.3)
        dets = dets[keep, :]
        landms = landms[keep]
        # keep top-K faster NMS
        dets = dets[:topK, :]
        landms = landms[:topK, :]
        return numpy.concatenate((dets, landms), axis=1)
