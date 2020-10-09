import os
import importlib
import random
import yaml
from collections import defaultdict

import cv2
import numpy as np
import tensorflow as tf
from tensorpack import imgaug

from loader.augs import (BinarizeLabel, GaussianBlur, GenInstanceDistance,
                         GenInstanceHV, MedianBlur, GenInstanceUnetMap,
                         GenInstanceContourMap,
                         eqRGB2HED, eqHistCV, pipeHEDAugment, linearAugmentation)
####
class Config(object):
    def __init__(self, ):
        # Select template (hv_kumar, hv_uit_w_kumar, hv_consep, hv_cmp17)
        self.model_config = os.environ['H_PROFILE'] if 'H_PROFILE' in os.environ else ''
        
        # Load config yml file
        data_config = defaultdict(lambda: None, yaml.load(open('config.yml'), Loader=yaml.FullLoader)[self.model_config])
        self.log_path = data_config['output_prefix'] # log root path

        assert (data_config['input_prefix'] is not None)
        assert (data_config['output_prefix'] is not None)

        # data extraion params
        self.data_dir_root = os.path.join(data_config['input_prefix'], data_config['data_dir']) # without modes
        
        self.extract_type = data_config['extract_type']
        self.data_modes = data_config['data_modes']
        self.win_size = data_config['win_size']
        self.step_size = data_config['step_size']
        self.img_ext = '.png' if data_config['img_ext'] is None else data_config['img_ext']

        for step in ['preproc', 'extract', 'train', 'infer', 'export', 'process']:
            exec(f"self.out_{step}_root = os.path.join(data_config['output_prefix'], '{step}')")
        #self.out_preproc_root = os.path.join(data_config['output_prefix'], 'preprocess')
        #self.out_extract_root = os.path.join(data_config['output_prefix'], 'extract')

        self.img_dirs = {k: v for k, v in zip(self.data_modes, [os.path.join(self.data_dir_root, mode, 'Images') 
                for mode in self.data_modes])}
        self.labels_dirs = {k: v for k, v in zip(self.data_modes, [os.path.join(self.data_dir_root, mode, 'Labels') 
                for mode in self.data_modes])}

        # normalized images
        self.out_preproc = None
        if data_config['include_preproc']:
            self.out_preproc = {k: v for k, v in zip(self.data_modes, [os.path.join(self.out_preproc_root, self.model_config, mode, 'Images') 
                    for mode in self.data_modes])}
        
        if data_config['stain_norm'] is not None:
            # self.target_norm = f"{self._data_dir}/{self.data_modes[0]}/'Images'/{data_config['stain_norm']['target']}{self.img_ext}"
            self.norm_target = os.path.join(self.data_dir_root, data_config['stain_norm']['mode'], 'Images', f"{data_config['stain_norm']['image']}{self.img_ext}")
            self.norm_brightness = data_config['stain_norm']['norm_brightness']
        elif data_config['histtk'] is not None:
            self.norm_histtk = True
        
        normalized = (data_config['include_preproc']) and (data_config['stain_norm'] is not None)
        win_code = '{}_{}x{}_{}x{}{}'.format(self.model_config, self.win_size[0], self.win_size[1], self.step_size[0], self.step_size[1], '_stain_norm' if normalized else '')
        self.out_extract = {k: v for k, v in zip(self.data_modes, [os.path.join(self.out_extract_root, win_code, mode, 'Annotations') 
            for mode in self.data_modes])}

        # init model params
        self.seed = data_config['seed']
        mode = data_config['mode']
        self.model_type = data_config['model_type']
        self.type_classification = data_config['type_classification']

        # Some semantic segmentation network like micronet, nr_types will replace nr_classes if type_classification=True
        self.nr_classes = 2 # Nuclei Pixels vs Background
        
        self.nuclei_type_dict = data_config['nuclei_types']
        self.nr_types = len(self.nuclei_type_dict.values()) + 1

        #### Dynamically setting the config file into variable
        if mode == 'hover':
            config_file = importlib.import_module('opt.hover') # np_hv, np_dist
        else:
            config_file = importlib.import_module('opt.other') # fcn8, dcan, etc.
        config_dict = config_file.__getattribute__(self.model_type)

        for variable, value in config_dict.items():
            self.__setattr__(variable, value)
        #### Training data

        # patches are stored as numpy arrays with N channels
        # ordering as [Image][Nuclei Pixels][Nuclei Type][Additional Map]
        # Ex: with type_classification=True
        #     HoVer-Net: RGB - Nuclei Pixels - Type Map - Horizontal and Vertical Map
        # Ex: with type_classification=False
        #     Dist     : RGB - Nuclei Pixels - Distance Map
        data_code_dict = {
            'unet'     : '536x536_84x84',
            'dist'     : '536x536_84x84',
            'fcn8'     : '512x512_256x256',
            'dcan'     : '512x512_256x256',
            'segnet'   : '512x512_256x256',
            'micronet' : '504x504_252x252',
            'np_hv'    : '540x540_80x80',
            'np_dist'  : '540x540_80x80',
        }

        self.color_palete = {
        'Background': [255.0, 0.0, 0.0],    # red
        'Neoplastic': [255.0, 255.0, 0.0],  # bright yellow
        'Inflammatory': [0.0, 255.0, 0.0],  # bright green
        'Connective': [0.0, 255.0, 170.0],  # emerald       # Soft tissue cells
        'Epithelial': [0.0, 0.0, 255.0],    # dark blue
        'Dead cells': [255.0, 0.0, 170.0],  # pink
        'Spindle': [0.0, 170.0, 255.0],     # light blue
        'Misc': [255.0, 170.0, 0.0],        # orange
        'light green': [170.0, 255.0, 0.0], # light green
        'purple': [170.0, 0.0, 255.0],      # purple
        'cyan': [0.0, 170.0, 255.0]        # cyan
        }

        # self.model_name = f"{self.model_config}-{self.model_type}-{data_config['input_augs']}-{data_config['exp_id']}"
        self.model_name = f"{self.model_config}-{data_config['input_augs']}-{data_config['exp_id']}"

        self.data_ext = '.npy' if data_config['data_ext'] is None else data_config['data_ext']
        # list of directories containing validation patches

        # self.train_dir = data_config['train_dir']
        # self.valid_dir = data_config['valid_dir']
        if data_config['include_extract']:
            self.train_dir = [os.path.join(self.out_extract_root, win_code, x) for x in data_config['train_dir']]
            self.valid_dir = [os.path.join(self.out_extract_root, win_code, x) for x in data_config['valid_dir']]
        else:
            self.train_dir = [os.path.join(self.data_dir_root, x) for x in data_config['train_dir']]
            self.valid_dir = [os.path.join(self.data_dir_root, x) for x in data_config['valid_dir']]


        # nr of processes for parallel processing input
        self.nr_procs_train = 8 if data_config['nr_procs_train'] is None else data_config['nr_procs_train']
        self.nr_procs_valid = 4 if data_config['nr_procs_valid'] is None else data_config['nr_procs_valid']

        self.input_norm = data_config['input_norm'] # normalize RGB to 0-1 range

        #self.save_dir = os.path.join(data_config['output_prefix'], 'train', self.model_name)
        self.save_dir = os.path.join(self.out_train_root, self.model_name)

        #### Info for running inference
        self.inf_auto_find_chkpt = data_config['inf_auto_find_chkpt']
        # path to checkpoints will be used for inference, replace accordingly
        self.inf_model_path = os.path.join(data_config['input_prefix'], data_config['inf_model_path'])
        #self.save_dir + '/model-19640.index'

        # output will have channel ordering as [Nuclei Type][Nuclei Pixels][Additional]
        # where [Nuclei Type] will be used for getting the type of each instance
        # while [Nuclei Pixels][Additional] will be used for extracting instances

        # TODO: encode the file extension for each folder?
        # list of [[root_dir1, codeX, subdirA, subdirB], [root_dir2, codeY, subdirC, subdirD] etc.]
        # code is used together with 'inf_output_dir' to make output dir for each set
        self.inf_imgs_ext = '.png' if data_config['inf_imgs_ext'] is None else data_config['inf_imgs_ext']

        # rootdir, outputdirname, subdir1, subdir2(opt) ...
        self.inf_data_list = [os.path.join(data_config['input_prefix'], x) for x in data_config['inf_data_list']]
        self.inf_output_dir = os.path.join(self.out_infer_root, self.model_name)
        self.model_export_dir = os.path.join(self.out_export_root, self.model_name)
        self.remap_labels = data_config['remap_labels']
        self.outline = data_config['outline']
        
        # For inference during evalutaion mode i.e run by inferer.py
        self.eval_inf_input_tensor_names = ['images']
        self.eval_inf_output_tensor_names = ['predmap-coded']
        # For inference during training mode i.e run by trainer.py
        self.train_inf_output_tensor_names = ['predmap-coded', 'truemap-coded']

        assert data_config['input_augs'] != '' or data_config['input_augs'] is not None

        #### Policies
        
        p_standard = [
            imgaug.RandomApplyAug(
                imgaug.RandomChooseAug([
                    GaussianBlur(),
                    MedianBlur(),
                    imgaug.GaussianNoise(),
                ]), 0.5
            ),
            imgaug.RandomOrderAug([
                imgaug.Hue((-8, 8), rgb=True), 
                imgaug.Saturation(0.2, rgb=True),
                imgaug.Brightness(26, clip=True),  
                imgaug.Contrast((0.75, 1.25), clip=True),
                ]),
            imgaug.ToUint8(),
        ]

        p_hed_random = [
            imgaug.RandomApplyAug(
                imgaug.RandomChooseAug([
                    GaussianBlur(),
                    MedianBlur(),
                    imgaug.GaussianNoise(),
                    #
                    imgaug.ColorSpace(cv2.COLOR_RGB2HSV),
                    imgaug.ColorSpace(cv2.COLOR_HSV2RGB),
                    #
                    eqRGB2HED(),
                ]), 0.5
            ),
            # standard color augmentation
            imgaug.RandomOrderAug([
                imgaug.Hue((-8, 8), rgb=True), 
                imgaug.Saturation(0.2, rgb=True),
                imgaug.Brightness(26, clip=True),  
                imgaug.Contrast((0.75, 1.25), clip=True),
                ]),
            imgaug.ToUint8(),
        ]

        p_linear = [
            linearAugmentation(),
            imgaug.RandomApplyAug(
                imgaug.RandomChooseAug([
                    GaussianBlur(),
                    MedianBlur(),
                    imgaug.GaussianNoise(),
                ]), 0.5
            ),
            imgaug.RandomOrderAug([
                imgaug.Hue((-8, 8), rgb=True), 
                imgaug.Saturation(0.2, rgb=True),
                imgaug.Brightness(26, clip=True),  
                imgaug.Contrast((0.75, 1.25), clip=True),
                ]),
            imgaug.ToUint8(),
        ]

        policies = {'p_standard': p_standard, 'p_hed_random': p_hed_random, 'p_linear': p_linear}
        self.input_augs = policies[(data_config['input_augs'])]
        ####

    def get_model(self):
        if self.model_type == 'np_hv':
            model_constructor = importlib.import_module('model.graph')
            model_constructor = model_constructor.Model_NP_HV
        elif self.model_type == 'np_hv_opt':
            model_constructor = importlib.import_module('model.hover_opt')
            model_constructor = model_constructor.Model_NP_HV_OPT
        elif self.model_type == 'np_dist':
            model_constructor = importlib.import_module('model.graph')
            model_constructor = model_constructor.Model_NP_DIST
        else:
            model_constructor = importlib.import_module(f'model.{self.model_type}')
            model_constructor = model_constructor.Graph
        return model_constructor # NOTE return alias, not object

    # refer to https://tensorpack.readthedocs.io/modules/dataflow.imgaug.html for
    # information on how to modify the augmentation parameters
    def get_train_augmentors(self, input_shape, output_shape, view=False):
        shape_augs = [
            imgaug.Affine(
                        shear=5, # in degree
                        scale=(0.8, 1.2),
                        rotate_max_deg=179,
                        translate_frac=(0.01, 0.01),
                        interp=cv2.INTER_NEAREST,
                        border=cv2.BORDER_CONSTANT),
            imgaug.Flip(vert=True),
            imgaug.Flip(horiz=True),
            imgaug.CenterCrop(input_shape),
        ]

        input_augs = self.input_augs

        label_augs = []
        if self.model_type == 'unet' or self.model_type == 'micronet':
            label_augs =[GenInstanceUnetMap(crop_shape=output_shape)]
        if self.model_type == 'dcan':
            label_augs =[GenInstanceContourMap(crop_shape=output_shape)]
        if self.model_type == 'dist':
            label_augs = [GenInstanceDistance(crop_shape=output_shape, inst_norm=False)]
        if self.model_type == 'np_hv' or self.model_type == 'np_hv_opt':
            label_augs = [GenInstanceHV(crop_shape=output_shape)]
        if self.model_type == 'np_dist':
            label_augs = [GenInstanceDistance(crop_shape=output_shape, inst_norm=True)]

        if not self.type_classification:
            label_augs.append(BinarizeLabel())

        if not view:
            label_augs.append(imgaug.CenterCrop(output_shape))

        return shape_augs, input_augs, label_augs

    def get_valid_augmentors(self, input_shape, output_shape, view=False):
        shape_augs = [
            imgaug.CenterCrop(input_shape),
        ]

        input_augs = None

        label_augs = []
        if self.model_type == 'unet' or self.model_type == 'micronet':
            label_augs =[GenInstanceUnetMap(crop_shape=output_shape)]
        if self.model_type == 'dcan':
            label_augs =[GenInstanceContourMap(crop_shape=output_shape)]
        if self.model_type == 'dist':
            label_augs = [GenInstanceDistance(crop_shape=output_shape, inst_norm=False)]
        if self.model_type == 'np_hv' or self.model_type == 'np_hv_opt':
            label_augs = [GenInstanceHV(crop_shape=output_shape)]
        if self.model_type == 'np_dist':
            label_augs = [GenInstanceDistance(crop_shape=output_shape, inst_norm=True)]
        label_augs.append(BinarizeLabel())

        if not view:
            label_augs.append(imgaug.CenterCrop(output_shape))

        return shape_augs, input_augs, label_augs
