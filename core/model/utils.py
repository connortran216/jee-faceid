import os
import pickle
import time
import zlib
import ftplib
import cv2
from PIL import Image
import numpy
from glob import glob
from tqdm import tqdm

# from dpsutil.log import info_log
# from dpsutil.compression import compress_ndarray, decompress_ndarray


def pil2cv(image):
    return cv2.cvtColor(numpy.asarray(image, dtype="uint8"), cv2.COLOR_RGB2BGR)


def cv2pil(img_arr):
    return Image.fromarray(cv2.cvtColor(img_arr, cv2.COLOR_BGR2RGB))


def read_video(file_path=None):
    if not check_file_exist(file_path=file_path):
        raise Exception("Not found images file")

    return cv2.VideoCapture(file_path)


def read_image(file_path=None):
    if not check_file_exist(file_path=file_path):
        raise Exception("Not found images file")

    return cv2.imread(file_path)


def write_image(image, file_path):
    assert type(file_path) is str, "file_path must be string but got %s" % type(file_path)
    assert type(image) is numpy.ndarray, "file_path must be string but got %s" % type(image)

    if os.path.isfile(file_path):
        info_log.info("File existed! Do you want to over-write!? Y/n")

        if not (input().lower() or 'y') == 'y':
            return

    elif "/" in file_path.split('.')[-1]:
        if not os.path.isdir(file_path):
            os.mkdir(file_path)
        file_path = os.path.join(file_path, "%.0f.png" % time.time())

    cv2.imwrite(file_path, image, [cv2.IMWRITE_PNG_COMPRESSION, 0])


def read_from_folder(folder_path=None):
    folder_path = os.path.abspath(folder_path)
    if not check_folder_exist(folder_path):
        raise Exception("Not found folder!")

    for image_path in tqdm(glob(os.path.join(folder_path, "**/*.jpg"))):
        parent_folder = os.path.dirname(image_path)
        name_file = os.path.basename(image_path)
        yield parent_folder, name_file, cv2.imread(image_path)


def draw_label(img, label, pos, color=(0, 0, 255), scale=1, thickness=1):
    return cv2.putText(img, label, pos, cv2.FONT_HERSHEY_DUPLEX, scale, color, thickness=thickness)


def draw_square(img, pos, color=(0, 255, 0)):
    cv2.rectangle(img, pos[0:2], pos[2:4], color, 2)


def imdecode(buffer: bytes, flags=1) -> numpy.ndarray:
    return cv2.imdecode(numpy.frombuffer(decompress_ndarray(buffer), dtype=numpy.uint8), flags)


def imencode(image: numpy.ndarray) -> bytes:
    ret, encode_data = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert ret
    return compress_ndarray(encode_data)


def crop_image(img, size=(0, 0, 0, 0), margin_size=0):
    if not img.any():
        raise Exception("Image is not existed!")

    (max_height, max_width, _) = img.shape
    (x, y, w, h) = size
    if margin_size:
        w = w + 2 * margin_size if x + w + 2 * margin_size < max_width else w
        h = h + 2 * margin_size if y + h + 2 * margin_size < max_width else h
        x = x - margin_size if x - margin_size > 0 else x
        y = y - margin_size if y - margin_size > 0 else y

    x = int(round(x))
    y = int(round(y))
    h = int(round(h))
    w = int(round(w))
    return img[y: y + h, x:x + w]


def resize_image(image=None, size=None):
    """
    :param image: numpy.ndarray
    :param size: (width, height)
    :return: new image
    """
    assert type(size[0]) is int and type(size[1]) is int, "Size must be int"
    assert type(image) is numpy.ndarray,\
        "Type of face features must been {}. But got {}".format(numpy.ndarray, type(image))
    _, new_height = size
    h, w, _ = image.shape

    if h == new_height:
        return image

    scale = new_height / h
    dim = int(w * scale), new_height

    return cv2.resize(image, dim, interpolation=cv2.INTER_NEAREST)


def poly2box(polygon):
    x, y, w, h = cv2.boundingRect(polygon)
    return x, y, x+w, y+h


def check_file_exist(file_path):
    return os.path.isfile(file_path)


def check_folder_exist(folder_path):
    return os.path.isdir(folder_path)


def show_image(winname, image, wait=True):
    cv2.namedWindow(winname, cv2.WINDOW_NORMAL)
    cv2.imshow(winname, image)
    cv2.resizeWindow(winname, 1600, 900)
    if wait:
        cv2.waitKey(0)


def destroyWindows():
    cv2.destroyAllWindows()


def euclidean_distance(a, b):
    assert type(a) is numpy.ndarray or type(b) is numpy.ndarray
    return numpy.linalg.norm(a - b)


def compress(a):
    return zlib.compress(pickle.dumps(a))


def decompress(compressed):
    return pickle.loads(zlib.decompress(compressed))


def upload_ftp(host, port, user, password, file_path, saved_name):
    """
    Upload file into server
    @param host:
    @param port:
    @param user:
    @param password:
    @param file_path:
    @param saved_name:
    @return:
    """
    with ftplib.FTP() as session:
        session.connect(host, port)
        session.login(user, password)
        with open(file_path, 'rb') as file:
            # send the file
            session.storbinary("STOR " + saved_name, file)


def download_ftp(host, port, user, password, file_path, saved_name="temp"):
    """
    Download file from server
    @param host:
    @param port:
    @param user:
    @param password:
    @param file_path: path + name from server
    @param saved_name: local path + name
    """
    info_log.info("Download => {}".format(file_path))
    with ftplib.FTP() as session:
        session.connect(host, port)
        session.login(user, password)
        with open(saved_name, 'wb') as f:
            session.retrbinary('RETR ' + file_path, f.write)


def get_binary_ftp(host, port, user, password, file_path, saved_name="temp", delete=True):
    """
    Get binary string of the file from server
    @param host:
    @param port:
    @param user:
    @param password:
    @param file_path:
    @param saved_name:
    @param delete: delete file after download
    @return:
    """
    download_ftp(host, port, user, password, file_path, saved_name)
    with open(saved_name, 'rb') as file:
        file_data = file.read()
        if delete:
            os.remove(saved_name)

    return file_data


def delete_file(file_path):
    os.remove(file_path)


def list_files_ftp(host, port, user, password, path=''):
    """
    Get binary string of the file from server
    @param host:
    @param port:
    @param user:
    @param password:
    @param path:
    @return:
    """
    with ftplib.FTP() as session:
        session.connect(host, port)
        session.login(user, password)
        session.cwd(os.path.join(f"/ftp/{user}", path))
        contents = session.nlst()

    return contents