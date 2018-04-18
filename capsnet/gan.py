# -*- coding: utf-8 -*-
"""GAN.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1BTAhVWXL4H3uPYfem7M7B54Wz1Honl2F
"""

"""# Pytorch DCGAN for MNIST
From https://github.com/znxlwm/pytorch-MNIST-CelebA-GAN-DCGAN
"""

import os, time
import matplotlib.pyplot as plt
import itertools
import pickle
import imageio
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.autograd import Variable
from model import Net
import argparse
import utils


"""# **Generator and Discriminator and other definitions**"""

# G(z)
class generator(nn.Module):
    # initializers
    def __init__(self, d=128):
        super(generator, self).__init__()
        #self.deconv1 = nn.ConvTranspose2d(100, d*8, 4, 1, 0)
        self.deconv1 = nn.ConvTranspose2d(100, d*8, 7, 1, 0)
        self.deconv1_bn = nn.BatchNorm2d(d*8)
        self.deconv2 = nn.ConvTranspose2d(d*8, d*4, 4, 2, 1)
        self.deconv2_bn = nn.BatchNorm2d(d*4)
        self.deconv3 = nn.ConvTranspose2d(d*4, d*2, 4, 2, 1)
        self.deconv3_bn = nn.BatchNorm2d(d*2)
        self.deconv3_pool = nn.MaxPool2d(2)
        self.deconv4 = nn.ConvTranspose2d(d*2, d, 4, 2, 1)
        self.deconv4_bn = nn.BatchNorm2d(d)
        self.deconv4_pool = nn.MaxPool2d(2)
        self.deconv5 = nn.ConvTranspose2d(d, 1, 4, 2, 1)

    # weight_init
    def weight_init(self, mean, std):
        for m in self._modules:
            normal_init(self._modules[m], mean, std)

    # forward method
    def forward(self, input):
        # x = F.relu(self.deconv1(input))
        x = F.relu(self.deconv1_bn(self.deconv1(input)))
        x = F.relu(self.deconv2_bn(self.deconv2(x)))
        x = F.relu(self.deconv3_pool(self.deconv3_bn(self.deconv3(x))))
        #print("x 3: {}".format(x.shape))
        x = F.relu(self.deconv4_pool(self.deconv4_bn(self.deconv4(x))))
        #print("x 4: {}".format(x.shape))
        x = F.tanh(self.deconv5(x))
        #print("x 5: {}".format(x.shape))

        return x

      
class discriminator(nn.Module):
    # initializers
    def __init__(self, d=128):
        super(discriminator, self).__init__()
        self.conv1 = nn.Conv2d(1, d, 4, 2, 1)
        self.conv2 = nn.Conv2d(d, d*2, 4, 2, 1)
        self.conv2_bn = nn.BatchNorm2d(d*2)
        self.conv3 = nn.Conv2d(d*2, d*4, 4, 2, 1)
        self.conv3_bn = nn.BatchNorm2d(d*4)
        self.conv4 = nn.Conv2d(d*4, d*8, 4, 2, 1)
        self.conv4_bn = nn.BatchNorm2d(d*8)
        self.conv5 = nn.Conv2d(d*8, 1, 4, 1, 0)

    # weight_init
    def weight_init(self, mean, std):
        for m in self._modules:
            normal_init(self._modules[m], mean, std)

    # forward method
    def forward(self, input):
        x = F.leaky_relu(self.conv1(input), 0.2)
        x = F.leaky_relu(self.conv2_bn(self.conv2(x)), 0.2)
        x = F.leaky_relu(self.conv3_bn(self.conv3(x)), 0.2)
        x = F.leaky_relu(self.conv4_bn(self.conv4(x)), 0.2)
        x = F.sigmoid(self.conv5(x))

        return x
      
def normal_init(m, mean, std):
    if isinstance(m, nn.ConvTranspose2d) or isinstance(m, nn.Conv2d):
        m.weight.data.normal_(mean, std)
        m.bias.data.zero_()

fixed_z_ = torch.randn((5 * 5, 100)).view(-1, 100, 1, 1)    # fixed noise
if torch.cuda.is_available():
    fixed_z_.cuda()
fixed_z_ = Variable(fixed_z_)
def show_result(G, num_epoch, show = False, save = False, path = 'result.png', isFix=False):
    z_ = torch.randn((5*5, 100)).view(-1, 100, 1, 1)
    if torch.cuda.is_available():
        z_.cuda()
    z_ = Variable(z_, volatile=True)

    G.eval()
    if isFix:
        test_images = G(fixed_z_)
    else:
        test_images = G(z_)
    G.train()

    size_figure_grid = 5
    fig, ax = plt.subplots(size_figure_grid, size_figure_grid, figsize=(5, 5))
    for i, j in itertools.product(range(size_figure_grid), range(size_figure_grid)):
        ax[i, j].get_xaxis().set_visible(False)
        ax[i, j].get_yaxis().set_visible(False)

    for k in range(5*5):
        i = k // 5
        j = k % 5
        ax[i, j].cla()
        ax[i, j].imshow(test_images[k, 0].cpu().data.numpy(), cmap='gray')

    label = 'Epoch {0}'.format(num_epoch)
    fig.text(0.5, 0.04, label, ha='center')
    plt.savefig(path)

    if show:
        plt.show()
    else:
        plt.close()

def show_train_hist(hist, show = False, save = False, path = 'Train_hist.png'):
    x = range(len(hist['D_losses']))

    y1 = hist['D_losses']
    y2 = hist['G_losses']

    plt.plot(x, y1, label='D_loss')
    plt.plot(x, y2, label='G_loss')

    plt.xlabel('Iter')
    plt.ylabel('Loss')

    plt.legend(loc=4)
    plt.grid(True)
    plt.tight_layout()

    if save:
        plt.savefig(path)

    if show:
        plt.show()
    else:
        plt.close()

"""# **Parameters + Run Model**"""

def main():
    global args

    # Setting the hyper parameters
    parser = argparse.ArgumentParser(description='Example of Capsule Network')
    parser.add_argument('--epochs', type=int, default=10,
                        help='number of training epochs. default=10')
    parser.add_argument('--lr', type=float, default=0.01,
                        help='learning rate. default=0.01')
    parser.add_argument('--batch-size', type=int, default=128,
                        help='training batch size. default=128')
    parser.add_argument('--test-batch-size', type=int,
                        default=128, help='testing batch size. default=128')
    parser.add_argument('--log-interval', type=int, default=10,
                        help='how many batches to wait before logging training status. default=10')
    parser.add_argument('--no-cuda', action='store_true', default=False,
                        help='disables CUDA training. default=false')
    parser.add_argument('--threads', type=int, default=4,
                        help='number of threads for data loader to use. default=4')
    parser.add_argument('--seed', type=int, default=42,
                        help='random seed for training. default=42')
    parser.add_argument('--num-conv-out-channel', type=int, default=256,
                        help='number of channels produced by the convolution. default=256')
    parser.add_argument('--num-conv-in-channel', type=int, default=1,
                        help='number of input channels to the convolution. default=1')
    parser.add_argument('--num-primary-unit', type=int, default=8,
                        help='number of primary unit. default=8')
    parser.add_argument('--primary-unit-size', type=int,
                        default=1152, help='primary unit size is 32 * 6 * 6. default=1152')
    parser.add_argument('--num-classes', type=int, default=1,
                        help='number of digit classes. 1 unit for one MNIST digit. default=10')
    parser.add_argument('--output-unit-size', type=int,
                        default=1, help='output unit size. default=16')
    parser.add_argument('--num-routing', type=int,
                        default=3, help='number of routing iteration. default=3')
    parser.add_argument('--use-reconstruction-loss', type=utils.str2bool, nargs='?', default=True,
                        help='use an additional reconstruction loss. default=True')
    parser.add_argument('--regularization-scale', type=float, default=0.0005,
                        help='regularization coefficient for reconstruction loss. default=0.0005')
    parser.add_argument('--dataset', help='the name of dataset (mnist, cifar10)', default='mnist')
    parser.add_argument('--input-width', type=int,
                        default=28, help='input image width to the convolution. default=28 for MNIST')
    parser.add_argument('--input-height', type=int,
                        default=28, help='input image height to the convolution. default=28 for MNIST')
    parser.add_argument('--is-training', type=int,
                        default=1, help='Whether or not is training, default is yes')
    parser.add_argument('--weights', type=str,
                        default=None, help='Load pretrained weights, default is none')

    args = parser.parse_args()

    print(args)

    # Check GPU or CUDA is available
    args.cuda = not args.no_cuda and torch.cuda.is_available()

    # Get reproducible results by manually seed the random number generator
    torch.manual_seed(args.seed)
    if args.cuda:
        torch.cuda.manual_seed(args.seed)



    # training parameters
    batch_size = 128
    lr = 0.0002
    train_epoch = 20

    # data_loader
    img_size = 28#64
    transform = transforms.Compose([
            transforms.Scale(img_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5))
    ])
    train_loader = torch.utils.data.DataLoader(
        datasets.MNIST('data', train=True, download=True, transform=transform),
        batch_size=batch_size, shuffle=True)

    # network
    G = generator(128)
    D = Net(num_conv_in_channel=args.num_conv_in_channel,
                    num_conv_out_channel=args.num_conv_out_channel,
                    num_primary_unit=args.num_primary_unit,
                    primary_unit_size=args.primary_unit_size,
                    num_classes=args.num_classes,
                    output_unit_size=args.output_unit_size,
                    num_routing=args.num_routing,
                    use_reconstruction_loss=args.use_reconstruction_loss,
                    regularization_scale=args.regularization_scale,
                    input_width=args.input_width,
                    input_height=args.input_height,
                    cuda_enabled=args.cuda)
    G.weight_init(mean=0.0, std=0.02)
    if args.cuda:
        print('Utilize GPUs for computation')
        print('Number of GPU available', torch.cuda.device_count())
        print('CUDNN version: ', torch.backends.cudnn.version())
        # torch.backends.cudnn.benchmark = True
        G = torch.nn.DataParallel(G).cuda()
        D = torch.nn.DataParallel(D).cuda()

    # Binary Cross Entropy loss
    BCE_loss = nn.BCELoss()

    # Adam optimizer
    G_optimizer = optim.Adam(G.parameters(), lr=lr, betas=(0.5, 0.999))
    D_optimizer = optim.Adam(D.parameters(), lr=lr, betas=(0.5, 0.999))

    # results save folder
    if not os.path.isdir('MNIST_DCGAN_results'):
        os.mkdir('MNIST_DCGAN_results')
    if not os.path.isdir('MNIST_DCGAN_results/Random_results'):
        os.mkdir('MNIST_DCGAN_results/Random_results')
    if not os.path.isdir('MNIST_DCGAN_results/Fixed_results'):
        os.mkdir('MNIST_DCGAN_results/Fixed_results')

    train_hist = {}
    train_hist['D_losses'] = []
    train_hist['G_losses'] = []
    train_hist['per_epoch_ptimes'] = []
    train_hist['total_ptime'] = []
    num_iter = 0

    print('training start!')
    start_time = time.time()

    for epoch in range(train_epoch):
        D_losses = []
        G_losses = []
        epoch_start_time = time.time()
        for x_, _ in train_loader:
            # train discriminator D
            D.zero_grad()
            mini_batch = x_.size()[0]

            y_real_ = torch.ones(mini_batch)
            y_fake_ = torch.zeros(mini_batch)
            if args.cuda:
                x_.cuda()
                y_real_.cuda()
                y_fake_.cuda()

            x_, y_real_, y_fake_ = Variable(x_), Variable(y_real_), Variable(y_fake_)
            D_result = D(x_).squeeze()
            D_real_loss = BCE_loss(D_result.cuda(), y_real_.cuda())

            z_ = torch.randn((mini_batch, 100)).view(-1, 100, 1, 1)
            if args.cuda:
                z_.cuda()
            z_ = Variable(z_)
            G_result = G(z_)

            #print("g result: {}".format(G_result.shape))

            D_result = D(G_result).squeeze()
            D_fake_loss = BCE_loss(D_result.cuda(), y_fake_.cuda())
            D_fake_score = D_result.data.mean()
            D_train_loss = D_real_loss + D_fake_loss
            D_train_loss.backward()
            D_optimizer.step()

            # D_losses.append(D_train_loss.data[0])
            D_losses.append(D_train_loss.data[0])

            # train generator G
            G.zero_grad()

            z_ = torch.randn((mini_batch, 100)).view(-1, 100, 1, 1)
		
            z_ = Variable(z_.cuda())
            G_result = G(z_)
            D_result = D(G_result).squeeze()
            G_train_loss = BCE_loss(D_result.cuda(), y_real_.cuda())
            G_train_loss.backward()
            G_optimizer.step()
            G_losses.append(G_train_loss.data[0])

            num_iter += 1

        epoch_end_time = time.time()
        per_epoch_ptime = epoch_end_time - epoch_start_time


        print('[%d/%d] - ptime: %.2f, loss_d: %.3f, loss_g: %.3f' % ((epoch + 1), train_epoch, per_epoch_ptime, torch.mean(torch.FloatTensor(D_losses)),
                                                                  torch.mean(torch.FloatTensor(G_losses))))
        p = 'MNIST_DCGAN_results/Random_results/MNIST_DCGAN_' + str(epoch + 1) + '.png'
        fixed_p = 'MNIST_DCGAN_results/Fixed_results/MNIST_DCGAN_' + str(epoch + 1) + '.png'
        show_result(G, (epoch+1), save=True, path=p, isFix=False)
        show_result(G, (epoch+1), save=True, path=fixed_p, isFix=True)
        train_hist['D_losses'].append(torch.mean(torch.FloatTensor(D_losses)))
        train_hist['G_losses'].append(torch.mean(torch.FloatTensor(G_losses)))
        train_hist['per_epoch_ptimes'].append(per_epoch_ptime)

    end_time = time.time()
    total_ptime = end_time - start_time
    train_hist['total_ptime'].append(total_ptime)

    print("Avg per epoch ptime: %.2f, total %d epochs ptime: %.2f" % (torch.mean(torch.FloatTensor(train_hist['per_epoch_ptimes'])), train_epoch, total_ptime))
    print("Training finish!... save training results")
    torch.save(G.state_dict(), "MNIST_DCGAN_results/generator_param.pkl")
    torch.save(D.state_dict(), "MNIST_DCGAN_results/discriminator_param.pkl")
    with open('MNIST_DCGAN_results/train_hist.pkl', 'wb') as f:
        pickle.dump(train_hist, f)

    show_train_hist(train_hist, save=True, path='MNIST_DCGAN_results/MNIST_DCGAN_train_hist.png')

    images = []
    for e in range(train_epoch):
        img_name = 'MNIST_DCGAN_results/Fixed_results/MNIST_DCGAN_' + str(e + 1) + '.png'
        images.append(imageio.imread(img_name))
    imageio.mimsave('MNIST_DCGAN_results/generation_animation.gif', images, fps=5)


if __name__ == "__main__":
    main()

