import os 

# wgan训练脚本

lrs = [0.00005, 0.0001, 0.0005, 0.001, 0.005]

device_ids = [0]

base_image_path = 'lr'

for lr in lrs:
    image_path = base_image_path + "/" + str(lr)
    os.system(f'python wgan.py --image_path {image_path} --lr {lr} --device_id {device_ids[0]}')


