import os
import json
import torch
import bentoml

from bentoml.adapters import ImageInput
from bentoml.artifact import PytorchModelArtifact

from core.model.utils import euclidean_distance, download_ftp, delete_file
from core.model.face_align_trans import warp_and_crop_face

# os.environ['CUDA_VISIBLE_DEVICES'] = '1'


class FTPServerConfig:
    def __init__(self):
        # if use ftp
        self.use_model_from_ftp = json.loads(os.environ.get("USE_MODEL_FROM_FTP", "False").lower())
        self.ftp_host = os.environ.get("FTP_SERVER_HOST", "127.0.0.1")
        self.ftp_port = int(os.environ.get("FTP_SERVER_PORT", 22))
        self.ftp_user = os.environ.get("FTP_SERVER_USER", "dps")
        self.ftp_password = os.environ.get("FTP_SERVER_PASSWORD", "123456")


class ConfigFaceDetector(FTPServerConfig):
    """
    Config of FaceDetector(RetinaFace)
    """

    def __init__(self):
        super().__init__()
        import torch
        from core.model.retinaface import RetinaFace
        from core.model.model import cfg_mnet
        from core.model.model import MobileNetV1

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # config of MobileNetV1
        self.model_backbone = MobileNetV1
        self.model_config = cfg_mnet
        self.model_backbone_path = "static/retina_backbone.tar"
        self.model = RetinaFace(self.model_backbone, self.model_config, self.device,
                                backbone_path=self.model_backbone_path)
        self.model_path = "static/retina_mobilenet.pth"

        # config of Resnet50
        # self.model_backbone = models.resnet50
        # self.model_config = cfg_re50
        # self.model = RetinaFace(self.model_backbone, self.model_config, self.device)
        # self.model_path = "./data/pretrained_model/retina_res50.pth"

        self.threshold = float(os.environ.get('DETECTOR_THRESHOLD', 0.97531))
        self.face_size = (112, 112)
        self.eyes_distance = float(os.environ.get('EYES_DISTANCE', 12))  # pixels
        self.central_points_face_distances = float(os.environ.get('CENTRAL_POINTS_FACE_DISTANCES', 12))  # pixels


class FaceDetector:
    def __init__(self):
        self.__config = ConfigFaceDetector()
        self.__detector = self.__config.model

        if not self.__config.use_model_from_ftp:
            self.__detector.load_model(self.__config.model_path)
        else:
            # load model from ftp server
            # first, download model
            download_ftp(
                file_path=self.__config.model_path,
                host=self.__config.ftp_host,
                port=self.__config.ftp_port,
                user=self.__config.ftp_user,
                password=self.__config.ftp_password
            )
            self.__detector.load_model("tmp")  # modify this line + delete
            delete_file("tmp")

        from core.model.face_align_trans import get_reference_facial_points
        self.__reference = get_reference_facial_points(default_square=True)

    def forward(self, image):
        result = []
        for face_detail in self.__detector.detect(image, self.__config.threshold):
            border = [idx for idx, pos in enumerate(face_detail[:4]) if pos > 5000 or pos < 0]

            if len(border) > 0:
                continue

            box = tuple(face_detail[:4])
            land_mask = face_detail[5:].reshape((5, 2))

            noise_line = euclidean_distance((land_mask[0] + land_mask[1])/2, (land_mask[3] + land_mask[4])/2)
            eyes_line = euclidean_distance(land_mask[1], land_mask[0])

            # if noise_line < self.__config.central_points_face_distances or eyes_line < self.__config.eyes_distance\
            #         or eyes_line/noise_line <= 0.8 or eyes_line/noise_line >= 0.98:
            if noise_line < self.__config.central_points_face_distances or eyes_line < self.__config.eyes_distance:
                continue

            result.append((land_mask, box))

        return result

    def warp_crop_face(self, image, land_mask, output_size=None):
        if output_size is None:
            output_size = self.__config.face_size

        return warp_and_crop_face(image, land_mask, self.__reference, output_size)


net = FaceDetector()
