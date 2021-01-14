# --------------------------------------------------------
# Fast R-CNN
# Copyright (c) 2015 Microsoft
# Licensed under The MIT License [see LICENSE for details]
# Written by Ross Girshick
# --------------------------------------------------------

"""Factory method for easily getting imdbs by name."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

__sets = {}
from lib.datasets.pascal_voc import pascal_voc
from lib.datasets.coco import coco


for year in ['2007', '2012']:
  for split in ['train', 'val', 'trainval', 'test']:
    name = 'voc_{}_{}'.format(year, split)
    __sets[name] = {"image_set": split,
                    "year": year,
                    } # (lambda split=split, year=year: pascal_voc(split, year, root_path=None))

# Set up coco_2017_<split>

for year in ['2017']:
  for split in ['train', 'val']:
    name = 'coco_{}_{}'.format(year, split)
    __sets[name] = (lambda split=split, year=year: coco(split, year))

# Set up vg_<split>
# for version in ['1600-400-20']:
#     for split in ['minitrain', 'train', 'minival', 'val', 'test']:
#         name = 'vg_{}_{}'.format(version,split)
#         __sets[name] = (lambda split=split, version=version: vg(version, split))
#
# for version in ['150-50-20', '150-50-50', '500-150-80', '750-250-150', '1750-700-450', '1600-400-20']:
#     for split in ['minitrain', 'smalltrain', 'train', 'minival', 'smallval', 'val', 'test']:
#         name = 'vg_{}_{}'.format(version,split)
#         __sets[name] = (lambda split=split, version=version: vg(version, split))
#
# # set up image net.
# for split in ['train', 'val', 'val1', 'val2', 'test']:
#     name = 'imagenet_{}'.format(split)
#     devkit_path = 'data/imagenet/ILSVRC/devkit'
#     data_path = 'data/imagenet/ILSVRC'
#     __sets[name] = (lambda split=split, devkit_path=devkit_path, data_path=data_path: imagenet(split,devkit_path,data_path))

def get_imdb(name, root_path=None):
  """Get an imdb (image database) by name."""
  # if name not in __sets:
  #   raise KeyError('Unknown dataset: {}'.format(name))
  return  pascal_voc(**__sets[name], root_path=root_path)


def list_imdbs():
  """List all registered imdbs."""
  return list(__sets.keys())
