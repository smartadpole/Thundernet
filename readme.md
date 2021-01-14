# Thundernet
>2021.01.14    
Thank you for <https://github.com/ouyanghuiyu/Thundernet_Pytorch>    

## Different from the origin project
- higher pytorch version    
- support various image type   
- remove the meaningless message    
- ...    

## Requirements
* pytorch 1.5.0    
* torchvision 0.4    


## pretrained model
- train code in : https://github.com/ouyanghuiyu/Snet    
[ ] model in:     


## Lib Prepare 
```sh
git clone https://github.com/ouyanghuiyu/Thundernet_Pytorch.git
```

### Build  
```sh
cd lib && python setup.py  build_ext --inplace
cd psroialign/PSROIAlign && sh build.sh 
 ```   
## Data Prepare 
Download VOC0712 datasets 
ln -s "YOUR PATH" data

## Train
```sh
cd script
sh  train_49.sh
sh  train_146.sh
sh  train_535.sh
```

## demo
```sh
cd script
sh  pre.sh

```

## TODO LIST
 
 - add coco train and test    
 - add NCNN inference    




