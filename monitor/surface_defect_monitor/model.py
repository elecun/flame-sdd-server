'''
Surface Defect Classification(Binary) Model using Residual Network with Pytorch
@author Byunghun Hwang<bh.hwang@iae.re.kr>
'''
import torch
import torch.nn as nn
import torchvision
import torchvision.models as models
import torch.nn.functional as F
from torchvision.datasets.utils import download_url
from torchvision.datasets import ImageFolder
from torch.utils.data import DataLoader
import torchvision.transforms as transform
from torch.utils.data import random_split
from torchvision.utils import make_grid
from torchinfo import summary

from PIL import Image
import pathlib
import os
from typing import Union
import argparse

from util.logger.console import ConsoleLogger

# global functions
# transfer data into the selected device
def to_device(data, device):
    if isinstance(data, (list, tuple)):
        return [to_device(x, device) for x in data]
    return data.to(device, non_blocking=True)

# Model base class
class ModelBase(nn.Module):
    @staticmethod
    def __accuracy(outputs, labels):
        _, preds = torch.max(outputs, dim=1)
        return torch.tensor(torch.sum(preds == labels).item() / len(preds))

    def training_step(self, batch):
        images, labels = batch 
        out = self(images)                  # Generate predictions
        loss = F.cross_entropy(out, labels) # Calculate loss
        acc = self.__accuracy(out, labels)  
        return loss,acc
    
    def validation_step(self, batch):
        images, labels = batch 
        out = self(images)                    # Generate predictions
        loss = F.cross_entropy(out, labels)   # Calculate loss
        acc = self.__accuracy(out, labels)    # Calculate accuracy
        return {'val_loss': loss.detach(), 'val_acc': acc}
        
    def validation_epoch_end(self, outputs):
        batch_losses = [x['val_loss'] for x in outputs]
        epoch_loss = torch.stack(batch_losses).mean()   # Combine losses
        batch_accs = [x['val_acc'] for x in outputs]
        epoch_acc = torch.stack(batch_accs).mean()      # Combine accuracies
        return {'val_loss': epoch_loss.item(), 'val_acc': epoch_acc.item()}
    
    def epoch_end(self, epoch, result):
        print("Epoch [{}], train_loss: {:.4f}, train_acc: {:.4f}, val_loss: {:.4f}, val_acc: {:.4f}, last_lr: {:.5f}".format(
            epoch+1, result['train_loss'], result['train_accuracy'], result['val_loss'], result['val_acc'], result['lrs'][-1]))
        
class ResNet(ModelBase):
    # resnet layer block : conv2d -> batch normalization -> ReLu
    @staticmethod
    def __conv_block(in_channels, out_channels, pool=False):
        # output dim and input dim are the same (kernel size=3, padding=1)
        layers = [nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1), nn.BatchNorm2d(num_features=out_channels), nn.ReLU(inplace=True)]
        if pool: 
            layers.append(nn.MaxPool2d(kernel_size=2))  # max pooling with 2 dim kernel
        return nn.Sequential(*layers) # combine into single block
    
    def __init__(self, channels, n_classes):
        super().__init__()
        
        self.conv1 = self.__conv_block(channels, 64)
        self.conv2 = self.__conv_block(64, 128, pool=True)
        self.res1 = nn.Sequential(self.__conv_block(128, 128), self.__conv_block(128, 128))
        
        self.conv3 = self.__conv_block(128, 256, pool=True)
        self.conv4 = self.__conv_block(256, 512, pool=True)
        self.res2 = nn.Sequential(self.__conv_block(512, 512), self.__conv_block(512, 512))
        
        self.classifier = nn.Sequential(nn.AdaptiveMaxPool2d((1,1)), 
                                        nn.Flatten(), 
                                        nn.Dropout(0.2),
                                        nn.Linear(512, n_classes))
        
    def forward(self, xb):
        out = self.conv1(xb)
        out = self.conv2(out)
        out = self.res1(out) + out
        out = self.conv3(out)
        out = self.conv4(out)
        out = self.res2(out) + out
        out = self.classifier(out)
        return out


# ResNet for PurgeFan Fault Classification
class PurgeFanFaultClassification_Resnet:
    def __init__(self, modelname:str) -> None:
        
        # for logging
        self.__console = ConsoleLogger.get_logger()
        
        self.__classes = ['fault', 'normal']
        self.__model = None # torch model instance
        self.__device = None # device to perform
        self.__model_path = pathlib.Path(__file__).parent / "model" / modelname
        self.__console.info(f"Model : {self.__model_path.as_posix()}")
        
        if os.path.isfile(self.__model_path.as_posix()):
            self.__model = ResNet(channels=3, n_classes=2)
            self.__model.load_state_dict(torch.load(self.__model_path.as_posix(), map_location=self.get_device_use()))
            self.__model.eval() # evaluation mode
            self.__console.info("PurgeFan Fault Classification(Binary) model is successfully loaded")
        
        else:
            self.__console.critical("PurgeFan Fault Classification Model is not exist")
            
    # model file exist check
    def exist(self):
        if os.path.isfile(self.__model_path.as_posix()):
            return True
        return False
    
    # device to perform        
    def get_device_use(self):
        if torch.cuda.is_available():
            self.__console.info("CUDA Device is selected")
            return torch.device('cuda')
        elif torch.backends.mps.is_available():
            self.__console.info("MPS Device is selected")
            return torch.device('mps')
        else:
            self.__console.info("CPU Device is selected")
            return torch.device('cpu')
    
    # performing the model inference
    def inference(self, image_path:pathlib.Path) -> str:
        try:
            # image preprocessing (changable mean, std responding to dataset)
            _transformer = transform.Compose([transform.ToTensor(), 
                                            transform.Normalize(mean=[0.0117, 0.0728, 0.8407], std=[0.9999, 0.9973, 0.5415])])
            _image = Image.open(image_path)
            _image = _transformer(_image).unsqueeze(0)
            
            with torch.no_grad():
                result = self.__model(_image)
                _, preds  = torch.max(result, dim=1) # pick highest class label
                return self.__classes[preds[0].item()]
        except Exception as e:
            self.__console.critical(f"{e}")        
            return "unknown"
            
    
    def predict_image(self, img, model):
        # Convert to a batch of 1
        xb = self.__to_device(img.unsqueeze(0), self.__device)
        # Get predictions from model
        self.__model.eval()
        with torch.no_grad():
            yb = self.__model(xb)
        # Pick index with highest probability
        _, preds  = torch.max(yb, dim=1)
        # Retrieve the class label
        return self.__classes[preds[0].item()]