import argparse
import os
import numpy as np
import math
import sys

import torchvision.transforms as transforms
from torchvision.utils import save_image

from torch.utils.data import DataLoader
from torchvision import datasets
from torch.autograd import Variable

import torch.nn as nn
import torch.nn.functional as F
import torch


parser = argparse.ArgumentParser()
parser.add_argument("--n_epochs", type=int, default=500, help="number of epochs of training")
parser.add_argument("--batch_size", type=int, default=512, help="size of the batches")
parser.add_argument("--lr", type=float, default=0.00005, help="learning rate")
parser.add_argument("--n_cpu", type=int, default=8, help="number of cpu threads to use during batch generation")
parser.add_argument("--latent_dim", type=int, default=100, help="dimensionality of the latent space")

parser.add_argument("--img_size", type=int, default=28, help="size of each image dimension")
parser.add_argument("--channels", type=int, default=1, help="number of image channels")

parser.add_argument("--n_critic", type=int, default=5, help="number of training steps for discriminator per iter")
parser.add_argument("--clip_value", type=float, default=0.01, help="lower and upper clip value for disc. weights")
parser.add_argument("--sample_interval", type=int, default=400, help="interval betwen image samples")

parser.add_argument("--device_id", type=int, default=0, help="device id")
parser.add_argument("--image_path", type=str, default="test", help="path to save images")

opt = parser.parse_args()
print(opt)

os.makedirs('result_wgan/' + opt.image_path, exist_ok=True)

img_shape = (opt.channels, opt.img_size, opt.img_size)

cuda = True if torch.cuda.is_available() else False
device = torch.device(f"cuda:{opt.device_id}" if torch.cuda.is_available() else "cpu")


class Generator(nn.Module):
    def __init__(self):
        super(Generator, self).__init__()

        def block(in_feat, out_feat, normalize=True):
            layers = [nn.Linear(in_feat, out_feat)]
            if normalize:
                layers.append(nn.BatchNorm1d(out_feat, 0.8))
            layers.append(nn.LeakyReLU(0.2, inplace=True))
            return layers

        self.model = nn.Sequential(
            *block(opt.latent_dim, 128, normalize=False),
            *block(128, 256),
            *block(256, 512),
            *block(512, 1024),
            nn.Linear(1024, int(np.prod(img_shape))),
            nn.Tanh()
        )

    def forward(self, z):
        img = self.model(z)
        img = img.view(img.shape[0], *img_shape)
        return img


class Discriminator(nn.Module):
    def __init__(self):
        super(Discriminator, self).__init__()

        self.model = nn.Sequential(
            nn.Linear(int(np.prod(img_shape)), 512),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(512, 256),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Linear(256, 1),
        )

    def forward(self, img):
        img_flat = img.view(img.shape[0], -1)
        validity = self.model(img_flat)
        return validity

class ConvGenerator(nn.Module):
    def __init__(self, latent_dim, img_channels, img_size):
        super(ConvGenerator, self).__init__()
        self.init_size = img_size // 4  # 初始分辨率
        self.fc = nn.Linear(latent_dim, 128 * self.init_size * self.init_size)

        self.conv_blocks = nn.Sequential(
            nn.BatchNorm2d(128),
            nn.Upsample(scale_factor=2),  # 上采样
            nn.Conv2d(128, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.Upsample(scale_factor=2),
            nn.Conv2d(128, 64, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, img_channels, kernel_size=3, stride=1, padding=1),
            nn.Tanh(),  # 输出范围 [-1, 1]
        )

    def forward(self, z):
        out = self.fc(z)
        out = out.view(out.size(0), 128, self.init_size, self.init_size)  # reshape 为特征图
        img = self.conv_blocks(out)
        return img

class ConvDiscriminator(nn.Module):
    def __init__(self, img_channels, img_size):
        super(ConvDiscriminator, self).__init__()
        def conv_block(in_channels, out_channels, bn=True):
            layers = [nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=2, padding=1)]
            if bn:
                layers.append(nn.BatchNorm2d(out_channels))
            layers.append(nn.LeakyReLU(0.2, inplace=True))
            return layers

        self.model = nn.Sequential(
            *conv_block(img_channels, 64, bn=False),
            *conv_block(64, 128),
            *conv_block(128, 256),
            *conv_block(256, 512),
        )

        ds_size = 2  # 每层 stride=2 的卷积将尺寸减半
        self.fc = nn.Linear(512 * ds_size * ds_size, 1)

    def forward(self, img):
        out = self.model(img)
        out = out.view(out.size(0), -1)  # 展平

        validity = self.fc(out)
        return validity


# Initialize generator and discriminator
# generator = Generator().to(device)
# discriminator = Discriminator().to(device)

# 替换生成器和判别器
generator = ConvGenerator(latent_dim=opt.latent_dim, img_channels=opt.channels, img_size=opt.img_size).to(device)
discriminator = ConvDiscriminator(img_channels=opt.channels, img_size=opt.img_size).to(device)



# if cuda:
#     generator.cuda()
#     discriminator.cuda()

# Configure data loader
# os.makedirs("../../data/mnist", exist_ok=True)
os.makedirs("data/mnist", exist_ok=True)
dataloader = torch.utils.data.DataLoader(
    datasets.MNIST(
        # "../../data/mnist",
        "data/mnist",
        train=True,
        download=True,
        transform=transforms.Compose([transforms.ToTensor(), transforms.Normalize([0.5], [0.5])]),
    ),
    batch_size=opt.batch_size,
    shuffle=True,
)

# Optimizers
optimizer_G = torch.optim.RMSprop(generator.parameters(), lr=opt.lr)
optimizer_D = torch.optim.RMSprop(discriminator.parameters(), lr=opt.lr)

# Tensor = torch.cuda.FloatTensor if cuda else torch.FloatTensor
Tensor = lambda x: torch.tensor(x, device=device, dtype=torch.float32)


# ----------
#  Training
# ----------

batches_done = 0
for epoch in range(opt.n_epochs):
    
    for i, (imgs, _) in enumerate(dataloader):
        
        # Configure input
        # real_imgs = Variable(imgs.type(Tensor)).to(device)
        real_imgs = imgs.to(device).type(torch.float32)

        # ---------------------
        #  Train Discriminator
        # ---------------------

        optimizer_D.zero_grad()

        # Sample noise as generator input
        # z = Variable(Tensor(np.random.normal(0, 1, (imgs.shape[0], opt.latent_dim)))).to(device)
        z = torch.randn((imgs.shape[0], opt.latent_dim), device=device)

        # Generate a batch of images
        fake_imgs = generator(z).detach()
        # Adversarial loss
        loss_D = -torch.mean(discriminator(real_imgs)) + torch.mean(discriminator(fake_imgs))

        loss_D.backward()
        optimizer_D.step()

        # Clip weights of discriminator
        for p in discriminator.parameters():
            p.data.clamp_(-opt.clip_value, opt.clip_value)

        # Train the generator every n_critic iterations
        if i % opt.n_critic == 0:

            # -----------------
            #  Train Generator
            # -----------------

            optimizer_G.zero_grad()

            # Generate a batch of images
            gen_imgs = generator(z)
            # Adversarial loss
            loss_G = -torch.mean(discriminator(gen_imgs))

            loss_G.backward()
            optimizer_G.step()

            print(
                "[Epoch %d/%d] [Batch %d/%d] [D loss: %f] [G loss: %f]"
                % (epoch, opt.n_epochs, batches_done % len(dataloader), len(dataloader), loss_D.item(), loss_G.item())
            )

        # if batches_done % opt.sample_interval == 0:
        #     save_image(gen_imgs.data[:25], f"{opt.image_path}/%d.png" % batches_done, nrow=5, normalize=True)
        batches_done += 1

    z = Variable(Tensor(np.random.normal(0, 1, (25, opt.latent_dim)))).to(device)  # 生成固定数量的图像
    gen_imgs = generator(z)
    save_image(gen_imgs.data[:25], f"result_wgan/{opt.image_path}/epoch%d.png" % epoch, nrow=5, normalize=True)
