import os

clip_values = [0.01, 0.05, 0.1, 0.2, 0.5]

device_ids = [1]

for clip_value in clip_values:
    image_path = f'clip_value/{clip_value}'
    os.system(f'python wgan.py --image_path {image_path} --clip_value {clip_value} --device_id {device_ids[0]}')