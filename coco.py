"""
Mask R-CNN
Configurations and data loading code for MS COCO.

Copyright (c) 2017 Matterport, Inc.
Licensed under the MIT License (see LICENSE for details)
Written by Waleed Abdulla

------------------------------------------------------------

Usage: import the module (see Jupyter notebooks for examples), or run from
       the command line as such:

    # Train a new model starting from pre-trained COCO weights
    python3 coco.py train --dataset=/path/to/coco/ --model=coco

    # Train a new model starting from ImageNet weights
    python3 coco.py train --dataset=/path/to/coco/ --model=imagenet

    # Continue training a model that you had trained earlier
    python3 coco.py train --dataset=/path/to/coco/ --model=/path/to/weights.h5

    # Continue training the last model you trained
    python3 coco.py train --dataset=/path/to/coco/ --model=last

    # Run COCO evaluatoin on the last model you trained
    python3 coco.py evaluate --dataset=/path/to/coco/ --model=last
"""

import os
import time
import numpy as np
import pdb

# Download and install the Python COCO tools from https://github.com/waleedka/coco
# That's a fork from the original https://github.com/pdollar/coco with a bug
# fix for Python 3.
# I submitted a pull request https://github.com/cocodataset/cocoapi/pull/50
# If the PR is merged then use the original repo.
# Note: Edit PythonAPI/Makefile and replace "python" with "python3".
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from pycocotools import mask as maskUtils

from config import Config
import utils
import model as modellib

# import pdb

# Root directory of the project
ROOT_DIR = os.getcwd()

# Path to trained weights file
COCO_MODEL_PATH = os.path.join(ROOT_DIR, "models/mask_rcnn_coco.pth")

# Directory to save logs and model checkpoints, if not provided
# through the command line argument --logs
DEFAULT_LOGS_DIR = os.path.join(ROOT_DIR, "logs")
DEFAULT_DATASET_YEAR = "2014"

############################################################
#  Configurations
############################################################


class CocoConfig(Config):
    """Configuration for training on MS COCO.
    Derives from the base Config class and overrides values specific
    to the COCO dataset.
    """
    # Give the configuration a recognizable name
    NAME = "coco"

    # We use one GPU with 8GB memory, which can fit one image.
    # Adjust down if you use a smaller GPU.
    IMAGES_PER_GPU = 1

    # Uncomment to train on 8 GPUs (default is 1)
    # GPU_COUNT = 8

    # Number of classes (including background)
    NUM_CLASSES = 1 + 80  # COCO has 80 classes


############################################################
#  Dataset
############################################################


class CocoDataset(utils.Dataset):
    def load_coco(self,
                  dataset_dir,
                  subset,
                  year=DEFAULT_DATASET_YEAR,
                  class_ids=None,
                  class_map=None,
                  return_coco=False):
        """Load a subset of the COCO dataset.
        dataset_dir: The root directory of the COCO dataset.
        subset: What to load (train, val, minival, valminusminival)
        year: What dataset year to load (2014, 2017) as a string, not an integer
        class_ids: If provided, only loads images that have the given classes.
        class_map: TODO: Not implemented yet. Supports maping classes from
            different datasets to the same class ID.
        return_coco: If True, returns the COCO object.
        """

        coco = COCO("{}/annotations/instances_{}{}.json".format(
            dataset_dir, subset, year))
        if subset == "minival" or subset == "valminusminival":
            subset = "val"
        image_dir = "{}/{}{}".format(dataset_dir, subset, year)

        # (Pdb) p image_dir
        # 'data/val2014'

        # pdb.set_trace()
        # class_ids = None
        # Load all classes or a subset?
        if not class_ids:
            # All classes
            class_ids = sorted(coco.getCatIds())

        # All images or a subset?
        if class_ids:
            image_ids = []
            for id in class_ids:
                image_ids.extend(list(coco.getImgIds(catIds=[id])))
            # Remove duplicates
            image_ids = list(set(image_ids))
        else:
            # All images
            image_ids = list(coco.imgs.keys())

        # Add classes
        for i in class_ids:
            self.add_class("coco", i, coco.loadCats(i)[0]["name"])

        # Add images
        for i in image_ids:
            self.add_image(
                "coco",
                image_id=i,
                path=os.path.join(image_dir, coco.imgs[i]['file_name']),
                width=coco.imgs[i]["width"],
                height=coco.imgs[i]["height"],
                annotations=coco.loadAnns(
                    coco.getAnnIds(imgIds=[i], catIds=class_ids,
                                   iscrowd=None)))
            # print(os.path.join(image_dir, coco.imgs[i]['file_name']), class_ids)

        # (Pdb) p class_ids
        # [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20,
        # 21, 22, 23, 24, 25, 27, 28, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
        # 41, 42, 43, 44, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61,
        # 62, 63, 64, 65, 67, 70, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81,
        # 82, 84, 85, 86, 87, 88, 89, 90]

        if return_coco:
            return coco

    def load_mask(self, image_id):
        """Load instance masks for the given image.

        Different datasets use different ways to store masks. This
        function converts the different mask format to one format
        in the form of a bitmap [height, width, instances].

        Returns:
        masks: A bool array of shape [height, width, instance count] with
            one mask per instance.
        class_ids: a 1D array of class IDs of the instance masks.
        """
        # If not a COCO image, delegate to parent class.
        image_info = self.image_info[image_id]
        if image_info["source"] != "coco":
            return super(CocoDataset, self).load_mask(image_id)

        instance_masks = []
        class_ids = []
        annotations = self.image_info[image_id]["annotations"]
        # Build mask of shape [height, width, instance_count] and list
        # of class IDs that correspond to each channel of the mask.
        # pdb.set_trace()

        for annotation in annotations:
            class_id = self.map_source_class_id("coco.{}".format(
                annotation['category_id']))
            if class_id:
                m = self.annToMask(annotation, image_info["height"],
                                   image_info["width"])
                # Some objects are so small that they're less than 1 pixel area
                # and end up rounded out. Skip those objects.
                if m.max() < 1:
                    continue
                # Is it a crowd? If so, use a negative class ID.
                if annotation['iscrowd']:
                    # Use negative class ID for crowds
                    class_id *= -1
                    # For crowd masks, annToMask() sometimes returns a mask
                    # smaller than the given dimensions. If so, resize it.
                    if m.shape[0] != image_info["height"] or m.shape[
                            1] != image_info["width"]:
                        m = np.ones(
                            [image_info["height"], image_info["width"]],
                            dtype=bool)
                instance_masks.append(m)
                class_ids.append(class_id)

        # Pack instance masks into an array
        if class_ids:
            mask = np.stack(instance_masks, axis=2)
            class_ids = np.array(class_ids, dtype=np.int32)

            # (Pdb) class_ids.shape, class_ids
            # ((11,), array([63, 63, 63, 63, 64, 74, 40, 63, 67, 67, 67], dtype=int32))
            # (Pdb)  type(mask), mask.shape
            # (<class 'numpy.ndarray'>, (349, 500, 11))

            return mask, class_ids
        else:
            # Call super class to return an empty mask
            return super(CocoDataset, self).load_mask(image_id)

    def image_reference(self, image_id):
        """Return a link to the image in the COCO Website."""
        info = self.image_info[image_id]
        if info["source"] == "coco":
            return "http://cocodataset.org/#explore?id={}".format(info["id"])
        else:
            super(CocoDataset, self).image_reference(image_id)

    # The following two functions are from pycocotools with a few changes.

    def annToRLE(self, ann, height, width):
        """
        Convert annotation which can be polygons, uncompressed RLE to RLE.
        :return: binary mask (numpy 2D array)
        """
        segm = ann['segmentation']
        if isinstance(segm, list):
            # polygon -- a single object might consist of multiple parts
            # we merge all parts into one mask rle code
            rles = maskUtils.frPyObjects(segm, height, width)
            rle = maskUtils.merge(rles)
        elif isinstance(segm['counts'], list):
            # uncompressed RLE
            rle = maskUtils.frPyObjects(segm, height, width)
        else:
            # rle
            rle = ann['segmentation']
        return rle

    def annToMask(self, ann, height, width):
        """
        Convert annotation which can be polygons, uncompressed RLE, or RLE to binary mask.
        return: binary mask (numpy 2D array)
        """
        rle = self.annToRLE(ann, height, width)
        m = maskUtils.decode(rle)
        return m


############################################################
#  COCO Evaluation
############################################################
def build_coco_results(dataset, image_ids, rois, class_ids, scores, masks):
    """Arrange resutls to match COCO specs in http://cocodataset.org/#format
    """
    # If no results, return an empty list
    if rois is None:
        return []

    results = []
    for image_id in image_ids:
        # Loop through detections
        for i in range(rois.shape[0]):
            class_id = class_ids[i]
            score = scores[i]
            bbox = np.around(rois[i], 1)
            mask = masks[:, :, i]

            result = {
                "image_id": image_id,
                "category_id": dataset.get_source_class_id(class_id, "coco"),
                "bbox":
                [bbox[1], bbox[0], bbox[3] - bbox[1], bbox[2] - bbox[0]],
                "score": score,
                "segmentation": maskUtils.encode(np.asfortranarray(mask))
            }
            results.append(result)
    return results


def evaluate_coco(model,
                  dataset,
                  coco,
                  eval_type="bbox",
                  limit=0,
                  image_ids=None):
    """Runs official COCO evaluation.
    dataset: A Dataset object with valiadtion data
    eval_type: "bbox" or "segm" for bounding box or segmentation evaluation
    limit: if not 0, it's the number of images to use for evaluation
    """
    # Pick COCO images from the dataset
    image_ids = image_ids or dataset.image_ids

    # Limit to a subset
    if limit:
        image_ids = image_ids[:limit]

    # Get corresponding COCO image IDs.
    coco_image_ids = [dataset.image_info[id]["id"] for id in image_ids]

    t_prediction = 0
    t_start = time.time()

    # pdb.set_trace()

    results = []
    for i, image_id in enumerate(image_ids):
        if i % 10 == 0:
            print("Evaluating ", eval_type, " ", i + 1, " ... ")
        # Load image
        image = dataset.load_image(image_id)

        # Run detection
        t = time.time()
        r = model.detect([image])[0]
        t_prediction += (time.time() - t)

        # Convert results to COCO format
        image_results = build_coco_results(dataset, coco_image_ids[i:i + 1],
                                           r["rois"], r["class_ids"],
                                           r["scores"], r["masks"])
        # pdb.set_trace()
        results.extend(image_results)

    # Load results. This modifies results with additional attributes.
    coco_results = coco.loadRes(results)

    # Evaluate
    cocoEval = COCOeval(coco, coco_results, eval_type)
    cocoEval.params.imgIds = coco_image_ids
    cocoEval.evaluate()
    cocoEval.accumulate()
    cocoEval.summarize()

    print("Prediction time: {}. Average {}/image".format(
        t_prediction, t_prediction / len(image_ids)))
    print("Total time: ", time.time() - t_start)


############################################################
#  Training
############################################################

if __name__ == '__main__':
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Train Mask R-CNN on MS COCO.')
    parser.add_argument(
        "command",
        metavar="<command>",
        help="'train' or 'evaluate' on MS COCO")
    parser.add_argument(
        '--dataset',
        required=True,
        metavar="/path/to/coco/",
        help='Directory of the MS-COCO dataset')
    parser.add_argument(
        '--year',
        required=False,
        default=DEFAULT_DATASET_YEAR,
        metavar="<year>",
        help='Year of the MS-COCO dataset (2014 or 2017) (default=2014)')
    parser.add_argument(
        '--model',
        required=False,
        metavar="/path/to/weights.pth",
        help="Path to weights .pth file or 'coco'")
    parser.add_argument(
        '--logs',
        required=False,
        default=DEFAULT_LOGS_DIR,
        metavar="/path/to/logs/",
        help='Logs and checkpoints directory (default=logs/)')
    parser.add_argument(
        '--limit',
        required=False,
        default=500,
        metavar="<image count>",
        help='Images to use for evaluation (default=500)')
    args = parser.parse_args()
    print("Command: ", args.command)
    print("Model: ", args.model)
    print("Dataset: ", args.dataset)
    print("Year: ", args.year)
    print("Logs: ", args.logs)

    # Configurations
    if args.command == "train":
        config = CocoConfig()
    else:

        class InferenceConfig(CocoConfig):
            # Set batch size to 1 since we'll be running inference on
            # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
            GPU_COUNT = 1
            IMAGES_PER_GPU = 1
            DETECTION_MIN_CONFIDENCE = 0

        config = InferenceConfig()
    config.display()

    # Create model
    if args.command == "train":
        model = modellib.MaskRCNN(config=config, model_dir=args.logs)
    else:
        model = modellib.MaskRCNN(config=config, model_dir=args.logs)
    if config.GPU_COUNT:
        model = model.cuda()

    # Select weights file to load
    if args.model:
        if args.model.lower() == "coco":
            model_path = COCO_MODEL_PATH
        elif args.model.lower() == "imagenet":
            # Start from ImageNet trained weights
            model_path = config.IMAGENET_MODEL_PATH
        else:
            model_path = args.model
    else:
        model_path = ""

    # Load weights
    print("Loading weights ", model_path)
    model.load_weights(model_path)

    # Train or evaluate
    if args.command == "train":
        # Training dataset. Use the training set and 35K from the
        # validation set, as as in the Mask RCNN paper.
        dataset_train = CocoDataset()

        dataset_train.load_coco(args.dataset, "train", year=args.year)

        # dataset_train.load_coco(
        #     args.dataset, "valminusminival", year=args.year)
        dataset_train.prepare()

        # Validation dataset
        dataset_val = CocoDataset()
        dataset_val.load_coco(args.dataset, "minival", year=args.year)
        dataset_val.prepare()

        # *** This training schedule is an example. Update to your needs ***

        # Training - Stage 1
        # model.train_model(
        #     dataset_train,
        #     dataset_val,
        #     learning_rate=config.LEARNING_RATE,
        #     epochs=40,
        #     layers='heads')

        # # Training - Stage 2
        # # Finetune layers from ResNet stage 4 and up
        # model.train_model(
        #     dataset_train,
        #     dataset_val,
        #     learning_rate=config.LEARNING_RATE,
        #     epochs=120,
        #     layers='4+')

        # Training - Stage 3
        # Fine tune all layers
        model.train_model(
            dataset_train,
            dataset_val,
            learning_rate=config.LEARNING_RATE / 10,
            epochs=160,
            layers='all')

    elif args.command == "evaluate":
        # Validation dataset
        dataset_val = CocoDataset()
        coco = dataset_val.load_coco(
            args.dataset, "minival", year=args.year, return_coco=True)
        dataset_val.prepare()
        print("Running COCO evaluation on {} images.".format(args.limit))
        evaluate_coco(model, dataset_val, coco, "bbox", limit=int(args.limit))
        evaluate_coco(model, dataset_val, coco, "segm", limit=int(args.limit))
    else:
        print("'{}' is not recognized. "
              "Use 'train' or 'evaluate'".format(args.command))
