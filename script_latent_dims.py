import os

latent_dims = [100, 200, 300, 400, 500]

device_ids = [2]

base_image_path = 'latent_dims'

for latent_dim in latent_dims:
    image_path = base_image_path + "/" + str(latent_dim)
    os.system(f'python wgan.py --image_path {image_path} --latent_dim {latent_dim} --device_id {device_ids[0]}')