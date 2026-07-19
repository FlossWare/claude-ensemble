#!/usr/bin/env python3
"""PyTorch documentation scraper.

Covers:
  - PyTorch docs/stable (core API, nn, autograd, distributed, etc.)
  - PyTorch tutorials (beginner, intermediate, advanced, recipes)
  - Torchvision, Torchaudio, Torchtext documentation
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class PyTorchScraper(BaseScraper):
    """Scrape PyTorch documentation and tutorials."""

    SOURCES = {
        "getting-started": {
            "pages": {
                "https://pytorch.org/docs/stable/index.html": "PyTorch Documentation",
                "https://pytorch.org/get-started/locally/": "Get Started Locally",
                "https://pytorch.org/get-started/previous-versions/": "Previous Versions",
                "https://pytorch.org/docs/stable/notes/cuda.html": "CUDA Semantics",
                "https://pytorch.org/docs/stable/notes/extending.html": "Extending PyTorch",
                "https://pytorch.org/docs/stable/notes/faq.html": "FAQ",
                "https://pytorch.org/docs/stable/notes/large_scale_deployments.html": "Large Scale Deployments",
                "https://pytorch.org/docs/stable/notes/serialization.html": "Serialization Semantics",
                "https://pytorch.org/docs/stable/notes/windows.html": "Windows FAQ",
                "https://pytorch.org/docs/stable/notes/multiprocessing.html": "Multiprocessing Best Practices",
                "https://pytorch.org/docs/stable/notes/randomness.html": "Reproducibility",
                "https://pytorch.org/docs/stable/notes/broadcasting.html": "Broadcasting Semantics",
                "https://pytorch.org/docs/stable/notes/autograd.html": "Autograd Mechanics",
                "https://pytorch.org/docs/stable/notes/modules.html": "Modules",
                "https://pytorch.org/docs/stable/community/contribution_guide.html": "Contribution Guide",
                "https://pytorch.org/docs/stable/community/governance.html": "PyTorch Governance",
                "https://pytorch.org/docs/stable/notes/numerical_accuracy.html": "Numerical Accuracy",
            },
        },
        "tensors": {
            "pages": {
                "https://pytorch.org/docs/stable/tensors.html": "Torch Tensor",
                "https://pytorch.org/docs/stable/tensor_attributes.html": "Tensor Attributes",
                "https://pytorch.org/docs/stable/tensor_view.html": "Tensor Views",
                "https://pytorch.org/docs/stable/sparse.html": "Sparse Tensors",
                "https://pytorch.org/docs/stable/complex_numbers.html": "Complex Numbers",
                "https://pytorch.org/docs/stable/generated/torch.tensor.html": "torch.tensor",
                "https://pytorch.org/docs/stable/generated/torch.zeros.html": "torch.zeros",
                "https://pytorch.org/docs/stable/generated/torch.ones.html": "torch.ones",
                "https://pytorch.org/docs/stable/generated/torch.arange.html": "torch.arange",
                "https://pytorch.org/docs/stable/generated/torch.linspace.html": "torch.linspace",
                "https://pytorch.org/docs/stable/generated/torch.logspace.html": "torch.logspace",
                "https://pytorch.org/docs/stable/generated/torch.eye.html": "torch.eye",
                "https://pytorch.org/docs/stable/generated/torch.empty.html": "torch.empty",
                "https://pytorch.org/docs/stable/generated/torch.full.html": "torch.full",
                "https://pytorch.org/docs/stable/generated/torch.rand.html": "torch.rand",
                "https://pytorch.org/docs/stable/generated/torch.randn.html": "torch.randn",
                "https://pytorch.org/docs/stable/generated/torch.randint.html": "torch.randint",
                "https://pytorch.org/docs/stable/generated/torch.cat.html": "torch.cat",
                "https://pytorch.org/docs/stable/generated/torch.stack.html": "torch.stack",
                "https://pytorch.org/docs/stable/generated/torch.reshape.html": "torch.reshape",
                "https://pytorch.org/docs/stable/generated/torch.squeeze.html": "torch.squeeze",
                "https://pytorch.org/docs/stable/generated/torch.unsqueeze.html": "torch.unsqueeze",
                "https://pytorch.org/docs/stable/generated/torch.transpose.html": "torch.transpose",
                "https://pytorch.org/docs/stable/generated/torch.permute.html": "torch.permute",
                "https://pytorch.org/docs/stable/generated/torch.chunk.html": "torch.chunk",
                "https://pytorch.org/docs/stable/generated/torch.split.html": "torch.split",
                "https://pytorch.org/docs/stable/generated/torch.index_select.html": "torch.index_select",
                "https://pytorch.org/docs/stable/generated/torch.masked_select.html": "torch.masked_select",
                "https://pytorch.org/docs/stable/generated/torch.where.html": "torch.where",
                "https://pytorch.org/docs/stable/generated/torch.clone.html": "torch.clone",
                "https://pytorch.org/docs/stable/generated/torch.contiguous_format.html": "torch.contiguous_format",
            },
        },
        "autograd": {
            "pages": {
                "https://pytorch.org/docs/stable/autograd.html": "Automatic Differentiation",
                "https://pytorch.org/docs/stable/generated/torch.autograd.backward.html": "torch.autograd.backward",
                "https://pytorch.org/docs/stable/generated/torch.autograd.grad.html": "torch.autograd.grad",
                "https://pytorch.org/docs/stable/generated/torch.autograd.Function.html": "torch.autograd.Function",
                "https://pytorch.org/docs/stable/generated/torch.autograd.functional.jacobian.html": "Jacobian",
                "https://pytorch.org/docs/stable/generated/torch.autograd.functional.hessian.html": "Hessian",
                "https://pytorch.org/docs/stable/generated/torch.autograd.functional.vjp.html": "VJP",
                "https://pytorch.org/docs/stable/generated/torch.autograd.functional.jvp.html": "JVP",
                "https://pytorch.org/docs/stable/generated/torch.autograd.gradcheck.html": "Grad Check",
                "https://pytorch.org/docs/stable/generated/torch.autograd.profiler.profile.html": "Autograd Profiler",
                "https://pytorch.org/docs/stable/generated/torch.no_grad.html": "torch.no_grad",
                "https://pytorch.org/docs/stable/generated/torch.enable_grad.html": "torch.enable_grad",
                "https://pytorch.org/docs/stable/generated/torch.set_grad_enabled.html": "torch.set_grad_enabled",
                "https://pytorch.org/docs/stable/generated/torch.inference_mode.html": "torch.inference_mode",
            },
        },
        "neural-networks": {
            "pages": {
                "https://pytorch.org/docs/stable/nn.html": "torch.nn",
                "https://pytorch.org/docs/stable/nn.functional.html": "torch.nn.functional",
                "https://pytorch.org/docs/stable/generated/torch.nn.Module.html": "nn.Module",
                "https://pytorch.org/docs/stable/generated/torch.nn.Sequential.html": "nn.Sequential",
                "https://pytorch.org/docs/stable/generated/torch.nn.ModuleList.html": "nn.ModuleList",
                "https://pytorch.org/docs/stable/generated/torch.nn.ModuleDict.html": "nn.ModuleDict",
                "https://pytorch.org/docs/stable/generated/torch.nn.Linear.html": "nn.Linear",
                "https://pytorch.org/docs/stable/generated/torch.nn.Conv1d.html": "nn.Conv1d",
                "https://pytorch.org/docs/stable/generated/torch.nn.Conv2d.html": "nn.Conv2d",
                "https://pytorch.org/docs/stable/generated/torch.nn.Conv3d.html": "nn.Conv3d",
                "https://pytorch.org/docs/stable/generated/torch.nn.ConvTranspose2d.html": "nn.ConvTranspose2d",
                "https://pytorch.org/docs/stable/generated/torch.nn.BatchNorm1d.html": "nn.BatchNorm1d",
                "https://pytorch.org/docs/stable/generated/torch.nn.BatchNorm2d.html": "nn.BatchNorm2d",
                "https://pytorch.org/docs/stable/generated/torch.nn.LayerNorm.html": "nn.LayerNorm",
                "https://pytorch.org/docs/stable/generated/torch.nn.GroupNorm.html": "nn.GroupNorm",
                "https://pytorch.org/docs/stable/generated/torch.nn.InstanceNorm2d.html": "nn.InstanceNorm2d",
                "https://pytorch.org/docs/stable/generated/torch.nn.Dropout.html": "nn.Dropout",
                "https://pytorch.org/docs/stable/generated/torch.nn.Dropout2d.html": "nn.Dropout2d",
                "https://pytorch.org/docs/stable/generated/torch.nn.ReLU.html": "nn.ReLU",
                "https://pytorch.org/docs/stable/generated/torch.nn.GELU.html": "nn.GELU",
                "https://pytorch.org/docs/stable/generated/torch.nn.SiLU.html": "nn.SiLU",
                "https://pytorch.org/docs/stable/generated/torch.nn.Sigmoid.html": "nn.Sigmoid",
                "https://pytorch.org/docs/stable/generated/torch.nn.Tanh.html": "nn.Tanh",
                "https://pytorch.org/docs/stable/generated/torch.nn.Softmax.html": "nn.Softmax",
                "https://pytorch.org/docs/stable/generated/torch.nn.LogSoftmax.html": "nn.LogSoftmax",
                "https://pytorch.org/docs/stable/generated/torch.nn.Embedding.html": "nn.Embedding",
                "https://pytorch.org/docs/stable/generated/torch.nn.EmbeddingBag.html": "nn.EmbeddingBag",
                "https://pytorch.org/docs/stable/generated/torch.nn.LSTM.html": "nn.LSTM",
                "https://pytorch.org/docs/stable/generated/torch.nn.GRU.html": "nn.GRU",
                "https://pytorch.org/docs/stable/generated/torch.nn.RNN.html": "nn.RNN",
                "https://pytorch.org/docs/stable/generated/torch.nn.Transformer.html": "nn.Transformer",
                "https://pytorch.org/docs/stable/generated/torch.nn.TransformerEncoder.html": "nn.TransformerEncoder",
                "https://pytorch.org/docs/stable/generated/torch.nn.TransformerDecoder.html": "nn.TransformerDecoder",
                "https://pytorch.org/docs/stable/generated/torch.nn.TransformerEncoderLayer.html": "nn.TransformerEncoderLayer",
                "https://pytorch.org/docs/stable/generated/torch.nn.TransformerDecoderLayer.html": "nn.TransformerDecoderLayer",
                "https://pytorch.org/docs/stable/generated/torch.nn.MultiheadAttention.html": "nn.MultiheadAttention",
                "https://pytorch.org/docs/stable/generated/torch.nn.MaxPool2d.html": "nn.MaxPool2d",
                "https://pytorch.org/docs/stable/generated/torch.nn.AvgPool2d.html": "nn.AvgPool2d",
                "https://pytorch.org/docs/stable/generated/torch.nn.AdaptiveAvgPool2d.html": "nn.AdaptiveAvgPool2d",
                "https://pytorch.org/docs/stable/generated/torch.nn.Flatten.html": "nn.Flatten",
                "https://pytorch.org/docs/stable/generated/torch.nn.Unflatten.html": "nn.Unflatten",
                "https://pytorch.org/docs/stable/generated/torch.nn.CrossEntropyLoss.html": "nn.CrossEntropyLoss",
                "https://pytorch.org/docs/stable/generated/torch.nn.MSELoss.html": "nn.MSELoss",
                "https://pytorch.org/docs/stable/generated/torch.nn.BCELoss.html": "nn.BCELoss",
                "https://pytorch.org/docs/stable/generated/torch.nn.BCEWithLogitsLoss.html": "nn.BCEWithLogitsLoss",
                "https://pytorch.org/docs/stable/generated/torch.nn.NLLLoss.html": "nn.NLLLoss",
                "https://pytorch.org/docs/stable/generated/torch.nn.L1Loss.html": "nn.L1Loss",
                "https://pytorch.org/docs/stable/generated/torch.nn.SmoothL1Loss.html": "nn.SmoothL1Loss",
                "https://pytorch.org/docs/stable/generated/torch.nn.HuberLoss.html": "nn.HuberLoss",
                "https://pytorch.org/docs/stable/generated/torch.nn.KLDivLoss.html": "nn.KLDivLoss",
                "https://pytorch.org/docs/stable/generated/torch.nn.CosineEmbeddingLoss.html": "nn.CosineEmbeddingLoss",
                "https://pytorch.org/docs/stable/generated/torch.nn.TripletMarginLoss.html": "nn.TripletMarginLoss",
                "https://pytorch.org/docs/stable/generated/torch.nn.ParameterList.html": "nn.ParameterList",
                "https://pytorch.org/docs/stable/generated/torch.nn.Parameter.html": "nn.Parameter",
                "https://pytorch.org/docs/stable/generated/torch.nn.utils.clip_grad_norm_.html": "clip_grad_norm_",
                "https://pytorch.org/docs/stable/generated/torch.nn.utils.clip_grad_value_.html": "clip_grad_value_",
                "https://pytorch.org/docs/stable/generated/torch.nn.init.xavier_uniform_.html": "xavier_uniform_",
                "https://pytorch.org/docs/stable/generated/torch.nn.init.kaiming_uniform_.html": "kaiming_uniform_",
                "https://pytorch.org/docs/stable/generated/torch.nn.init.normal_.html": "init.normal_",
                "https://pytorch.org/docs/stable/generated/torch.nn.init.constant_.html": "init.constant_",
            },
        },
        "data-loading": {
            "pages": {
                "https://pytorch.org/docs/stable/data.html": "torch.utils.data",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.DataLoader.html": "DataLoader",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.Dataset.html": "Dataset",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.IterableDataset.html": "IterableDataset",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.TensorDataset.html": "TensorDataset",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.ConcatDataset.html": "ConcatDataset",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.Subset.html": "Subset",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.random_split.html": "random_split",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.Sampler.html": "Sampler",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.RandomSampler.html": "RandomSampler",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.SequentialSampler.html": "SequentialSampler",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.BatchSampler.html": "BatchSampler",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.DistributedSampler.html": "DistributedSampler",
                "https://pytorch.org/docs/stable/generated/torch.utils.data.WeightedRandomSampler.html": "WeightedRandomSampler",
            },
        },
        "transforms": {
            "pages": {
                "https://pytorch.org/vision/stable/transforms.html": "Torchvision Transforms",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.Compose.html": "transforms.Compose",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.ToTensor.html": "transforms.ToTensor",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.Normalize.html": "transforms.Normalize",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.Resize.html": "transforms.Resize",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.CenterCrop.html": "transforms.CenterCrop",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.RandomCrop.html": "transforms.RandomCrop",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.RandomHorizontalFlip.html": "transforms.RandomHorizontalFlip",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.RandomVerticalFlip.html": "transforms.RandomVerticalFlip",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.RandomRotation.html": "transforms.RandomRotation",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.ColorJitter.html": "transforms.ColorJitter",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.RandomAffine.html": "transforms.RandomAffine",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.RandomPerspective.html": "transforms.RandomPerspective",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.RandomErasing.html": "transforms.RandomErasing",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.GaussianBlur.html": "transforms.GaussianBlur",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.Pad.html": "transforms.Pad",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.RandomGrayscale.html": "transforms.RandomGrayscale",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.ToPILImage.html": "transforms.ToPILImage",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.Lambda.html": "transforms.Lambda",
                "https://pytorch.org/vision/stable/generated/torchvision.transforms.RandomResizedCrop.html": "transforms.RandomResizedCrop",
                "https://pytorch.org/vision/stable/auto_examples/transforms/plot_transforms_getting_started.html": "Transforms Getting Started",
            },
        },
        "saving-loading": {
            "pages": {
                "https://pytorch.org/docs/stable/generated/torch.save.html": "torch.save",
                "https://pytorch.org/docs/stable/generated/torch.load.html": "torch.load",
                "https://pytorch.org/docs/stable/notes/serialization.html": "Serialization Semantics",
                "https://pytorch.org/tutorials/beginner/saving_loading_models.html": "Saving and Loading Models",
                "https://pytorch.org/docs/stable/generated/torch.jit.save.html": "torch.jit.save",
                "https://pytorch.org/docs/stable/generated/torch.jit.load.html": "torch.jit.load",
                "https://pytorch.org/docs/stable/generated/torch.export.save.html": "torch.export.save",
                "https://pytorch.org/docs/stable/generated/torch.export.load.html": "torch.export.load",
            },
        },
        "torchvision": {
            "pages": {
                "https://pytorch.org/vision/stable/index.html": "Torchvision Documentation",
                "https://pytorch.org/vision/stable/models.html": "Torchvision Models",
                "https://pytorch.org/vision/stable/datasets.html": "Torchvision Datasets",
                "https://pytorch.org/vision/stable/io.html": "Torchvision IO",
                "https://pytorch.org/vision/stable/ops.html": "Torchvision Ops",
                "https://pytorch.org/vision/stable/utils.html": "Torchvision Utils",
                "https://pytorch.org/vision/stable/feature_extraction.html": "Torchvision Feature Extraction",
                "https://pytorch.org/vision/stable/models/resnet.html": "ResNet",
                "https://pytorch.org/vision/stable/models/vgg.html": "VGG",
                "https://pytorch.org/vision/stable/models/alexnet.html": "AlexNet",
                "https://pytorch.org/vision/stable/models/densenet.html": "DenseNet",
                "https://pytorch.org/vision/stable/models/efficientnet.html": "EfficientNet",
                "https://pytorch.org/vision/stable/models/mobilenetv2.html": "MobileNet V2",
                "https://pytorch.org/vision/stable/models/mobilenetv3.html": "MobileNet V3",
                "https://pytorch.org/vision/stable/models/inception.html": "Inception",
                "https://pytorch.org/vision/stable/models/squeezenet.html": "SqueezeNet",
                "https://pytorch.org/vision/stable/models/shufflenetv2.html": "ShuffleNet V2",
                "https://pytorch.org/vision/stable/models/wide_resnet.html": "Wide ResNet",
                "https://pytorch.org/vision/stable/models/vision_transformer.html": "Vision Transformer",
                "https://pytorch.org/vision/stable/models/swin_transformer.html": "Swin Transformer",
                "https://pytorch.org/vision/stable/models/convnext.html": "ConvNeXt",
                "https://pytorch.org/vision/stable/models/maxvit.html": "MaxVit",
                "https://pytorch.org/vision/stable/models/fasterrcnn.html": "Faster R-CNN",
                "https://pytorch.org/vision/stable/models/retinanet.html": "RetinaNet",
                "https://pytorch.org/vision/stable/models/ssd.html": "SSD",
                "https://pytorch.org/vision/stable/models/fcos.html": "FCOS",
                "https://pytorch.org/vision/stable/models/maskrcnn.html": "Mask R-CNN",
                "https://pytorch.org/vision/stable/models/keypointrcnn.html": "Keypoint R-CNN",
                "https://pytorch.org/vision/stable/models/deeplabv3.html": "DeepLab V3",
                "https://pytorch.org/vision/stable/models/fcn.html": "FCN",
                "https://pytorch.org/vision/stable/models/lraspp.html": "LRASPP",
                "https://pytorch.org/vision/stable/generated/torchvision.datasets.CIFAR10.html": "CIFAR-10",
                "https://pytorch.org/vision/stable/generated/torchvision.datasets.CIFAR100.html": "CIFAR-100",
                "https://pytorch.org/vision/stable/generated/torchvision.datasets.MNIST.html": "MNIST",
                "https://pytorch.org/vision/stable/generated/torchvision.datasets.FashionMNIST.html": "FashionMNIST",
                "https://pytorch.org/vision/stable/generated/torchvision.datasets.ImageNet.html": "ImageNet",
                "https://pytorch.org/vision/stable/generated/torchvision.datasets.ImageFolder.html": "ImageFolder",
                "https://pytorch.org/vision/stable/generated/torchvision.datasets.CocoDetection.html": "COCO Detection",
                "https://pytorch.org/vision/stable/generated/torchvision.datasets.VOCDetection.html": "VOC Detection",
            },
        },
        "torchaudio": {
            "pages": {
                "https://pytorch.org/audio/stable/index.html": "Torchaudio Documentation",
                "https://pytorch.org/audio/stable/torchaudio.html": "torchaudio",
                "https://pytorch.org/audio/stable/transforms.html": "Torchaudio Transforms",
                "https://pytorch.org/audio/stable/functional.html": "Torchaudio Functional",
                "https://pytorch.org/audio/stable/datasets.html": "Torchaudio Datasets",
                "https://pytorch.org/audio/stable/models.html": "Torchaudio Models",
                "https://pytorch.org/audio/stable/pipelines.html": "Torchaudio Pipelines",
                "https://pytorch.org/audio/stable/io.html": "Torchaudio IO",
                "https://pytorch.org/audio/stable/backend.html": "Torchaudio Backend",
                "https://pytorch.org/audio/stable/sox_effects.html": "Torchaudio Sox Effects",
                "https://pytorch.org/audio/stable/compliance.kaldi.html": "Torchaudio Kaldi Compliance",
                "https://pytorch.org/audio/stable/generated/torchaudio.load.html": "torchaudio.load",
                "https://pytorch.org/audio/stable/generated/torchaudio.save.html": "torchaudio.save",
                "https://pytorch.org/audio/stable/generated/torchaudio.info.html": "torchaudio.info",
                "https://pytorch.org/audio/stable/generated/torchaudio.transforms.Spectrogram.html": "Spectrogram",
                "https://pytorch.org/audio/stable/generated/torchaudio.transforms.MelSpectrogram.html": "MelSpectrogram",
                "https://pytorch.org/audio/stable/generated/torchaudio.transforms.MFCC.html": "MFCC",
                "https://pytorch.org/audio/stable/generated/torchaudio.transforms.Resample.html": "Resample",
            },
        },
        "torchtext": {
            "pages": {
                "https://pytorch.org/text/stable/index.html": "Torchtext Documentation",
                "https://pytorch.org/text/stable/datasets.html": "Torchtext Datasets",
                "https://pytorch.org/text/stable/data_utils.html": "Torchtext Data Utils",
                "https://pytorch.org/text/stable/transforms.html": "Torchtext Transforms",
                "https://pytorch.org/text/stable/vocab.html": "Torchtext Vocab",
                "https://pytorch.org/text/stable/models.html": "Torchtext Models",
                "https://pytorch.org/text/stable/functional.html": "Torchtext Functional",
                "https://pytorch.org/text/stable/nn_modules.html": "Torchtext NN Modules",
                "https://pytorch.org/text/stable/utils.html": "Torchtext Utils",
            },
        },
        "distributed": {
            "pages": {
                "https://pytorch.org/docs/stable/distributed.html": "Distributed Communication",
                "https://pytorch.org/docs/stable/notes/ddp.html": "DDP Notes",
                "https://pytorch.org/docs/stable/generated/torch.nn.parallel.DistributedDataParallel.html": "DistributedDataParallel",
                "https://pytorch.org/docs/stable/generated/torch.nn.DataParallel.html": "DataParallel",
                "https://pytorch.org/docs/stable/rpc.html": "Distributed RPC",
                "https://pytorch.org/docs/stable/distributed.fsdp.html": "FSDP",
                "https://pytorch.org/docs/stable/elastic/run.html": "TorchElastic",
                "https://pytorch.org/docs/stable/distributed.tensor.parallel.html": "Tensor Parallelism",
                "https://pytorch.org/docs/stable/distributed.pipeline.html": "Pipeline Parallelism",
                "https://pytorch.org/docs/stable/distributed.checkpoint.html": "Distributed Checkpoint",
                "https://pytorch.org/docs/stable/distributed.optim.html": "Distributed Optimizer",
                "https://pytorch.org/docs/stable/distributed.algorithms.join.html": "Join Context Manager",
                "https://pytorch.org/docs/stable/generated/torch.distributed.init_process_group.html": "init_process_group",
                "https://pytorch.org/docs/stable/generated/torch.distributed.all_reduce.html": "all_reduce",
                "https://pytorch.org/docs/stable/generated/torch.distributed.broadcast.html": "broadcast",
                "https://pytorch.org/docs/stable/generated/torch.distributed.all_gather.html": "all_gather",
                "https://pytorch.org/docs/stable/generated/torch.distributed.reduce_scatter.html": "reduce_scatter",
                "https://pytorch.org/docs/stable/generated/torch.distributed.barrier.html": "barrier",
                "https://pytorch.org/docs/stable/generated/torch.distributed.send.html": "send",
                "https://pytorch.org/docs/stable/generated/torch.distributed.recv.html": "recv",
                "https://pytorch.org/tutorials/intermediate/ddp_tutorial.html": "DDP Tutorial",
                "https://pytorch.org/tutorials/intermediate/dist_tuto.html": "Distributed Tutorial",
                "https://pytorch.org/tutorials/intermediate/FSDP_tutorial.html": "FSDP Tutorial",
            },
        },
        "quantization": {
            "pages": {
                "https://pytorch.org/docs/stable/quantization.html": "Quantization",
                "https://pytorch.org/docs/stable/quantization-support.html": "Quantization Support",
                "https://pytorch.org/docs/stable/generated/torch.quantization.quantize_dynamic.html": "Dynamic Quantization",
                "https://pytorch.org/docs/stable/generated/torch.quantization.prepare.html": "Quantization Prepare",
                "https://pytorch.org/docs/stable/generated/torch.quantization.convert.html": "Quantization Convert",
                "https://pytorch.org/docs/stable/generated/torch.quantization.QConfig.html": "QConfig",
                "https://pytorch.org/docs/stable/generated/torch.ao.quantization.quantize_fx.html": "FX Graph Mode Quantization",
                "https://pytorch.org/tutorials/advanced/static_quantization_tutorial.html": "Static Quantization Tutorial",
                "https://pytorch.org/tutorials/intermediate/dynamic_quantization_bert_tutorial.html": "Dynamic Quantization BERT",
                "https://pytorch.org/tutorials/prototype/pt2e_quant_ptq.html": "PT2E PTQ Tutorial",
            },
        },
        "pruning": {
            "pages": {
                "https://pytorch.org/docs/stable/generated/torch.nn.utils.prune.l1_unstructured.html": "L1 Unstructured Pruning",
                "https://pytorch.org/docs/stable/generated/torch.nn.utils.prune.random_unstructured.html": "Random Unstructured Pruning",
                "https://pytorch.org/docs/stable/generated/torch.nn.utils.prune.ln_structured.html": "Ln Structured Pruning",
                "https://pytorch.org/docs/stable/generated/torch.nn.utils.prune.global_unstructured.html": "Global Unstructured Pruning",
                "https://pytorch.org/docs/stable/generated/torch.nn.utils.prune.remove.html": "Remove Pruning",
                "https://pytorch.org/docs/stable/generated/torch.nn.utils.prune.is_pruned.html": "Is Pruned",
                "https://pytorch.org/tutorials/intermediate/pruning_tutorial.html": "Pruning Tutorial",
            },
        },
        "mobile": {
            "pages": {
                "https://pytorch.org/mobile/home/": "PyTorch Mobile",
                "https://pytorch.org/mobile/android/": "PyTorch Android",
                "https://pytorch.org/mobile/ios/": "PyTorch iOS",
                "https://pytorch.org/executorch/stable/index.html": "ExecuTorch",
                "https://pytorch.org/executorch/stable/getting-started-setup.html": "ExecuTorch Setup",
                "https://pytorch.org/executorch/stable/export-overview.html": "ExecuTorch Export",
                "https://pytorch.org/executorch/stable/runtime-overview.html": "ExecuTorch Runtime",
                "https://pytorch.org/executorch/stable/backend-delegates-integration.html": "ExecuTorch Delegates",
                "https://pytorch.org/tutorials/beginner/deeplabv3_on_android.html": "DeepLab on Android",
                "https://pytorch.org/tutorials/beginner/deeplabv3_on_ios.html": "DeepLab on iOS",
            },
        },
        "onnx": {
            "pages": {
                "https://pytorch.org/docs/stable/onnx.html": "ONNX Export",
                "https://pytorch.org/docs/stable/onnx_dynamo.html": "ONNX Dynamo Export",
                "https://pytorch.org/docs/stable/onnx_torchscript.html": "ONNX TorchScript Export",
                "https://pytorch.org/docs/stable/generated/torch.onnx.export.html": "torch.onnx.export",
                "https://pytorch.org/docs/stable/generated/torch.onnx.dynamo_export.html": "torch.onnx.dynamo_export",
                "https://pytorch.org/tutorials/advanced/super_resolution_with_onnxruntime.html": "ONNX Runtime Tutorial",
            },
        },
        "tutorials-beginner": {
            "pages": {
                "https://pytorch.org/tutorials/": "PyTorch Tutorials Home",
                "https://pytorch.org/tutorials/beginner/basics/intro.html": "Learn the Basics",
                "https://pytorch.org/tutorials/beginner/basics/quickstart_tutorial.html": "Quickstart",
                "https://pytorch.org/tutorials/beginner/basics/tensorqs_tutorial.html": "Tensors Tutorial",
                "https://pytorch.org/tutorials/beginner/basics/data_tutorial.html": "Datasets & DataLoaders",
                "https://pytorch.org/tutorials/beginner/basics/transforms_tutorial.html": "Transforms Tutorial",
                "https://pytorch.org/tutorials/beginner/basics/buildmodel_tutorial.html": "Build Model Tutorial",
                "https://pytorch.org/tutorials/beginner/basics/autogradqs_tutorial.html": "Autograd Tutorial",
                "https://pytorch.org/tutorials/beginner/basics/optimization_tutorial.html": "Optimization Tutorial",
                "https://pytorch.org/tutorials/beginner/basics/saveloadrun_tutorial.html": "Save & Load Tutorial",
                "https://pytorch.org/tutorials/beginner/deep_learning_60min_blitz.html": "60 Minute Blitz",
                "https://pytorch.org/tutorials/beginner/blitz/tensor_tutorial.html": "Tensor Tutorial (Blitz)",
                "https://pytorch.org/tutorials/beginner/blitz/autograd_tutorial.html": "Autograd Tutorial (Blitz)",
                "https://pytorch.org/tutorials/beginner/blitz/neural_networks_tutorial.html": "Neural Networks (Blitz)",
                "https://pytorch.org/tutorials/beginner/blitz/cifar10_tutorial.html": "CIFAR-10 Classifier",
                "https://pytorch.org/tutorials/beginner/pytorch_with_examples.html": "PyTorch with Examples",
                "https://pytorch.org/tutorials/beginner/nn_tutorial.html": "What is torch.nn",
                "https://pytorch.org/tutorials/beginner/transfer_learning_tutorial.html": "Transfer Learning",
                "https://pytorch.org/tutorials/beginner/data_loading_tutorial.html": "Data Loading Tutorial",
                "https://pytorch.org/tutorials/beginner/dcgan_faces_tutorial.html": "DCGAN Tutorial",
                "https://pytorch.org/tutorials/beginner/nlp/pytorch_tutorial.html": "NLP From Scratch: Classifying Names",
                "https://pytorch.org/tutorials/beginner/nlp/word_embeddings_tutorial.html": "Word Embeddings Tutorial",
                "https://pytorch.org/tutorials/beginner/nlp/sequence_models_tutorial.html": "Sequence Models Tutorial",
                "https://pytorch.org/tutorials/beginner/text_sentiment_ngrams_tutorial.html": "Text Classification",
                "https://pytorch.org/tutorials/beginner/transformer_tutorial.html": "Transformer Tutorial",
                "https://pytorch.org/tutorials/beginner/chatbot_tutorial.html": "Chatbot Tutorial",
                "https://pytorch.org/tutorials/beginner/finetuning_torchvision_models_tutorial.html": "Finetuning Torchvision",
            },
        },
        "tutorials-intermediate": {
            "pages": {
                "https://pytorch.org/tutorials/intermediate/seq2seq_translation_tutorial.html": "Seq2Seq Translation",
                "https://pytorch.org/tutorials/intermediate/reinforcement_q_learning.html": "Reinforcement Learning (DQN)",
                "https://pytorch.org/tutorials/intermediate/char_rnn_classification_tutorial.html": "Char RNN Classification",
                "https://pytorch.org/tutorials/intermediate/char_rnn_generation_tutorial.html": "Char RNN Generation",
                "https://pytorch.org/tutorials/intermediate/tensorboard_tutorial.html": "TensorBoard Tutorial",
                "https://pytorch.org/tutorials/intermediate/torchvision_tutorial.html": "Torchvision Object Detection",
                "https://pytorch.org/tutorials/intermediate/speech_recognition_pipeline_tutorial.html": "Speech Recognition",
                "https://pytorch.org/tutorials/intermediate/speech_command_classification_with_torchaudio_tutorial.html": "Speech Command Classification",
                "https://pytorch.org/tutorials/intermediate/text_to_speech_with_torchaudio.html": "Text-to-Speech",
                "https://pytorch.org/tutorials/intermediate/forced_alignment_with_torchaudio_tutorial.html": "Forced Alignment",
                "https://pytorch.org/tutorials/intermediate/memory_format_tutorial.html": "Memory Format Tutorial",
                "https://pytorch.org/tutorials/intermediate/fx_conv_bn_fuser.html": "FX Conv-BN Fuser",
                "https://pytorch.org/tutorials/intermediate/torch_compile_tutorial.html": "torch.compile Tutorial",
                "https://pytorch.org/tutorials/intermediate/scaled_dot_product_attention_tutorial.html": "Scaled Dot-Product Attention",
                "https://pytorch.org/tutorials/intermediate/model_parallel_tutorial.html": "Model Parallel Tutorial",
                "https://pytorch.org/tutorials/intermediate/rpc_tutorial.html": "RPC Tutorial",
                "https://pytorch.org/tutorials/intermediate/autograd_saved_tensors_hooks_tutorial.html": "Autograd Saved Tensors Hooks",
            },
        },
        "tutorials-advanced": {
            "pages": {
                "https://pytorch.org/tutorials/advanced/dynamic_quantization_tutorial.html": "Dynamic Quantization (Advanced)",
                "https://pytorch.org/tutorials/advanced/cpp_export.html": "C++ Export",
                "https://pytorch.org/tutorials/advanced/cpp_extension.html": "C++ Extension",
                "https://pytorch.org/tutorials/advanced/torch_script_custom_ops.html": "Custom TorchScript Ops",
                "https://pytorch.org/tutorials/advanced/torch_script_custom_classes.html": "Custom TorchScript Classes",
                "https://pytorch.org/tutorials/advanced/dispatcher.html": "Dispatcher Tutorial",
                "https://pytorch.org/tutorials/advanced/extend_dispatcher.html": "Extend Dispatcher",
                "https://pytorch.org/tutorials/advanced/python_custom_ops.html": "Python Custom Ops",
                "https://pytorch.org/tutorials/advanced/neural_style_tutorial.html": "Neural Style Transfer",
                "https://pytorch.org/tutorials/advanced/numpy_extensions_tutorial.html": "NumPy Extensions",
                "https://pytorch.org/tutorials/advanced/ddp_pipeline.html": "DDP Pipeline Tutorial",
                "https://pytorch.org/tutorials/advanced/generic_join.html": "Generic Join Context Manager",
            },
        },
        "tutorials-recipes": {
            "pages": {
                "https://pytorch.org/tutorials/recipes/recipes_index.html": "Recipes Index",
                "https://pytorch.org/tutorials/recipes/recipes/loading_data_recipe.html": "Loading Data Recipe",
                "https://pytorch.org/tutorials/recipes/recipes/defining_a_neural_network.html": "Defining a Neural Network",
                "https://pytorch.org/tutorials/recipes/recipes/what_is_state_dict.html": "What is state_dict",
                "https://pytorch.org/tutorials/recipes/recipes/saving_and_loading_models_for_inference.html": "Save/Load for Inference",
                "https://pytorch.org/tutorials/recipes/recipes/saving_and_loading_a_general_checkpoint.html": "Save/Load General Checkpoint",
                "https://pytorch.org/tutorials/recipes/recipes/saving_multiple_models_in_one_file.html": "Save Multiple Models",
                "https://pytorch.org/tutorials/recipes/recipes/warmstarting_model_using_parameters_from_a_different_model.html": "Warmstarting Models",
                "https://pytorch.org/tutorials/recipes/recipes/save_load_across_devices.html": "Save/Load Across Devices",
                "https://pytorch.org/tutorials/recipes/recipes/zeroing_out_gradients.html": "Zeroing Out Gradients",
                "https://pytorch.org/tutorials/recipes/recipes/benchmark.html": "Benchmark Recipe",
                "https://pytorch.org/tutorials/recipes/recipes/timer_quick_start.html": "Timer Quick Start",
                "https://pytorch.org/tutorials/recipes/recipes/amp_recipe.html": "AMP Recipe",
                "https://pytorch.org/tutorials/recipes/recipes/tuning_guide.html": "Performance Tuning Guide",
                "https://pytorch.org/tutorials/recipes/torch_compile_user_defined_triton_kernel_tutorial.html": "Triton Kernel Tutorial",
                "https://pytorch.org/tutorials/recipes/torch_compile_backend_ipex.html": "torch.compile IPEX Backend",
                "https://pytorch.org/tutorials/recipes/regional_compilation.html": "Regional Compilation",
                "https://pytorch.org/tutorials/recipes/compiling_optimizer.html": "Compiling Optimizer",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"pytorch-{source_key}" if source_key else "pytorch"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean common suffixes
            for suffix in [' - PyTorch', ' PyTorch', ' | PyTorch']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"pytorch-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping pytorch/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    PyTorchScraper(base, source_key).run()
