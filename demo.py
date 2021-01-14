# --------------------------------------------------------
# Tensorflow Faster R-CNN
# Licensed under The MIT License [see LICENSE for details]
# Written by Lichao Wang, Jianwei Yang, based on code from Ross Girshick, Jiasen Lu, Jianwei Yang
# --------------------------------------------------------
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import _init_paths
import os
import sys
import numpy as np
import argparse
import pprint
import pdb
import time
import cv2
import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.optim as optim
import glob

import torchvision.transforms as transforms
import torchvision.datasets as dset
from cv2 import imread
from utils import Timer

from lib.model.utils.config import cfg, cfg_from_file, cfg_from_list, get_output_dir
from lib.model.rpn.bbox_transform import clip_boxes
from torchvision.ops import nms
from lib.model.rpn.bbox_transform import bbox_transform_inv
from lib.model.utils.net_utils import save_net, load_net, vis_detections
from lib.model.utils.blob import im_list_to_blob

from lib.model.faster_rcnn.Snet import snet
from utils import  color_list
import pdb
from utils import MkdirSimple

try:
    xrange  # Python 2
except NameError:
    xrange = range  # Python 3


def parse_args():
    """
  Parse input arguments
  """
    parser = argparse.ArgumentParser(description='Train a Fast R-CNN network')
    parser.add_argument('--dataset',
                        dest='dataset',
                        help='training dataset',
                        default='pascal_voc',
                        type=str)
    parser.add_argument('--cfg',
                        dest='cfg_file',
                        help='optional config file',
                        default='cfgs/snet.yml',
                        type=str)
    parser.add_argument('--net',
                        dest='net',
                        help='vgg16, res50, res101, res152',
                        default='res101',
                        type=str)
    parser.add_argument('--set',
                        dest='set_cfgs',
                        help='set config keys',
                        default=None,
                        nargs=argparse.REMAINDER)
    parser.add_argument('--load_dir',
                        dest='load_dir',
                        help='directory to load models',
                        default="./models")
    parser.add_argument('--image_dir',
                        dest='image_dir',
                        help='directory to load images for demo',
                        default="images")
    parser.add_argument('--output_dir',
                        dest='output_dir',)
    parser.add_argument('--cuda',
                        dest='cuda',
                        help='whether use CUDA',
                        action='store_true')
    parser.add_argument('--mGPUs',
                        dest='mGPUs',
                        help='whether use multiple GPUs',
                        action='store_true')
    parser.add_argument('--cag',
                        dest='class_agnostic',
                        help='whether perform class_agnostic bbox regression',
                        action='store_true')
    parser.add_argument(
        '--parallel_type',
        dest='parallel_type',
        help=
        'which part of model to parallel, 0: all, 1: model before roi pooling',
        default=0,
        type=int)

    parser.add_argument('--checkepoch',
                        dest='checkepoch',
                        help='checkepoch to load network',
                        default=1,
                        type=int)

    parser.add_argument('--bs',
                        dest='batch_size',
                        help='batch_size',
                        default=1,
                        type=int)
    parser.add_argument('--vis',
                        dest='vis',
                        help='visualization mode',
                        action='store_true')
    parser.add_argument('--webcam_num',
                        dest='webcam_num',
                        help='webcam ID number',
                        default=-1,
                        type=int)



    args = parser.parse_args()
    return args


lr = cfg.TRAIN.LEARNING_RATE
momentum = cfg.TRAIN.MOMENTUM
weight_decay = cfg.TRAIN.WEIGHT_DECAY


def _get_image_blob(im):
    """Converts an image into a network input.
  Arguments:
    im (ndarray): a color image in BGR order
  Returns:
    blob (ndarray): a data blob holding an image pyramid
    im_scale_factors (list): list of image scales (relative to im) used
      in the image pyramid
  """
    im_orig = im.astype(np.float32, copy=True)
    im_orig -= cfg.PIXEL_MEANS

    im_shape = im_orig.shape


    processed_ims = []
    im_scale_factors = []

    size = cfg.TEST.SIZE
    im_scale_w = float(size) / float(im_shape[1])
    im_scale_h = float(size) / float(im_shape[0])
    # Prevent the biggest axis from being more than MAX_SIZE

    im = cv2.resize(im_orig,
                    (size,size),
                        interpolation=cv2.INTER_LINEAR)
    im_scale_factors.append(im_scale_w)
    im_scale_factors.append(im_scale_h)
    processed_ims.append(im)

    # Create a blob to hold the input images
    blob = im_list_to_blob(processed_ims)

    return blob, np.array(im_scale_factors)

# @Timer
def forward(im_data_pt, im_info_pt):
    with torch.no_grad():
        im_data.resize_(im_data_pt.size()).copy_(im_data_pt)
        im_info.resize_(im_info_pt.size()).copy_(im_info_pt)
        gt_boxes.resize_(1, 1, 5).zero_()
        num_boxes.resize_(1).zero_()

    with torch.no_grad():
        time_measure, rois, cls_prob, bbox_pred, \
        rpn_loss_cls, rpn_loss_box, \
        RCNN_loss_cls, RCNN_loss_bbox, \
        rois_label = _RCNN(im_data, im_info, gt_boxes, num_boxes)

    scores = cls_prob.data
    boxes = rois.data[:, :, 1:5]

    return scores, boxes, bbox_pred.data, time_measure

if __name__ == '__main__':

    args = parse_args()

    print('Called with args:')
    print(args)

    if args.cfg_file is not None:
        cfg_from_file(args.cfg_file)

    set_cfgs = [
            'ANCHOR_SCALES', '[2, 4 , 8, 16, 32]', 'ANCHOR_RATIOS', '[1.0/2 , 3.0/4 , 1 , 4.0/3 , 2 ]',
            'MAX_NUM_GT_BOXES', '20'
        ]
    cfg_from_list(set_cfgs)

    cfg.USE_GPU_NMS = args.cuda



    print('Using config:')
    pprint.pprint(cfg)
    np.random.seed(cfg.RNG_SEED)

    # train set
    # -- Note: Use validation set and disable the flipped to enable faster loading.

    input_dir = args.load_dir + "/" + args.net + "/" + args.dataset
    if not os.path.exists(input_dir):
        raise Exception(
            'There is no input directory for loading network from ' +
            input_dir)

    load_name = os.path.join(
            input_dir,
            'thundernet_epoch_{}.pth'.format(args.checkepoch,
                                         ))


    device = torch.device("cuda" if args.cuda > 0 else "cpu")

    pascal_classes = np.asarray([
        '__background__',
        'pet-cat', 'pet-dog', 'excrement', 'wire', 'key',
        'weighing-scale', 'shoes', 'socks', 'power-strip', 'base',
    ])

    layer = int(args.net.split("_")[1])
    _RCNN = snet(pascal_classes,layer, pretrained_path= None  , class_agnostic=args.class_agnostic)


    _RCNN.create_architecture()

    print("load checkpoint %s" % (load_name))
    if args.cuda > 0:
        checkpoint = torch.load(load_name)
    else:
        checkpoint = torch.load(load_name,
                                map_location=(lambda storage, loc: storage))
    _RCNN.load_state_dict(checkpoint['model'])
    if 'pooling_mode' in checkpoint.keys():
        cfg.POOLING_MODE = checkpoint['pooling_mode']

    print('load model successfully!')

    # pdb.set_trace()

    print("load checkpoint %s" % (load_name))

    # initilize the tensor holder here.
    im_data = torch.FloatTensor(1)
    im_info = torch.FloatTensor(1)
    num_boxes = torch.LongTensor(1)
    gt_boxes = torch.FloatTensor(1)

    # ship to cuda
    if args.cuda > 0:
        im_data = im_data.cuda()
        im_info = im_info.cuda()
        num_boxes = num_boxes.cuda()
        gt_boxes = gt_boxes.cuda()

    # make variable (PyTorch 0.4.0+)
    with torch.no_grad():
        im_data = Variable(im_data)
        im_info = Variable(im_info)
        num_boxes = Variable(num_boxes)
        gt_boxes = Variable(gt_boxes)

    if args.cuda > 0:
        cfg.CUDA = True

    if args.cuda > 0:
        _RCNN.cuda()

    _RCNN.eval()

    start = time.time()
    max_per_image = 100
    thresh = 0.3
    vis = True

    webcam_num = args.webcam_num
    # Set up webcam or get image directories
    if webcam_num >= 0:
        cap = cv2.VideoCapture(webcam_num)
        num_images = 0
    else:
        imglist = list(map(lambda file: file[len(args.image_dir):].lstrip("/"), glob.glob(args.image_dir+"/*/*[jpg,png]")))
        num_images = len(imglist)

    print('Loaded Photo: {} images.'.format(num_images))

    while (num_images >= 0):
        total_tic = time.time()
        if webcam_num == -1:
            num_images -= 1

        # Get image from the webcam
        if webcam_num >= 0:
            if not cap.isOpened():
                raise RuntimeError(
                    "Webcam could not open. Please check connection.")
            ret, frame = cap.read()
            im_in = np.array(frame)
        # Load the demo image
        else:
            im_file = os.path.join(args.image_dir, imglist[num_images])
            im_in = cv2.imread(im_file)
            # im_in = np.array(imread(im_file))
        if len(im_in.shape) == 2:
            im_in = im_in[:, :, np.newaxis]
            im_in = np.concatenate((im_in, im_in, im_in), axis=2)

        im =  im_in
        blobs, im_scales = _get_image_blob(im)

        im_blob = blobs
        im_info_np = np.array(
            [[im_blob.shape[1], im_blob.shape[2], im_scales[0], im_scales[1]]],
            dtype=np.float32)

        im_data_pt = torch.from_numpy(im_blob)
        im_data_pt = im_data_pt.permute(0, 3, 1, 2)
        im_info_pt = torch.from_numpy(im_info_np)

        det_tic = time.time()
        scores, boxes, box_deltas, time_measure = forward(im_data_pt, im_info_pt)

        if cfg.TEST.BBOX_REG:
            # Apply bounding-box regression deltas
            if cfg.TRAIN.BBOX_NORMALIZE_TARGETS_PRECOMPUTED:
                # Optionally normalize targets by a precomputed mean and stdev
                if args.class_agnostic:
                    if args.cuda > 0:
                        box_deltas = box_deltas.view(-1, 4) * torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_STDS).cuda() \
                                   + torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_MEANS).cuda()
                    else:
                        box_deltas = box_deltas.view(-1, 4) * torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_STDS) \
                                   + torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_MEANS)

                    box_deltas = box_deltas.view(1, -1, 4)
                else:
                    if args.cuda > 0:
                        box_deltas = box_deltas.view(-1, 4) * torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_STDS).cuda() \
                                   + torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_MEANS).cuda()
                    else:
                        box_deltas = box_deltas.view(-1, 4) * torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_STDS) \
                                   + torch.FloatTensor(cfg.TRAIN.BBOX_NORMALIZE_MEANS)
                    box_deltas = box_deltas.view(1, -1,
                                                 4 * len(pascal_classes))

            pred_boxes = bbox_transform_inv(boxes, box_deltas, 1)
            pred_boxes = clip_boxes(pred_boxes, im_info.data, 1)
        else:
            # Simply repeat the boxes, once for each class
            pred_boxes = np.tile(boxes, (1, scores.shape[1]))

        pred_boxes[:, :, 0::2] /= im_scales[0]
        pred_boxes[:, :, 1::2] /= im_scales[1]

        scores = scores.squeeze()
        pred_boxes = pred_boxes.squeeze()
        det_toc = time.time()
        detect_time = det_toc - det_tic
        misc_tic = time.time()
        if vis:
            im2show = np.copy(im)
        for j in xrange(1, len(pascal_classes)):
            inds = torch.nonzero(scores[:, j] > thresh, as_tuple=False).view(-1)
            # if there is det
            if inds.numel() > 0:
                cls_scores = scores[:, j][inds]
                _, order = torch.sort(cls_scores, 0, True)
                if args.class_agnostic:
                    cls_boxes = pred_boxes[inds, :]
                else:
                    cls_boxes = pred_boxes[inds][:, j * 4:(j + 1) * 4]

                cls_dets = torch.cat((cls_boxes, cls_scores.unsqueeze(1)), 1)
                # cls_dets = torch.cat((cls_boxes, cls_scores), 1)
                cls_dets = cls_dets[order]
                # keep = nms(cls_dets, cfg.TEST.NMS, force_cpu=not cfg.USE_GPU_NMS)
                keep = nms(cls_boxes[order, :], cls_scores[order], cfg.TEST.NMS)
                cls_dets = cls_dets[keep.view(-1).long()]
                if vis:
                    vis_detections(im2show, pascal_classes[j],color_list[j].tolist(),
                                             cls_dets.cpu().numpy(), 0.5)

        misc_toc = time.time()
        nms_time = misc_toc - misc_tic

        if webcam_num == -1:
            sys.stdout.write('im_detect: {:03d}/{:03d}\tDetect: {:.3f}s (RPN: {:.3f}s, Pre-RoI: {:.3f}s, RoI: {:.3f}s, Subnet: {:.3f}s)\tNMS: {:.3f}s\r' \
                             .format(num_images + 1, len(imglist), detect_time, time_measure[0], time_measure[1], time_measure[2], time_measure[3], nms_time))
            sys.stdout.flush()

        if vis and webcam_num == -1:
            # cv2.imshow('test', im2show)
            # cv2.waitKey(0)
            result_path = os.path.join(args.output_dir, imglist[num_images])
            MkdirSimple(result_path)
            cv2.imwrite(result_path, im2show)
        else:
            im2showRGB = cv2.cvtColor(im2show, cv2.COLOR_BGR2RGB)
            cv2.imshow("frame", im2showRGB)
            total_toc = time.time()
            total_time = total_toc - total_tic
            frame_rate = 1 / total_time
            print('Frame rate:', frame_rate)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    if webcam_num >= 0:
        cap.release()
        cv2.destroyAllWindows()
