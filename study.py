#! /usr/bin/env python
# coding=utf-8

# /************************************************************************************
# ***
# ***    File Author: Dell, 2018年 08月 19日 星期日 20:38:18 CST
# ***
# ************************************************************************************/

import random
import numpy as np

import coco
import utils
import utils
import config

dataset = coco.CocoDataset()
dataset.load_coco("data", "minival", year=2014)

# Prepares the Dataset class
dataset.prepare()

print("Image Count: {}".format(len(dataset.image_ids)))
print("Class Count: {}".format(dataset.num_classes))
# for i, info in enumerate(dataset.class_info):
#     print("{:3}. {:50}".format(i, info['name']))

# image_ids = np.random.choice(dataset.image_ids, 4)
# for image_id in image_ids:
#     image = dataset.load_image(image_id)
#     mask, class_ids = dataset.load_mask(image_id)
#     utils.display_top_masks(image, mask, class_ids, dataset.class_names)

# image_id = random.choice(dataset.image_ids)
image_id = dataset.image_ids[1]

image = dataset.load_image(image_id)
mask, class_ids = dataset.load_mask(image_id)
# Compute Bounding box
bbox = utils.extract_bboxes(mask)

# Display image and additional stats
# print("image_id ", image_id, dataset.image_reference(image_id))
# print("image", image)
# print("mask", mask)
# print("class_ids", class_ids)
# print("bbox", bbox)
# # Display image and instances
# utils.display_instances(image, bbox, mask, class_ids, dataset.class_names)

config = config.Config()

original_shape = image.shape
# Resize
image, window, scale, padding = utils.resize_image(
    image,
    min_dim=config.IMAGE_MIN_DIM,
    max_dim=config.IMAGE_MAX_DIM,
    padding=config.IMAGE_PADDING)
mask = utils.resize_mask(mask, scale, padding)
# Compute Bounding box
bbox = utils.extract_bboxes(mask)
print("image_id: ", image_id, dataset.image_reference(image_id))
print("Original shape: ", original_shape)
# print("image_id ", image_id, dataset.image_reference(image_id))
# print("image", image)
# print("mask", mask)
# print("class_ids", class_ids)
# print("bbox", bbox)
# Display image and instances
utils.display_instances(image, bbox, mask, class_ids, dataset.class_names)